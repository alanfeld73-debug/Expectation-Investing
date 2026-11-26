"""
Motor de DCF inverso — Expectations Investing (Rappaport & Mauboussin)
Prototipo v0.1 · caso BKNG

Uso:  python reverse_dcf.py            (corre el caso BKNG con los inputs de INPUTS)
Datos: XBRL de la SEC (companyfacts) + precio Nasdaq. Todo en USD millones.

Convenciones (fijas para que el screen sea comparable entre compañías):
  - NOPAT = EBIT GAAP x (1 - tasa impositiva). La SBC queda como gasto (no se suma).
  - FCF   = NOPAT - inversión incremental, con inversión = tasa x ΔVentas
            (capex neto de D&A + capital de trabajo).
  - Valor residual: perpetuidad de Rappaport, NOPAT_N / WACC (sin crecimiento:
            después del horizonte, ROIC incremental = costo de capital).
  - Valor del equity = valor operativo + caja e inversiones - deuda - leases.
"""
import json
import urllib.request
from dataclasses import dataclass, replace

import numpy as np
from scipy.optimize import brentq

from config import SEC_USER_AGENT

UA = {"User-Agent": SEC_USER_AGENT}


# ----------------------------------------------------------------------------
# Inputs
# ----------------------------------------------------------------------------
@dataclass
class Inputs:
    ticker: str
    price: float            # USD por acción
    shares: float           # millones
    sales0: float           # ventas base (TTM normalizadas)
    ebit_margin: float      # margen EBIT que se asume constante
    tax: float
    inv_rate: float         # inversión incremental / ΔVentas
    wacc: float
    cash_inv: float         # caja + inversiones
    debt: float             # deuda financiera + leases
    horizon: int = 10

    @property
    def mkt_cap(self):
        return self.price * self.shares

    @property
    def target_op_value(self):
        """Valor operativo que el mercado está pagando (EV)."""
        return self.mkt_cap + self.debt - self.cash_inv


# BKNG al 25-nov-2026. Fuentes: 10-K 2025 y 10-Q 3T26 (XBRL SEC), precio Nasdaq.
# TTM = FY25 + 9M26 - 9M25. Se suma de vuelta el cargo FTC de ~USD 0,9 bn
# registrado como menor ingreso en 3T26 (no recurrente según la compañía).
BKNG = Inputs(
    ticker="BKNG",
    price=149.50,
    shares=743.7,
    sales0=26917 + 21777 - 20568 + 900,          # 29.026
    ebit_margin=(8825 + 7189 - 6795 + 900) / (26917 + 21777 - 20568 + 900),
    tax=0.21,
    inv_rate=0.0,            # capex ≈ D&A y capital de trabajo negativo (float)
    wacc=0.095,              # Rf 4,85% + beta 1,1 x ERP 5% ; Kd 5,5% ; D/V 15%
    cash_inv=15814 + 435,
    debt=18074 + 1987 + 672,
)


# ----------------------------------------------------------------------------
# Motor
# ----------------------------------------------------------------------------
def operating_value(inp: Inputs, g: float, horizon: int | None = None,
                    margin: float | None = None, inv_rate: float | None = None,
                    wacc: float | None = None) -> float:
    N = inp.horizon if horizon is None else horizon
    m = inp.ebit_margin if margin is None else margin
    ir = inp.inv_rate if inv_rate is None else inv_rate
    k = inp.wacc if wacc is None else wacc

    pv, sales_prev, nopat = 0.0, inp.sales0, inp.sales0 * m * (1 - inp.tax)
    for t in range(1, N + 1):
        sales = sales_prev * (1 + g)
        nopat = sales * m * (1 - inp.tax)
        fcf = nopat - ir * (sales - sales_prev)
        pv += fcf / (1 + k) ** t
        sales_prev = sales
    residual = nopat / k / (1 + k) ** N
    return pv + residual


def steady_state_value(inp: Inputs) -> float:
    """Valor sin crecimiento: NOPAT actual a perpetuidad."""
    return inp.sales0 * inp.ebit_margin * (1 - inp.tax) / inp.wacc


def implied_growth(inp: Inputs, **kw) -> float:
    """CAGR de ventas a `horizon` años que justifica el precio actual."""
    f = lambda g: operating_value(inp, g, **kw) - inp.target_op_value
    return brentq(f, -0.30, 0.60)


def implied_forecast_period(inp: Inputs, g: float, max_years: int = 40) -> float:
    """Market-Implied Forecast Period: años de crecimiento a `g` que descuenta el precio."""
    target = inp.target_op_value
    vals = [operating_value(inp, g, horizon=n) for n in range(0, max_years + 1)]
    for n in range(1, len(vals)):
        if vals[n] >= target:  # interpolación lineal entre años
            return n - 1 + (target - vals[n - 1]) / (vals[n] - vals[n - 1])
    return float("inf")


