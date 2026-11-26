"""
Expectations Investing — screen batch v0.2
Corre el DCF inverso sobre una lista de tickers con datos TTM de TradingView
(validados contra XBRL de la SEC para BKNG) y supuestos por compañía.

Uso: python expectations_screen.py   -> imprime tabla y guarda screen_output.csv

Tres modelos, según el tipo de negocio:
  FCF     DCF de firma (Rappaport): NOPAT - inversión incremental, residual NOPAT/WACC.
  RAMP    Igual que FCF, pero el margen converge de m0 a un margen objetivo en
          `ramp` años (para compañías sin EBIT positivo o en inversión).
  EQUITY  Para bancos (NU): FCFE = NI - ΔPatrimonio, con ROE constante.

Métricas por compañía:
  g_impl     CAGR de ventas a 10 años que justifica el precio (margen según modelo)
  g_ref      crecimiento de referencia: consenso del próximo FY (o override)
  V_fade     valor/acción si la compañía cumple g_ref en el año 1 y desacelera
             linealmente hasta 4% nominal en el año 10, con márgenes del modelo
  upside     V_fade / precio - 1
  ss_share   % del EV explicado por el valor sin crecimiento (NOPAT0 / WACC)
"""
import csv
import datetime as dt
import json
import os
import urllib.request
from dataclasses import dataclass, field

from scipy.optimize import brentq

RF, ERP, G_TERMINAL, H = 0.0485, 0.05, 0.04, 10   # RF: UST 10 años (fecha de toma: ver SUPUESTOS.md)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

TICKERS = {
    # ticker: (símbolo TradingView, modelo)
    "TOYO": ("NASDAQ:TOYO", "FCF"), "CEG": ("NASDAQ:CEG", "EQUITY"),
    "NBIS": ("NASDAQ:NBIS", "RAMP"), "MP": ("NYSE:MP", "RAMP"),
    "GGGOF": ("OTC:GGGOF", "FCF"), "RX": ("TSXV:RX", "FCF"),
    "CROX": ("NASDAQ:CROX", "FCF"), "VST": ("NYSE:VST", "EQUITY"),
    "CART": ("NASDAQ:CART", "FCF"), "VU": ("EURONEXT:VU", "FCF"),
    "VIST": ("NYSE:VIST", "FCF"), "TLN": ("NASDAQ:TLN", "EQUITY"),
    "MELI": ("NASDAQ:MELI", "RAMP"), "NVO": ("NYSE:NVO", "FCF"),
    "V": ("NYSE:V", "FCF"), "BKNG": ("NASDAQ:BKNG", "FCF"),
    "DLO": ("NASDAQ:DLO", "FCF"), "UBER": ("NYSE:UBER", "FCF"),
    "CTEK": ("TSXV:CTEK", "FCF"),   # supuesto: Cleantek (TSXV); podría ser CTEK AB (OMX)
    "NU": ("NYSE:NU", "EQUITY"), "GTBIF": ("OTC:GTBIF", "FCF"),
}

