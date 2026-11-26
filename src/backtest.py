"""Backtest v1 (PREREGISTRO.md): carteras anuales por quintil de brecha contra SPY y el promedio del universo.

Uso: python backtest.py  -> data/backtest/*.csv y data/backtest/resultado.json

- Cada fin de abril se arma la cartera con pesos iguales y se mantiene 12 meses (los pesos derivan con los precios).
- Retornos totales mensuales con adjclose de Yahoo (dividendos reinvertidos). Si una acción deja de tener precio
  durante el año, esa parte queda en efectivo (retorno 0) hasta el rebalanceo.
- Costos: 20 pb por lado sobre el volumen operado en cada rebalanceo (Σ|peso nuevo - peso derivado| x 0,2%).
- Criterio: (1) Q1 > SPY después de costos en la mayoría de los años calendario completos; (2a) alfa > 0 con
  t >= 2 contra Fama-French 5 + momentum; (2b) en el doble orden, Q1 > Q5 en promedio y en >= 3 de 5 niveles de
  múltiplo.
"""
import json
import os

import numpy as np
import pandas as pd

import factores as FF
from pit import ROOT

DIR = os.path.join(ROOT, "data", "backtest")
COSTO = 0.002


def retornos_mensuales(px):
    adj = px.pivot(index="mes", columns="ticker", values="adjclose").sort_index()
    return adj.pct_change(fill_method=None)


def cartera(R, fechas_tickers, nombre):
    """fechas_tickers: lista de (mes de armado, [tickers]). Devuelve Serie de retornos mensuales netos de costos."""
    out = {}
    w_prev = pd.Series(dtype=float)
    for i, (m0, tks) in enumerate(fechas_tickers):
        m1 = fechas_tickers[i + 1][0] if i + 1 < len(fechas_tickers) else R.index.max()
        meses = R.index[(R.index > m0) & (R.index <= m1)]
        tks = list(dict.fromkeys(t for t in tks if t in R.columns))
        if not tks or len(meses) == 0:
            continue
        w = pd.Series(1 / len(tks), index=tks)
        todos = w.index.union(w_prev.index)
        costo = COSTO * (w.reindex(todos, fill_value=0) - w_prev.reindex(todos, fill_value=0)).abs().sum()
        v = w.copy()
        for j, mes in enumerate(meses):
            r = R.loc[mes, tks].fillna(0.0)
            rp = float((v * r).sum() / v.sum())
            if j == 0:
                rp = (1 - costo) * (1 + rp) - 1
            out[mes] = rp
            v = v * (1 + r)
        w_prev = v / v.sum()
    return pd.Series(out, name=nombre).sort_index()


def anual(s):
    return (1 + s).groupby(s.index.year).prod() - 1


def stats(s, rf):
    n = len(s)
    cagr = (1 + s).prod() ** (12 / n) - 1
    vol = s.std() * np.sqrt(12)
    curva = (1 + s).cumprod()
    dd = (curva / curva.cummax() - 1).min()
    ex = s - rf.reindex(s.index).fillna(0)
    return dict(cagr=cagr, vol=vol, sharpe=ex.mean() / s.std() * np.sqrt(12), max_dd=dd, meses=n)


