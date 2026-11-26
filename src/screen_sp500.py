"""Semana 1 — corrida cruda del S&P 500 con defaults por sector.

Uso: python screen_sp500.py   -> data/screen_sp500.csv y resultados/screen_sp500_AAAA-MM-DD.xlsx

Fuentes: precios, TTM, beta, deuda/caja y consenso de TradingView; tasa impositiva e inversión
incremental = defaults por sector (medianas de la SEC, defaults_sector.py); crecimiento previo = CAGR
3 años de la SEC; Rf = FRED DGS10. Sin overrides manuales: es la corrida "cruda" que la Semana 2 normaliza.

Modelo: EQUITY para bancos, aseguradoras, brokers, consumer finance y holdings (sobre utilidad TTM, ROE
TTM); FCF para el resto (incluye procesadores de pagos, bolsas/datos y brokers de seguros).
Brecha = V_fade / precio - 1 (valor con consenso año 1 + fade a 4%, sobre precio). Quintil 1 = mayor brecha.
"""
import datetime as dt
import json
import os
import urllib.request

import numpy as np
import pandas as pd

import defaults_sector as DS
import expectations_screen as E
import rates
from baserates import prob
from pit import ROOT, universo

EQUITY_SUBIND = {"Asset Management & Custody Banks", "Property & Casualty Insurance", "Diversified Banks",
                 "Investment Banking & Brokerage", "Regional Banks", "Life & Health Insurance",
                 "Consumer Finance", "Multi-line Insurance", "Multi-Sector Holdings", "Reinsurance"}
SPREAD = 0.0125
ROE_CLIP = (0.05, 0.30)
TV_COLS = ["name"] + E.COLS


def tv_bulk(tickers):
    os.makedirs(E.DATA, exist_ok=True)
    path = os.path.join(E.DATA, f"tv_sp500_{dt.date.today():%Y-%m-%d}.json")
    if os.path.exists(path):
        return json.load(open(path))
    body = {"filter": [{"left": "name", "operation": "in_range", "right": tickers}], "columns": TV_COLS,
            "range": [0, 2000], "markets": ["america"]}
    req = urllib.request.Request("https://scanner.tradingview.com/america/scan", data=json.dumps(body).encode(),
                                 headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})
    data = json.load(urllib.request.urlopen(req, timeout=60))["data"]
    out = {}
    for x in data:
        d = dict(zip(TV_COLS, x["d"]))
        out[d["name"]] = dict(d, tv_symbol=x["s"])
    json.dump(out, open(path, "w"))
    return out


def construir(r, d, sec_def, co_m):
    """Arma el objeto Co del screen con defaults por sector. Devuelve (Co o None, flags)."""
    flags = []
    model = "EQUITY" if r.subindustria in EQUITY_SUBIND else "FCF"
    sales = d.get("total_revenue_ttm") or d.get("total_revenue_fy")
    ebit = d.get("oper_income_ttm") if d.get("oper_income_ttm") is not None else d.get("oper_income_fy")
    price, mcap = d.get("close"), d.get("market_cap_basic")
    if not price or not mcap:
        return None, ["sin precio/market cap"]
    tax, inv = sec_def.tax_default, sec_def.inv_default
    debt, cash = d.get("total_debt_fq") or 0, d.get("cash_n_short_term_invest_fq") or 0
    beta = min(max(d.get("beta_5_year") or 1.0, 0.8), 1.8)
    ke = E.RF + beta * E.ERP
    if model == "EQUITY":
        ni = d.get("net_income_ttm")
        eq = d.get("total_equity_fq")
        if not ni or ni <= 0 or not eq or eq <= 0:
            return None, ["EQUITY sin utilidad o patrimonio positivo"]
        roe = float(np.clip(ni / eq, *ROE_CLIP))
        wacc, net_debt = ke, 0.0
    else:
        if not sales or ebit is None:
            return None, ["sin ventas/EBIT"]
        if ebit <= 0:
            flags.append("EBIT ≤ 0: requiere RAMP manual")
        kd = (E.RF + SPREAD) * (1 - tax)
        wd = debt / (debt + mcap)
        wacc = (1 - wd) * ke + wd * kd
        ni, roe, net_debt = 0.0, 0.15, debt - cash
    fy, fwd = d.get("total_revenue_fy"), d.get("revenue_forecast_next_fy")
    if fwd and fy:
        g_ref = fwd / fy - 1
    else:
        g_ref = (d.get("total_revenue_yoy_growth_ttm") or 5) / 100
        flags.append("sin consenso: g_ref = crecimiento TTM")
    g_ref = max(min(g_ref, 0.60), -0.10)
    # Conciliación TV vs SEC (ventas del último ejercicio)
    if co_m is not None and pd.notna(co_m.get("ventas_fy")) and sales and model == "FCF":
        ratio = sales / co_m["ventas_fy"]
        if not 0.85 <= ratio <= 1.6:
            flags.append(f"conciliar ventas: TV TTM / SEC FY = {ratio:.2f}")
    c = E.Co(t=r.ticker, model=model, price=price, mcap=mcap, sales0=sales or 0.0,
             m0=(ebit / sales) if sales and ebit is not None else 0.0, tax=tax, inv=inv, wacc=wacc, ke=ke,
             net_debt=net_debt, g_ref=g_ref, m_target=(ebit / sales) if sales and ebit is not None else 0.0,
             ramp=0, ni0=ni, roe=roe, g_hist=co_m.get("cagr3") if co_m is not None else None, flags=flags)
    return c, flags


