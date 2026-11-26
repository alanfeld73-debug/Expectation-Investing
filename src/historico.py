"""Brecha point-in-time en cada fecha de rebalanceo del backtest (sin look-ahead en los datos de compañías).

Uso: python historico.py  -> data/backtest/brechas.parquet

Para cada fecha t (fin de abril) y cada miembro del S&P 500 en t que sigue cotizando:
- Precio nominal de fin de abril (Yahoo, des-ajustado de splits posteriores) x acciones en circulación (SEC dei,
  último dato presentado hasta t) = market cap.
- Ventas, EBIT y utilidad del último ejercicio presentado hasta t; deuda, caja y patrimonio del último balance.
- Crecimiento año 1 = crecimiento de ventas del último ejercicio (reemplazo del consenso, PREREGISTRO.md).
- Beta: 60 meses de retornos contra SPY (mínimo 24). Rf: DGS10 a fin de abril.
- Defaults por sector: medianas de los miembros en t con datos hasta t.
Se valúa con screen_sp500.construir (el mismo modelo del screen diario) y se rankea con sesgo.rankings.

Limitación conocida: la distribución de base rates (punto de llegada de la desaceleración) usa ventas 2015-2025,
o sea información posterior a las primeras fechas. Afecta a todas las compañías por igual (depende solo del tamaño
y del crecimiento previo), no a una en particular.
"""
import io
import contextlib
import os
from types import SimpleNamespace

import numpy as np
import pandas as pd

import expectations_screen as E
import fundamentals as F
import screen_sp500 as SP
import sesgo
from baserates import prob
from pit import ROOT
from universo_bt import FECHAS

OUT = os.path.join(ROOT, "data", "backtest", "brechas.parquet")
RF_CSV = os.path.join(ROOT, "data", "rates", "DGS10.csv")


def rf_en(fecha):
    r = pd.read_csv(RF_CSV)
    r.columns = ["fecha", "v"]
    r["v"] = pd.to_numeric(r.v, errors="coerce")
    r = r.dropna()
    r = r[pd.to_datetime(r.fecha) <= fecha]
    return float(r.v.iloc[-1]) / 100


def betas(px, mes, n=60, minimo=24):
    ret = px.pivot(index="mes", columns="ticker", values="adjclose").sort_index().pct_change(fill_method=None)
    ventana = ret.loc[(ret.index > mes - n) & (ret.index <= mes)]
    spy = ventana["SPY"]
    out = {}
    for t in ventana.columns:
        x = pd.concat([ventana[t], spy], axis=1).dropna()
        if len(x) >= minimo:
            out[t] = x.iloc[:, 0].cov(x.iloc[:, 1]) / x.iloc[:, 1].var()
    return out