# Supuestos por compañía. tax = tasa sobre EBIT; inv = inversión incremental / ΔVentas;
# crp = prima riesgo país en Ke; spread = spread de deuda sobre RF;
# m_target/ramp solo para RAMP; g_ref override cuando el consenso está distorsionado por M&A;
# adj_rev/adj_ebit = normalizaciones (USD).
A = {
    "TOYO":  dict(tax=0.20, inv=0.40, crp=0.015, spread=0.04, note="Sin TTM: usa FY; solar, microcap"),
    # Generadores: modelo de equity sobre utilidad/FCF ajustado de guidance (evita el MTM de coberturas).
    # ni = base año 1; roe_inc = retorno sobre el capital incremental que financia el crecimiento.
    "CEG":   dict(ni=12.65 * 356e6, roe_inc=0.15, g_ref=0.08,
                  note="Base: EPS ajustado 2026 guía (12,50-12,80) x 356 M acc."),
    "NBIS":  dict(tax=0.21, inv=1.30, m_target=0.25, ramp=6, g_ref=0.60, note="Neocloud; valor depende del ROIC incremental"),
    "MP":    dict(tax=0.21, inv=0.80, m_target=0.30, ramp=5, g_ref=0.40, note="Precio piso DoD; muy especulativo"),
    "GGGOF": dict(tax=0.27, inv=0.30, crp=0.025, spread=0.04, g_ref=0.10, note="Mina de oro; valor ligado a precio del oro y vida de reservas"),
    "RX":    dict(tax=0.265, inv=0.10, g_ref=0.10, note="Datos TradingView sin validar"),
    "CROX":  dict(tax=0.22, inv=0.15),
    "VST":   dict(ni=4.7e9, roe_inc=0.15, g_ref=0.06,
                  note="Base: FCF antes de crecimiento 2027 guía (4,3-5,1 bn)"),
    "CART":  dict(tax=0.25, inv=0.05),
    "VU":    dict(tax=0.25, inv=0.20, note="FCF negativo por capital de trabajo (rollout)"),
    "VIST":  dict(tax=0.35, inv=0.90, crp=0.05, spread=0.03, g_ref=0.12,
                  note="E&P: mejor complementar con NAV de reservas; M&A distorsiona consenso"),
    "TLN":   dict(ni=1.625e9, roe_inc=0.15, g_ref=0.08,
                  note="Base: FCF ajustado 2027 guía (1,50-1,75 bn)"),
    "MELI":  dict(tax=0.30, inv=0.25, crp=0.025, m_target=0.10, ramp=5,
                  note="Margen deprimido por crédito/envíos; deuda fintech tratada como operativa"),
    "NVO":   dict(tax=0.21, inv=0.40, adj_rev=-4.2e9, adj_ebit=-4.2e9, g_ref=0.0,
                  note="Sin reversión 340B (USD 4,2 bn); recortes de precio de lista en 2027"),
    "V":     dict(tax=0.18, inv=0.10),
    "BKNG":  dict(tax=0.21, inv=0.00, adj_rev=0.9e9, adj_ebit=0.9e9, note="Normalizado por cargo FTC"),
    "DLO":   dict(tax=0.16, inv=0.05, crp=0.03, driver_ratio=0.33, g_ref=0.275,
                  note="Driver = margen bruto (TPV x take rate), no ingresos"),
    "UBER":  dict(tax=0.21, inv=0.05),
    "CTEK":  dict(tax=0.23, inv=0.40, spread=0.04, g_ref=0.15, note="Ticker ambiguo; microcap"),
    "NU":    dict(crp=0.025, g_ref=0.25, note="Modelo de equity (banco); tasa efectiva sube a 20-25% en 2027"),
    "GTBIF": dict(tax=0.50, inv=0.20, note="Tasa alta por 280E; reprogramación sería trigger"),
}

COLS = ["close", "market_cap_basic", "total_revenue_ttm", "total_revenue_fy", "oper_income_ttm",
        "oper_income_fy", "net_income_ttm", "total_debt_fq", "cash_n_short_term_invest_fq",
        "beta_5_year", "revenue_forecast_next_fy", "total_equity_fq", "total_revenue_yoy_growth_ttm"]


def tv_scan(symbols, refresh=False):
    """Scanner de TradingView con caché diario en data/tv_scan_AAAA-MM-DD.json."""
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, f"tv_scan_{dt.date.today():%Y-%m-%d}.json")
    cache = {}
    if os.path.exists(path):
        with open(path) as f:
            cache = json.load(f)
    missing = [s for s in symbols if s not in cache]
    if missing or refresh:
        cache.update(_tv_fetch(symbols if refresh else missing))
        with open(path, "w") as f:
            json.dump(cache, f, indent=1)
    return cache


def _tv_fetch(symbols):
    body = json.dumps({"symbols": {"tickers": symbols}, "columns": COLS}).encode()
    req = urllib.request.Request("https://scanner.tradingview.com/global/scan", data=body,
                                 headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})
    data = json.load(urllib.request.urlopen(req))["data"]
    return {x["s"]: dict(zip(COLS, x["d"])) for x in data}


