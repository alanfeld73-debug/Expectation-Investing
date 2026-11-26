"""Análisis EXPLORATORIO (posterior a ver resultados, no pre-registrado): ¿concentrar en el top N de brecha ayuda?

Uso: python concentracion.py  -> data/backtest/concentracion.json

Top N = las N compañías de mayor brecha entre las rankeadas (sin marcas [revisar]) en cada rebalanceo, pesos iguales,
mismas reglas que el backtest (fin de abril, 12 meses, 20 pb por lado). Control: carteras de N acciones elegidas al
azar dentro del Q1 de cada año (mismo universo, mismo tamaño); el percentil del top N dentro de esa distribución dice
si ordenar por brecha dentro del Q1 agrega algo o si la diferencia es ruido de concentración.
"""
import json
import os

import numpy as np
import pandas as pd

import backtest as B
import factores as FF
from pit import ROOT

NS = (15, 20, 25)
N_AZAR = 300
SEMILLA = 7


def main():
    b = pd.read_parquet(os.path.join(B.DIR, "brechas.parquet"))
    px = pd.read_parquet(os.path.join(ROOT, "data", "precios", "mensual.parquet"))
    R = B.retornos_mensuales(px)
    rk = b[b.quintil.notna()]
    fechas = sorted(rk.fecha.unique())
    meses = [pd.Timestamp(f).to_period("M") for f in fechas]
    M = pd.read_csv(os.path.join(B.DIR, "mensual.csv"), index_col=0)
    M.index = pd.PeriodIndex(M.index, freq="M")
    F = FF.factores()
    rf = F["RF"]
    cg = lambda s: (1 + s).prod() ** (12 / len(s)) - 1
    q1_por_fecha = {f: rk[(rk.fecha == f) & (rk.quintil == 1)].sort_values("brecha", ascending=False).ticker.tolist()
                    for f in fechas}
    rng = np.random.default_rng(SEMILLA)
    out = {}
    corte = pd.Period("2016-04", "M")
    for n in NS:
        ft = [(m, q1_por_fecha[f][:n]) for f, m in zip(fechas, meses)]
        s = B.cartera(R, ft, f"Top {n}").reindex(M.index)
        A = pd.concat([s, M[["Q1", "SPY", "RSP"]]], axis=1).apply(B.anual)
        comp = [y for y in A.index if (M.index.year == y).sum() == 12]
        reg = FF.alfa(s - rf.reindex(s.index), F)
        reg_rsp = FF.alfa(s - M["RSP"], F)
        azar = []
        for _ in range(N_AZAR):
            fa = [(m, list(rng.choice(q1_por_fecha[f], size=min(n, len(q1_por_fecha[f])), replace=False)))
                  for f, m in zip(fechas, meses)]
            azar.append(cg(B.cartera(R, fa, "azar").reindex(M.index).fillna(0)))
        azar = np.array(azar)
        st = B.stats(s, rf)
        out[n] = dict(
            cagr=cg(s), cagr_oos=cg(s[s.index <= corte]), cagr_v1=cg(s[s.index > corte]),
            vol=st["vol"], sharpe=st["sharpe"], max_dd=st["max_dd"],
            gana_spy=int((A.loc[comp, f"Top {n}"] > A.loc[comp, "SPY"]).sum()),
            gana_rsp=int((A.loc[comp, f"Top {n}"] > A.loc[comp, "RSP"]).sum()),
            gana_q1=int((A.loc[comp, f"Top {n}"] > A.loc[comp, "Q1"]).sum()), anios=len(comp),
            alfa=float(reg.loc["alfa", "coef"] * 12), t=float(reg.loc["alfa", "t"]), hml=float(reg.loc["HML", "coef"]),
            alfa_rsp=float(reg_rsp.loc["alfa", "coef"] * 12), t_rsp=float(reg_rsp.loc["alfa", "t"]),
            azar_mediana=float(np.median(azar)), azar_p10=float(np.percentile(azar, 10)),
            azar_p90=float(np.percentile(azar, 90)), percentil_vs_azar=float((azar < cg(s)).mean()),
            anual={int(y): float(A.loc[y, f"Top {n}"]) for y in A.index})
        print(f"Top {n}: {out[n]['cagr']:.1%} anual (2010-16 {out[n]['cagr_oos']:.1%}, 2016-26 {out[n]['cagr_v1']:.1%}) | "
              f"vol {st['vol']:.1%} | peor caída {st['max_dd']:.0%} | > SPY {out[n]['gana_spy']}/{len(comp)}, "
              f"> RSP {out[n]['gana_rsp']}/{len(comp)}, > Q1 {out[n]['gana_q1']}/{len(comp)} | alfa {out[n]['alfa']:.1%} "
              f"(t {out[n]['t']:.2f}) | vs RSP {out[n]['alfa_rsp']:.1%} (t {out[n]['t_rsp']:.2f}) | "
              f"azar p10-mediana-p90 {out[n]['azar_p10']:.1%} / {out[n]['azar_mediana']:.1%} / {out[n]['azar_p90']:.1%} "
              f"-> percentil {out[n]['percentil_vs_azar']:.0%}")
    ref = {c: dict(cagr=cg(M[c]), cagr_oos=cg(M[c][M.index <= corte]), cagr_v1=cg(M[c][M.index > corte]),
                   **{k: v for k, v in B.stats(M[c], rf).items() if k in ("vol", "sharpe", "max_dd")})
           for c in ("Q1", "SPY", "RSP")}
    for c, v in ref.items():
        print(f"{c}: {v['cagr']:.1%} anual (2010-16 {v['cagr_oos']:.1%}, 2016-26 {v['cagr_v1']:.1%}) | vol {v['vol']:.1%} | peor caída {v['max_dd']:.0%}")
    with open(os.path.join(B.DIR, "concentracion.json"), "w") as f:
        json.dump(dict(top=out, ref=ref, n_azar=N_AZAR), f, indent=1)
    return out


if __name__ == "__main__":
    main()