def fecha(t, u, px):
    mes = t.to_period("M")
    E.RF = rf_en(t)
    miembros = u[(u.fecha == t.date().isoformat()) & u.ticker.notna()]
    met = F.metricas_compania(as_of=t).set_index("ticker")
    met = met[met.index.isin(miembros.ticker)]
    m2 = miembros.merge(met, left_on="ticker", right_index=True, how="left")
    sec = m2.groupby("sector").agg(tax_default=("tax_rate", "median"), inv_default=("inv_rate", "median"))
    sec = sec.fillna({"tax_default": m2.tax_rate.median(), "inv_default": m2.inv_rate.median()})
    saldos = {c: F.ultimo_saldo(c, t) for c in ("shares_out", "debt_cur", "debt_lt", "cash", "st_invest", "equity")}
    p_mes = px[px.mes == mes].set_index("ticker")
    b = betas(px, mes)
    filas = []
    for r in miembros.itertuples():
        base = dict(fecha=t, ticker=r.ticker, sector=r.sector)
        if r.ticker not in p_mes.index or r.ticker not in met.index:
            filas.append(dict(base, nota="sin precio o sin datos SEC"))
            continue
        m = met.loc[r.ticker]
        precio = float(p_mes.loc[r.ticker, "close"] * p_mes.loc[r.ticker, "factor_split"])
        acc = saldos["shares_out"].get(r.ticker)
        if not acc or pd.isna(m.ventas_fy) or pd.isna(m.get("g_fy")):
            filas.append(dict(base, nota="faltan acciones, ventas o crecimiento"))
            continue
        g = lambda c: float(saldos[c].get(r.ticker, 0) or 0)
        d = dict(close=precio, market_cap_basic=precio * acc, total_revenue_ttm=m.ventas_fy,
                 oper_income_ttm=m.ebit_fy if pd.notna(m.ebit_fy) else None, net_income_ttm=m.ni_fy,
                 total_debt_fq=g("debt_cur") + g("debt_lt"), cash_n_short_term_invest_fq=g("cash") + g("st_invest"),
                 beta_5_year=b.get(r.ticker), total_equity_fq=g("equity") or None,
                 total_revenue_fy=m.ventas_fy / (1 + m.g_fy), revenue_forecast_next_fy=m.ventas_fy)
        rr = SimpleNamespace(ticker=r.ticker, sector=r.sector,
                             subindustria=r.subindustria if isinstance(r.subindustria, str) else "")
        sd = SimpleNamespace(tax_default=float(sec.loc[r.sector, "tax_default"]),
                             inv_default=float(sec.loc[r.sector, "inv_default"]))
        c, flags = SP.construir(rr, d, sd, dict(ventas_fy=m.ventas_fy, cagr3=m.get("cagr3")))
        if c is None:
            filas.append(dict(base, precio=precio, nota="; ".join(flags)))
            continue
        try:
            v4 = c.value_per_share(c.fade_path())
            gt = prob(c.sales0, 0.0, c.g_hist)[2] if c.sales0 > 0 else None
            c.g_term = float(np.clip(gt, *SP.G_TERM_CLIP)) if gt is not None else None
            v = c.value_per_share(c.fade_path())
        except (ZeroDivisionError, OverflowError, ValueError):
            filas.append(dict(base, precio=precio, nota="error de valuación"))
            continue
        ss = c.steady_state_share()
        if v < 0:
            flags.append("[revisar] valor negativo")
        if ss > SP.SS_MAX:
            flags.append("[revisar] valor sin crecimiento > 150% del EV")
        gi, p_br = None, None
        if c.model == "FCF" and c.m0 > 0:
            gi = c.implied_g()
            if gi is not None:
                p_br = prob(c.sales0, gi, c.g_hist)[0]
        ey = (c.ni0 / c.mcap) if c.model == "EQUITY" else (c.sales0 * c.m0 * (1 - c.tax) / c.ev)
        filas.append(dict(base, modelo=c.model, precio=precio, mcap_bn=c.mcap / 1e9, g_ref=c.g_ref, g_term=c.g_term,
                          g_impl=gi, p_base_rate=p_br, ss_share=ss, ey=ey, brecha=v / precio - 1,
                          brecha_4=v4 / precio - 1, rf=E.RF, nota="; ".join(flags)))
    df = pd.DataFrame(filas)
    ok = df.brecha.notna() & ~df.nota.fillna("").str.contains("[revisar]", regex=False)
    return sesgo.rankings(df, ok), len(miembros)


def main():
    u = pd.read_csv(os.path.join(ROOT, "data", "universo", "universo_bt.csv"))
    px = pd.read_parquet(os.path.join(ROOT, "data", "precios", "mensual.parquet"))
    import rates
    rates.rf10()   # asegura el CSV de DGS10 en caché
    partes = []
    for t in FECHAS:
        with contextlib.redirect_stdout(io.StringIO()):
            df, n = fecha(t, u, px)
        partes.append(df)
        print(f"[historico] {t.date()}: {n} miembros vigentes, {df.brecha.notna().sum()} valuadas, "
              f"{df.quintil.notna().sum()} rankeadas", flush=True)
    out = pd.concat(partes)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.to_parquet(OUT, index=False)
    print(f"-> {OUT}")
    return out


if __name__ == "__main__":
    main()