@dataclass
class Co:
    t: str
    model: str
    price: float
    mcap: float
    sales0: float
    m0: float
    tax: float
    inv: float
    wacc: float
    ke: float
    net_debt: float
    g_ref: float
    m_target: float
    ramp: int
    ni0: float = 0.0
    roe: float = 0.15
    g_hist: float | None = None
    note: str = ""
    flags: list = field(default_factory=list)

    @property
    def ev(self):
        return self.mcap + self.net_debt

    @property
    def target(self):
        return self.mcap if self.model == "EQUITY" else self.ev

    def margin(self, t, m_shift=0.0):
        if self.ramp <= 0:
            return self.m0 + m_shift
        w = min(t / self.ramp, 1.0)
        return self.m0 + (self.m_target - self.m0) * w + m_shift

    # --- valor operativo (o del equity) para una trayectoria de crecimiento ---
    def op_value(self, path, m_shift=0.0, inv=None, k=None, roe=None):
        if self.model == "EQUITY":
            ke = self.ke if k is None else k
            roe = self.roe if roe is None else roe
            ni, pv = self.ni0, 0.0
            for t, g in enumerate(path, 1):
                ni_new = ni * (1 + g)
                # Para crecer g hay que retener g/ROE de la utilidad
                pv += ni_new * (1 - g / roe) / (1 + ke) ** t
                ni = ni_new
            return pv + ni / ke / (1 + ke) ** len(path)
        inv = self.inv if inv is None else inv
        k = self.wacc if k is None else k
        pv, s_prev, nopat = 0.0, self.sales0, 0.0
        for t, g in enumerate(path, 1):
            s = s_prev * (1 + g)
            nopat = s * self.margin(t, m_shift) * (1 - self.tax)
            pv += (nopat - inv * (s - s_prev)) / (1 + k) ** t
            s_prev = s
        return pv + nopat / k / (1 + k) ** len(path)

    def implied_g(self, **kw):
        f = lambda g: self.op_value([g] * H, **kw) - self.target
        # En el modelo de equity el valor deja de crecer con g cuando g se acerca al ROE,
        # así que se acota el intervalo de búsqueda por debajo del ROE incremental.
        his = [1.5] if self.model == "FCF" else [min(0.6, 0.95 * (kw.get("roe") or self.roe))]
        lo = -0.5
        for hi in his:
            if f(lo) * f(hi) <= 0:
                return brentq(f, lo, hi)
        return None

    def fade_path(self, n=H):
        g1 = self.g_ref
        path = [g1 + (G_TERMINAL - g1) * i / (H - 1) for i in range(H)]
        return (path + [G_TERMINAL] * max(0, n - H))[:n]

    def mifp(self, max_years=40):
        """Market-Implied Forecast Period: años de creación de valor (con la trayectoria
        de consenso + fade) que hacen falta para justificar el precio."""
        vals = [self.op_value(self.fade_path(n)) if n else
                (self.ni0 / self.ke if self.model == "EQUITY"
                 else self.sales0 * self.margin(0) * (1 - self.tax) / self.wacc)
                for n in range(max_years + 1)]
        for n in range(1, len(vals)):
            if vals[n] >= self.target > vals[n - 1]:
                return n - 1 + (self.target - vals[n - 1]) / (vals[n] - vals[n - 1])
        return 0.0 if vals[0] >= self.target else float("inf")

    def value_per_share(self, path, **kw):
        v = self.op_value(path, **kw)
        eq = v if self.model == "EQUITY" else v - self.net_debt
        return eq / self.mcap * self.price

    def steady_state_share(self):
        if self.model == "EQUITY":
            return self.ni0 / self.ke / self.mcap
        return self.sales0 * self.m0 * (1 - self.tax) / self.wacc / self.ev

    def turbine(self):
        """Δ% del valor por acción ante shocks a cada value driver (sobre la trayectoria fade)."""
        p = self.fade_path()
        base = self.value_per_share(p)
        up = [g + 0.01 for g in p]
        if self.model == "EQUITY":
            shocks = {"Crecimiento +1pp": dict(path=up), "ROE incremental +2pp": dict(path=p, roe=self.roe + 0.02),
                      "Ke -50bp": dict(path=p, k=self.ke - 0.005)}
        else:
            shocks = {"Ventas +1pp": dict(path=up), "Margen +1pp": dict(path=p, m_shift=0.01),
                      "Inversión +10pp": dict(path=p, inv=self.inv + 0.10),
                      "WACC -50bp": dict(path=p, k=self.wacc - 0.005)}
        return {n: self.value_per_share(**kw) / base - 1 for n, kw in shocks.items()}


