"""Universo del backtest: miembros del S&P 500 en cada fecha de rebalanceo que siguen cotizando hoy.

Uso: python universo_bt.py  -> data/universo/universo_bt.csv

- Composición histórica: data/universo/sp500_historico.csv (fja05680/sp500).
- Cambios de ticker de la misma compañía (mismo CIK): RENOMBRES. Las que fueron compradas, se fusionaron
  o quebraron quedan afuera (decisión del usuario, PREREGISTRO.md) y se cuentan por fecha.
- Sector: GICS si la compañía está en la lista actual; si no, se deriva del código SIC de la SEC (SIC_A_GICS).
"""
import json
import os

import pandas as pd

import sec
from pit import ROOT, universo

FECHAS = [pd.Timestamp(f"{y}-04-30") for y in range(2016, 2027)]   # rebalanceo anual, fin de abril
OUT = os.path.join(ROOT, "data", "universo", "universo_bt.csv")
HIST = os.path.join(ROOT, "data", "universo", "sp500_historico.csv")

# Ticker histórico -> ticker actual de la MISMA compañía (mismo emisor/CIK). Fuente: conocimiento público de
# cambios de nombre; anotado en SUPUESTOS.md.
RENOMBRES = {
    "FB": "META", "ANTM": "ELV", "ABC": "COR", "BLL": "BALL", "FBHS": "FBIN", "FLT": "CPAY", "GPS": "GAP",
    "HFC": "DINO", "JEC": "J", "KORS": "CPRI", "NLOK": "GEN", "SYMC": "GEN", "PEAK": "DOC", "HCP": "DOC",
    "PKI": "RVTY", "RE": "EG", "TMK": "GL", "WLTW": "WTW", "HRS": "LHX", "UTX": "RTX", "DWDP": "DD",
    "ADS": "BFH", "ARNC": "HWM", "CTL": "LUMN",
}


def sic_a_gics(sic):
    """Mapa aproximado SIC -> sector GICS (solo para compañías que ya no están en la lista actual)."""
    s = int(sic)
    tabla = [
        ((1300, 1399), "Energy"), ((2900, 2999), "Energy"), ((100, 999), "Consumer Staples"),
        ((1000, 1499), "Materials"), ((1500, 1799), "Industrials"), ((2000, 2199), "Consumer Staples"),
        ((2200, 2399), "Consumer Discretionary"), ((2500, 2599), "Consumer Discretionary"),
        ((2400, 2699), "Materials"), ((2700, 2799), "Communication Services"), ((2830, 2836), "Health Care"),
        ((2840, 2844), "Consumer Staples"), ((2800, 2899), "Materials"), ((3000, 3399), "Materials"),
        ((3570, 3579), "Information Technology"), ((3600, 3699), "Information Technology"),
        ((3710, 3716), "Consumer Discretionary"), ((3800, 3829), "Information Technology"),
        ((3840, 3851), "Health Care"), ((3860, 3999), "Consumer Discretionary"), ((3400, 3799), "Industrials"),
        ((4800, 4899), "Communication Services"), ((4900, 4999), "Utilities"), ((4000, 4799), "Industrials"),
        ((5120, 5122), "Health Care"), ((5000, 5199), "Industrials"), ((5400, 5499), "Consumer Staples"),
        ((5910, 5912), "Consumer Staples"), ((5200, 5999), "Consumer Discretionary"), ((6798, 6798), "Real Estate"),
        ((6500, 6553), "Real Estate"), ((6000, 6799), "Financials"), ((7370, 7379), "Information Technology"),
        ((7800, 7899), "Communication Services"), ((7000, 7999), "Consumer Discretionary"),
        ((8000, 8099), "Health Care"),
    ]
    for (lo, hi), sector in tabla:
        if lo <= s <= hi:
            return sector
    return "Industrials"


def sic(cik):
    path = os.path.join(sec.DIR, f"submissions_{cik:010d}.json")
    d = sec._cached_json(path, f"https://data.sec.gov/submissions/CIK{cik:010d}.json", 365)
    return d.get("sic") or None


def main():
    h = pd.read_csv(HIST)
    h["date"] = pd.to_datetime(h.date)
    act = universo().set_index("ticker")
    m = sec.cik_map()
    filas, resumen = [], []
    for f in FECHAS:
        fila = h[h.date <= f].iloc[-1]
        miembros = fila.tickers.split(",")
        dentro = 0
        for t in miembros:
            tk = RENOMBRES.get(t, t)
            cik = m.get(tk) or m.get(tk.replace(".", "-"))
            if cik is None:
                filas.append(dict(fecha=f.date(), ticker_hist=t, ticker=None, cik=None, sector=None, fuente_sector=None))
                continue
            if tk in act.index:
                sector, fuente = act.loc[tk, "sector"], "GICS"
                subind = act.loc[tk, "subindustria"]
            else:
                code = sic(int(cik))
                sector, fuente, subind = (sic_a_gics(code) if code else "Industrials"), f"SIC {code}", None
                if code and 6000 <= int(code) <= 6199:     # bancos -> modelo EQUITY
                    subind = "Regional Banks"
                elif code and 6200 <= int(code) <= 6299:   # brokers
                    subind = "Investment Banking & Brokerage"
                elif code and 6300 <= int(code) <= 6411:   # seguros
                    subind = "Property & Casualty Insurance"
            filas.append(dict(fecha=f.date(), ticker_hist=t, ticker=tk, cik=int(cik), sector=sector,
                              subindustria=subind, fuente_sector=fuente))
            dentro += 1
        resumen.append((f.date(), len(miembros), dentro))
    df = pd.DataFrame(filas)
    df.to_csv(OUT, index=False)
    for f, n, d in resumen:
        print(f"{f}: {n} miembros, {d} con ticker vigente ({n - d} afuera)")
    print(f"-> {OUT}; tickers únicos con CIK: {df.ticker.dropna().nunique()}")
    return df


if __name__ == "__main__":
    main()
