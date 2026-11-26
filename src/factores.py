"""Regresión de factores Fama-French para el backtest: ¿el retorno del quintil 1 se explica solo por value?

Factores: Fama-French 5 (mercado, tamaño SMB, value HML, rentabilidad RMW, inversión CMA) + momentum (UMD),
mensuales, de la biblioteca de Kenneth French (mba.tuck.dartmouth.edu), cacheados en data/factores/.

alfa(retornos) regresa el exceso de retorno mensual de una cartera contra los factores con errores estándar
Newey-West (corrigen autocorrelación por carteras superpuestas de 3-5 años). Criterio de la Semana 3:
alfa > 0 y significativo con HML en la regresión = el método aporta más que value.
"""
import io
import os
import urllib.request
import zipfile

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "data", "factores")
BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
ARCHIVOS = {"ff5": "F-F_Research_Data_5_Factors_2x3_CSV.zip", "mom": "F-F_Momentum_Factor_CSV.zip"}


def _bajar(nombre):
    os.makedirs(DIR, exist_ok=True)
    path = os.path.join(DIR, ARCHIVOS[nombre])
    if not (os.path.exists(path) and os.path.getsize(path) > 0):
        body = urllib.request.urlopen(BASE + ARCHIVOS[nombre], timeout=60).read()
        with open(path + ".tmp", "wb") as f:
            f.write(body)
        os.replace(path + ".tmp", path)
    with zipfile.ZipFile(path) as z:
        return z.read(z.namelist()[0]).decode("latin-1")


def _parse_mensual(texto):
    """Toma el primer bloque de filas AAAAMM del CSV de French (el mensual) y lo pasa a decimales."""
    lineas = texto.splitlines()
    ini = next(i for i, l in enumerate(lineas) if l.strip().startswith(",")) if any(
        l.strip().startswith(",") for l in lineas) else 0
    hdr = [h.strip() for h in lineas[ini].split(",")]
    filas = []
    for l in lineas[ini + 1:]:
        p = [x.strip() for x in l.split(",")]
        if len(p[0]) != 6 or not p[0].isdigit():
            break
        filas.append(p)
    df = pd.DataFrame(filas, columns=["mes"] + hdr[1:]).set_index("mes").astype(float) / 100
    df.index = pd.PeriodIndex(df.index.str[:4] + "-" + df.index.str[4:], freq="M")
    return df


def factores():
    """DataFrame mensual con Mkt-RF, SMB, HML, RMW, CMA, RF y UMD (decimales)."""
    ff5 = _parse_mensual(_bajar("ff5"))
    mom = _parse_mensual(_bajar("mom"))
    mom.columns = ["UMD"]
    return ff5.join(mom, how="inner")


def newey_west(X, e, lags):
    n = X.shape[0]
    Xe = X * e[:, None]
    S = Xe.T @ Xe
    for l in range(1, lags + 1):
        w = 1 - l / (lags + 1)
        G = Xe[l:].T @ Xe[:-l]
        S += w * (G + G.T)
    XtX_inv = np.linalg.inv(X.T @ X)
    return XtX_inv @ S @ XtX_inv


def alfa(exceso, F, cols=("Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD"), lags=None):
    """exceso: Serie mensual (PeriodIndex) de retorno de la cartera menos RF (o menos SPY para retorno activo).
    Devuelve DataFrame con coeficiente, error estándar Newey-West y t por factor; 'alfa' es mensual."""
    d = pd.concat([exceso.rename("y"), F[list(cols)]], axis=1, join="inner").dropna()
    y = d.y.to_numpy()
    X = np.column_stack([np.ones(len(d)), d[list(cols)].to_numpy()])
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    lags = lags if lags is not None else int(np.floor(4 * (len(d) / 100) ** (2 / 9)))
    se = np.sqrt(np.diag(newey_west(X, e, lags)))
    out = pd.DataFrame({"coef": b, "se": se, "t": b / se}, index=["alfa"] + list(cols))
    out.attrs.update(n=len(d), lags=lags, r2=1 - e.var() / y.var())
    return out