def build(t, sym, model, d):
    a = A[t]
    flags = []
    sales = d["total_revenue_ttm"] or d["total_revenue_fy"]
    ebit = d["oper_income_ttm"] if d["oper_income_ttm"] is not None else d["oper_income_fy"]
    for k, v in (("close", d["close"]), ("market_cap_basic", d["market_cap_basic"]), ("ventas", sales), ("EBIT", ebit)):
        if v is None:
            raise ValueError(f"{t}: falta {k} en TradingView")
    if d["total_revenue_ttm"] is None:
        flags.append("sin TTM")
    sales += a.get("adj_rev", 0)
    ebit += a.get("adj_ebit", 0)
    if "driver_ratio" in a:      # p.ej. DLO: se modela margen bruto en lugar de ingresos
        sales *= a["driver_ratio"]
    debt, cash = d["total_debt_fq"] or 0, d["cash_n_short_term_invest_fq"] or 0
    mcap = d["market_cap_basic"]
    beta = min(max(d["beta_5_year"] or 1.0, 0.8), 1.8)
    crp = a.get("crp", 0.0)
    ke = RF + beta * ERP + crp
    kd = (RF + a.get("spread", 0.0125) + crp) * (1 - a.get("tax", 0.21))
    wd = debt / (debt + mcap) if model != "EQUITY" else 0
    wacc = (1 - wd) * ke + wd * kd
    if "g_ref" in a:
        g_ref = a["g_ref"]
    elif d["revenue_forecast_next_fy"] and d["total_revenue_fy"]:
        g_ref = d["revenue_forecast_next_fy"] / d["total_revenue_fy"] - 1
    else:
        g_ref = (d["total_revenue_yoy_growth_ttm"] or 5) / 100
    g_ref = max(min(g_ref, 0.60), -0.10)
    ni0 = a.get("ni", d["net_income_ttm"] or 0)
    roe = a.get("roe_inc", (d["net_income_ttm"] or 0) / (d["total_equity_fq"] or 1))
    g_hist = (d["total_revenue_yoy_growth_ttm"] or 0) / 100
    return Co(t=t, model="EQUITY" if model == "EQUITY" else "FCF", price=d["close"], mcap=mcap,
              sales0=sales, m0=ebit / (sales / a.get("driver_ratio", 1)) / a.get("driver_ratio", 1),
              tax=a.get("tax", 0.21), inv=a.get("inv", 0.1),
              wacc=wacc, ke=ke, net_debt=0 if model == "EQUITY" else debt - cash, g_ref=g_ref,
              m_target=a.get("m_target", ebit / sales), ramp=a.get("ramp", 0) if model == "RAMP" else 0,
              ni0=ni0, roe=roe, g_hist=g_hist, note=a.get("note", ""), flags=flags)


def vist_implied_oil(ev, wacc, prod_kboed=170, ebitda_per_boe_per_usd=0.645, da_per_boe=18.6, tax=0.35):
    """VIST: precio realizado de petróleo (plano, a perpetuidad) que justifica el EV,
    con producción constante y capex de sostenimiento = D&A. EBITDA/boe ≈ 0,645 x precio
    (calibrado con la sensibilidad de USD 200 M por cada USD 10/bbl en un semestre)."""
    boe = prod_kboed * 1e3 * 365
    ebit_per_boe = ev * wacc / (1 - tax) / boe
    return (ebit_per_boe + da_per_boe) / ebitda_per_boe_per_usd


def main():
    from baserates import prob
    raw = tv_scan([s for s, _ in TICKERS.values()])
    rows, cos = [], {}
    for t, (sym, model) in TICKERS.items():
        if sym not in raw:
            print(f"[screen] {t}: {sym} no vino en el scan de TradingView, se omite")
            continue
        try:
            c = build(t, sym, model, raw[sym])
        except ValueError as e:
            print(f"[screen] {e}, se omite")
            continue
        cos[t] = c
        gi = c.implied_g()
        v = c.value_per_share(c.fade_path())
        p_br = None
        if gi is not None and c.model == "FCF" and A[t].get("driver_ratio") is None:
            p_br = prob(c.sales0, gi, c.g_hist)[0]
        rows.append(dict(
            ticker=t, modelo=model, precio=c.price, ev_bn=c.target / 1e9,
            wacc=c.ke if c.model == "EQUITY" else c.wacc, ss_share=c.steady_state_share(),
            g_impl=gi, p_base_rate=p_br, g_ref=c.g_ref, mifp=c.mifp(),
            v_fade=v, upside=v / c.price - 1, nota="; ".join(c.flags + ([c.note] if c.note else []))))
    rows.sort(key=lambda r: r["upside"], reverse=True)
    pct = lambda x: "   n/a" if x is None else f"{x:6.1%}"
    print(f"{'Tk':6}{'Mod':7}{'Precio':>9}{'EV bn':>8}{'WACC':>7}{'SS%EV':>7}{'g_impl':>8}"
          f"{'P(br)':>7}{'g_ref':>7}{'MIFP':>6}{'V_fade':>9}{'Upside':>8}")
    for r in rows:
        mf = "  >40" if r["mifp"] == float("inf") else f"{r['mifp']:5.1f}"
        print(f"{r['ticker']:6}{r['modelo']:7}{r['precio']:9.2f}{r['ev_bn']:8.1f}{pct(r['wacc'])}"
              f"{pct(r['ss_share'])}  {pct(r['g_impl'])}{pct(r['p_base_rate'])}{pct(r['g_ref'])}"
              f"{mf} {r['v_fade']:8.2f}{pct(r['upside'])}")
    if "VIST" in cos:
        ev = cos["VIST"].ev
        print("\nVIST — precio realizado de petróleo implícito (producción 170 kboe/d plana):")
        for w in (0.10, cos["VIST"].wacc, 0.13):
            print(f"   WACC {w:.1%}: USD {vist_implied_oil(ev, w):.1f}/bbl")
    with open(os.path.join(DATA, "screen_output.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return cos


if __name__ == "__main__":
    main()
