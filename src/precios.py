"""Precios mensuales de Yahoo Finance (chart API), con caché en data/precios/.

Uso: python precios.py  -> data/precios/mensual.parquet (tickers del universo del backtest + SPY)

Por ticker y mes (último día hábil): close (ajustado por splits, no por dividendos), adjclose (splits y
dividendos: sirve para retornos totales) y factor_split (cuántas acciones de hoy equivalen a una de ese mes:
para pasar el close a precio nominal de la época y calcular el market cap con las acciones de ese momento).
"""
import json
import os
import time
import urllib.request

import pandas as pd

from pit import ROOT

DIR = os.path.join(ROOT, "data", "precios")
OUT = os.path.join(DIR, "mensual.parquet")
DESDE = 1262304000   # 2010-01-01


def yahoo_symbol(t):
    return t.replace(".", "-")


def bajar(t):
    path = os.path.join(DIR, "raw", f"{t}.json")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return json.load(open(path))
    url = (f"https://query2.finance.yahoo.com/v8/finance/chart/{yahoo_symbol(t)}?period1={DESDE}"
           f"&period2={int(time.time())}&interval=1mo&events=div,split")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for intento in range(3):
        try:
            body = urllib.request.urlopen(req, timeout=30).read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 * (intento + 1))
        except Exception:
            time.sleep(2 * (intento + 1))
    else:
        return None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(body)
    time.sleep(0.15)
    return json.loads(body)


def a_tabla(t, d):
    try:
        r = d["chart"]["result"][0]
    except (KeyError, IndexError, TypeError):
        return None
    if not r.get("timestamp"):
        return None
    idx = pd.to_datetime(r["timestamp"], unit="s").to_period("M")
    df = pd.DataFrame({"close": r["indicators"]["quote"][0]["close"],
                       "adjclose": r["indicators"]["adjclose"][0]["adjclose"]}, index=idx)
    df = df[~df.index.duplicated(keep="last")].dropna()
    # Factor de split: producto de los splits posteriores a cada mes
    splits = r.get("events", {}).get("splits", {})
    df["factor_split"] = 1.0
    for s in splits.values():
        mes = pd.Timestamp(s["date"], unit="s").to_period("M")
        df.loc[df.index < mes, "factor_split"] *= s["numerator"] / s["denominator"]
    df["ticker"] = t
    return df.reset_index(names="mes")


def main():
    u = pd.read_csv(os.path.join(ROOT, "data", "universo", "universo_bt.csv"))
    tickers = sorted(set(u.ticker.dropna())) + ["SPY"]
    partes, faltan = [], []
    for i, t in enumerate(tickers, 1):
        tabla = a_tabla(t, bajar(t)) if bajar(t) else None
        if tabla is None or tabla.empty:
            faltan.append(t)
        else:
            partes.append(tabla)
        if i % 100 == 0:
            print(f"[precios] {i}/{len(tickers)}", flush=True)
    df = pd.concat(partes)
    df.to_parquet(OUT, index=False)
    print(f"[precios] {df.ticker.nunique()} tickers, {len(df):,} filas -> {OUT}")
    print(f"[precios] sin datos ({len(faltan)}): {faltan}")
    return df


if __name__ == "__main__":
    main()