def main():
    b = pd.read_parquet(os.path.join(DIR, "brechas.parquet"))
    px = pd.read_parquet(os.path.join(ROOT, "data", "precios", "mensual.parquet"))
    R = retornos_mensuales(px)
    fechas = sorted(b.fecha.unique())
    meses = [pd.Timestamp(f).to_period("M") for f in fechas]
    rk = b[b.quintil.notna()]

    def armar(filtro):
        return [(m, list(rk[(rk.fecha == f) & filtro(rk[rk.fecha == f])].ticker)) for f, m in zip(fechas, meses)]

    carteras = {}
    for q in range(1, 6):
        carteras[f"Q{q}"] = cartera(R, armar(lambda d, q=q: d.quintil == q), f"Q{q}")
    carteras["Universo (pesos iguales)"] = cartera(R, armar(lambda d: d.quintil.notna()), "Universo")
    for col, nom in (("quintil_4", "Q1 brecha 4%"), ("quintil_pbr", "Q1 P(base rate)"), ("quintil_sector", "Q1 neutral sector")):
        carteras[nom] = cartera(R, armar(lambda d, col=col: d[col] == 1), nom)
    for k in range(1, 6):
        for q in (1, 5):
            carteras[f"EY{k}-Q{q}"] = cartera(R, armar(lambda d, k=k, q=q: (d.quintil_ey == k) & (d.quintil_dentro_ey == q)), f"EY{k}-Q{q}")
    inicio = carteras["Q1"].index.min()
    carteras["SPY"] = R["SPY"].loc[R.index >= inicio].rename("SPY")
    M = pd.DataFrame(carteras).dropna(subset=["Q1", "SPY"])
    M.to_csv(os.path.join(DIR, "mensual.csv"))

    F = FF.factores()
    rf = F["RF"]
    A = M.apply(anual)
    ultimo = M.index.max()
    completos = [y for y in A.index if (M.index.year == y).sum() == 12]
    A["completo"] = A.index.isin(completos)
    A.to_csv(os.path.join(DIR, "anual.csv"))

    # Criterio 1
    gana = (A.loc[completos, "Q1"] > A.loc[completos, "SPY"])
    c1 = dict(anios=len(completos), gana=int(gana.sum()), cumple=bool(gana.sum() > len(completos) / 2),
              gana_universo=int((A.loc[completos, "Q1"] > A.loc[completos, "Universo (pesos iguales)"]).sum()))
    # Criterio 2a
    reg = FF.alfa(M["Q1"] - rf.reindex(M.index), F)
    reg_univ = FF.alfa(M["Universo (pesos iguales)"] - rf.reindex(M.index), F)
    c2a = dict(alfa_mensual=float(reg.loc["alfa", "coef"]), t=float(reg.loc["alfa", "t"]),
               alfa_anual=float((1 + reg.loc["alfa", "coef"]) ** 12 - 1), hml=float(reg.loc["HML", "coef"]),
               t_hml=float(reg.loc["HML", "t"]), n=reg.attrs["n"], r2=reg.attrs["r2"],
               cumple=bool(reg.loc["alfa", "coef"] > 0 and reg.loc["alfa", "t"] >= 2))
    # Criterio 2b
    spreads = {k: float(((1 + M[f"EY{k}-Q1"]).prod() ** (12 / len(M)) - 1) - ((1 + M[f"EY{k}-Q5"]).prod() ** (12 / len(M)) - 1))
               for k in range(1, 6)}
    pos = sum(v > 0 for v in spreads.values())
    c2b = dict(spreads=spreads, positivos=pos, promedio=float(np.mean(list(spreads.values()))),
               cumple=bool(pos >= 3 and np.mean(list(spreads.values())) > 0))
    st = {c: stats(M[c], rf) for c in M.columns}
    # Exclusiones por año (sesgo de supervivencia)
    u = pd.read_csv(os.path.join(ROOT, "data", "universo", "universo_bt.csv"))
    excl = u.groupby("fecha").apply(lambda d: dict(miembros=len(d), afuera=int(d.ticker.isna().sum()))).to_dict()
    res = dict(desde=str(M.index.min()), hasta=str(ultimo), criterio1=c1, criterio2a=c2a, criterio2b=c2b,
               aprobado=bool(c1["cumple"] and c2a["cumple"] and c2b["cumple"]), stats=st,
               regresion=reg.round(5).to_dict(), regresion_universo=reg_univ.round(5).to_dict(), exclusiones=excl,
               n_q1={str(pd.Timestamp(k).date()): int(v) for k, v in rk[rk.quintil == 1].groupby("fecha").size().items()})
    with open(os.path.join(DIR, "resultado.json"), "w") as f:
        json.dump(res, f, indent=1, default=str)
    pd.set_option("display.width", 200)
    print(A[["Q1", "Q2", "Q3", "Q4", "Q5", "Universo (pesos iguales)", "SPY", "completo"]].round(3).to_string())
    print(json.dumps({k: res[k] for k in ("criterio1", "criterio2a", "criterio2b", "aprobado")}, indent=1, default=str))
    return res


if __name__ == "__main__":
    main()