def value_per_share(inp: Inputs, op_value: float) -> float:
    return (op_value + inp.cash_inv - inp.debt) / inp.shares


def trigger_sensitivity(inp: Inputs, g: float) -> dict:
    """Cambio % en valor por acción ante shocks a cada value driver."""
    base = value_per_share(inp, operating_value(inp, g))
    shocks = {
        "Ventas +1pp CAGR": dict(g=g + 0.01),
        "Margen EBIT +1pp": dict(g=g, margin=inp.ebit_margin + 0.01),
        "Inversión incremental +10pp": dict(g=g, inv_rate=inp.inv_rate + 0.10),
        "WACC -50bp": dict(g=g, wacc=inp.wacc - 0.005),
    }
    out = {}
    for name, kw in shocks.items():
        v = value_per_share(inp, operating_value(inp, **kw))
        out[name] = v / base - 1
    return out


# ----------------------------------------------------------------------------
# Datos SEC (para escalar al universo; BKNG ya está precargado arriba)
# ----------------------------------------------------------------------------
def sec_companyfacts(cik: int) -> dict:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    req = urllib.request.Request(url, headers=UA)
    return json.load(urllib.request.urlopen(req))


# ----------------------------------------------------------------------------
# Reporte
# ----------------------------------------------------------------------------
def report(inp: Inputs, hist_cagr: dict, scenarios: dict):
    ev = inp.target_op_value
    ssv = steady_state_value(inp)
    g_imp = implied_growth(inp)
    print(f"=== {inp.ticker} · DCF inverso ===")
    print(f"Precio {inp.price:.2f} | Market cap {inp.mkt_cap/1e3:.1f} bn | EV {ev/1e3:.1f} bn")
    print(f"Ventas base {inp.sales0/1e3:.2f} bn | Margen EBIT {inp.ebit_margin:.1%} | "
          f"NOPAT {inp.sales0*inp.ebit_margin*(1-inp.tax)/1e3:.2f} bn | EV/NOPAT "
          f"{ev/(inp.sales0*inp.ebit_margin*(1-inp.tax)):.1f}x")
    print(f"Valor steady-state (sin crecimiento): {ssv/1e3:.1f} bn = {ssv/ev:.0%} del EV"
          f" -> el mercado paga {1-ssv/ev:.0%} por crecimiento futuro")
    print(f"\nCrecimiento implícito (CAGR ventas {inp.horizon} años, margen constante): {g_imp:.1%}")
    for name, c in hist_cagr.items():
        print(f"   vs. {name}: {c:.1%}")

    print("\nMIFP (años de crecimiento que descuenta el precio):")
    for g in (0.04, 0.06, 0.08, 0.10):
        print(f"   creciendo {g:.0%} anual: {implied_forecast_period(inp, g):.1f} años")

    print("\nSensibilidad del crecimiento implícito (filas WACC, columnas margen EBIT):")
    margins = [inp.ebit_margin - 0.04, inp.ebit_margin - 0.02, inp.ebit_margin, inp.ebit_margin + 0.02]
    print("WACC   " + "".join(f"{m:>9.1%}" for m in margins))
    for k in (0.085, 0.09, 0.095, 0.10, 0.105):
        row = []
        for m in margins:
            try:
                row.append(f"{implied_growth(inp, wacc=k, margin=m):>9.1%}")
            except ValueError:
                row.append(f"{'n/a':>9}")
        print(f"{k:.1%}  " + "".join(row))

    print("\nTurbina de value triggers (Δ% valor/acción, alrededor de g implícito):")
    for k, v in trigger_sensitivity(inp, g_imp).items():
        print(f"   {k:<30} {v:+.1%}")

    print("\nEscenarios (valor por acción y retorno implícito):")
    ev_w = 0.0
    for name, (p, g, m) in scenarios.items():
        v = value_per_share(inp, operating_value(inp, g, margin=m))
        ev_w += p * v
        print(f"   {name:<10} p={p:.0%}  g={g:.0%}  margen={m:.0%}  -> {v:7.2f}  ({v/inp.price-1:+.0%})")
    print(f"   Valor esperado ponderado: {ev_w:.2f}  ({ev_w/inp.price-1:+.0%} vs precio)")


if __name__ == "__main__":
    hist = {
        "historia 2015-2025 (incluye COVID)": (26917 / 9224) ** (1 / 10) - 1,
        "historia 2019-2025": (26917 / 15066) ** (1 / 6) - 1,
    }
    # (probabilidad, CAGR ventas 10 años, margen EBIT) — supuestos editables
    escenarios = {
        "Bajista": (0.25, 0.02, 0.29),   # desintermediación por IA/Google, take rate cae
        "Base":    (0.50, 0.07, 0.34),   # room nights mid-single digit + alternativos/pagos
        "Alcista": (0.25, 0.10, 0.37),   # connected trip + apalancamiento operativo
    }
    report(BKNG, hist, escenarios)