def main():
    E.RF, E.RF_DATE, rf_src = rates.rf10()
    print(f"Rf = {E.RF:.2%} al {E.RF_DATE} [{rf_src}]")
    co, sec = DS.main()
    sec_by = sec.set_index("sector")
    co_by = co.set_index("ticker")
    u = universo()
    tv = tv_bulk(list(u.ticker))
    rows = []
    for r in u.itertuples():
        d = tv.get(r.ticker)
        base = dict(ticker=r.ticker, nombre=r.nombre, sector=r.sector, subindustria=r.subindustria)
        if d is None:
            rows.append(dict(base, nota="no vino en TradingView"))
            continue
        cm = co_by.loc[r.ticker].to_dict() if r.ticker in co_by.index else None
        c, flags = construir(r, d, sec_by.loc[r.sector], cm)
        if c is None:
            rows.append(dict(base, precio=d.get("close"), nota="; ".join(flags)))
            continue
        gi = c.implied_g() if c.m0 > 0 or c.model == "EQUITY" else None
        v = c.value_per_share(c.fade_path())
        p_br = None
        if gi is not None and c.model == "FCF" and c.sales0 > 0:
            p_br = prob(c.sales0, gi, c.g_hist)[0]
        rows.append(dict(base, modelo=c.model, precio=c.price, mcap_bn=c.mcap / 1e9, ev_bn=c.target / 1e9,
                         tasa_imp=c.tax if c.model == "FCF" else None, tasa_inv=c.inv if c.model == "FCF" else None,
                         margen_ebit=c.m0 if c.model == "FCF" else None, roe=c.roe if c.model == "EQUITY" else None,
                         wacc=c.ke if c.model == "EQUITY" else c.wacc, ss_share=c.steady_state_share(),
                         g_impl=gi, g_hist3=c.g_hist, p_base_rate=p_br, g_ref=c.g_ref, mifp=c.mifp(),
                         v_fade=v, brecha=v / c.price - 1, nota="; ".join(flags)))
    df = pd.DataFrame(rows)
    ok = df.brecha.notna() & ~df.nota.fillna("").str.contains("EBIT ≤ 0")
    df.loc[ok, "quintil"] = pd.qcut(df.loc[ok, "brecha"].rank(method="first", ascending=False), 5,
                                    labels=[1, 2, 3, 4, 5]).astype(int)
    df["rf"], df["rf_fecha"] = E.RF, E.RF_DATE
    df = df.sort_values("brecha", ascending=False)
    out = os.path.join(E.DATA, "screen_sp500.csv")
    df.to_csv(out, index=False)
    print(f"{len(df)} compañías; {ok.sum()} con brecha válida -> {out}")
    return df, co, sec


if __name__ == "__main__":
    main()
