"""Defaults por sector GICS: tasa impositiva y tasa de inversión incremental (medianas de la SEC).

Uso: python defaults_sector.py  -> data/defaults_compania.csv, data/defaults_sector.csv

El default de cada sector es la mediana de las compañías del S&P 500 con dato válido (últimos 5 ejercicios).
Se usa la mediana y no el promedio para que no la muevan los extremos (p.ej. Δventas chico).
Si un sector tiene menos de MIN_N compañías válidas, se usa la mediana de todo el índice.
"""
import os

import pandas as pd

import fundamentals as F
from pit import ROOT, universo

MIN_N = 8
SALIDA_CO = os.path.join(ROOT, "data", "defaults_compania.csv")
SALIDA_SEC = os.path.join(ROOT, "data", "defaults_sector.csv")


def calcular(as_of=None):
    u = universo()
    m = F.metricas_compania(as_of)
    co = u.merge(m, on="ticker", how="left")
    filas = []
    glob_tax, glob_inv = co.tax_rate.median(), co.inv_rate.median()
    for s, g in co.groupby("sector"):
        t, i = g.tax_rate.dropna(), g.inv_rate.dropna()
        filas.append(dict(
            sector=s, n=len(g),
            tax_default=t.median() if len(t) >= MIN_N else glob_tax, tax_n=len(t),
            tax_p25=t.quantile(0.25), tax_p75=t.quantile(0.75),
            inv_default=i.median() if len(i) >= MIN_N else glob_inv, inv_n=len(i),
            inv_p25=i.quantile(0.25), inv_p75=i.quantile(0.75)))
    sec = pd.DataFrame(filas)
    return co, sec


def main():
    co, sec = calcular()
    co.to_csv(SALIDA_CO, index=False)
    sec.to_csv(SALIDA_SEC, index=False)
    pd.set_option("display.width", 200)
    print(sec.round(3).to_string(index=False))
    return co, sec


if __name__ == "__main__":
    main()
