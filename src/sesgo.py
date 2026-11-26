"""Rankings y diagnósticos de sesgo value (pre-registrados en SUPUESTOS.md, 2026-11-26).

Variantes de ranking (quintil 1 = más atractivo):
  quintil         principal: brecha con desaceleración hacia el base rate.
  quintil_4       brecha con desaceleración a 4% fijo (versión anterior).
  quintil_pbr     P(base rate) del g implícito: alta = el precio pide poco contra la historia (solo FCF).
  quintil_sector  brecha principal, quintiles dentro de cada sector (neutral por sector).
  quintil_ey      rendimiento operativo (NOPAT/EV o utilidad/market cap): es el factor value puro.
  quintil_dentro_ey  brecha principal, quintiles dentro de cada quintil de rendimiento (doble orden):
                  si el Q1 le gana al Q5 dentro del mismo nivel de múltiplo, el método aporta más que value.
"""
import numpy as np
import pandas as pd


def quintil(s, ascending=False):
    """1 = mayor valor (o menor si ascending). NaN se mantiene."""
    r = s.rank(method="first", ascending=ascending, pct=True)
    return np.ceil(r * 5).clip(1, 5)


def por_grupo(df, col, grupo, ascending=False):
    return df.groupby(grupo, group_keys=False)[col].apply(lambda s: quintil(s, ascending))


def rankings(df, ok):
    d = df.loc[ok].copy()
    d["quintil"] = quintil(d.brecha)
    d["quintil_4"] = quintil(d.brecha_4)
    d["quintil_pbr"] = quintil(d.p_base_rate)
    d["quintil_sector"] = por_grupo(d, "brecha", "sector")
    d["quintil_ey"] = quintil(d.ey)
    d["quintil_dentro_ey"] = por_grupo(d, "brecha", "quintil_ey")
    for c in ("quintil", "quintil_4", "quintil_pbr", "quintil_sector", "quintil_ey", "quintil_dentro_ey"):
        df.loc[ok, c] = d[c]
    return df


def diagnostico(df):
    """Correlación de rangos (Spearman) de cada métrica con el rendimiento operativo y composición del Q1
    por quintil de rendimiento. Correlación cerca de 1 = la métrica es básicamente value."""
    d = df[df.quintil.notna()]
    filas = []
    for nombre, col, q in (("Brecha (base rate) — principal", "brecha", "quintil"),
                           ("Brecha (4% fijo)", "brecha_4", "quintil_4"),
                           ("P(base rate)", "p_base_rate", "quintil_pbr"),
                           ("Brecha neutral por sector", None, "quintil_sector"),
                           ("Brecha dentro de cada nivel de múltiplo", None, "quintil_dentro_ey")):
        x = d[col] if col else -d[q]
        rho = x.rank().corr(d.ey.rank())
        q1 = d[d[q] == 1]
        comp = q1.quintil_ey.value_counts(normalize=True).reindex([1, 2, 3, 4, 5]).fillna(0)
        filas.append(dict(variante=nombre, rho_rendimiento=rho, n_q1=len(q1),
                          **{f"q1_en_ey{k}": comp[k] for k in range(1, 6)}))
    return pd.DataFrame(filas)
