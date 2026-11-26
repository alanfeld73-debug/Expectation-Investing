"""Lectura de la base point-in-time (data/pit/facts.parquet) y métricas por compañía.

Todas las funciones aceptan `as_of`: solo usan datos presentados (filed) hasta esa fecha, para que el
backtest no vea el futuro.

Definiciones (convenciones del modelo):
- Tasa impositiva efectiva = Σ impuesto / Σ resultado antes de impuestos, últimos 5 ejercicios.
- Tasa de inversión incremental = [Σ (capex - depreciación) + Δ capital de trabajo operativo] / Δ ventas, últimos 5
  ejercicios. Capex = PP&E + software capitalizado + inmuebles (REIT). Depreciación = D&A menos amortización de
  intangibles: como el M&A no se cuenta como inversión, tampoco se resta la amortización de lo comprado.
  Capital de trabajo operativo = (activo corriente - caja - inversiones CP) - (pasivo corriente - deuda CP).
"""
import os

import numpy as np
import pandas as pd

from pit import CAMPOS, OUT

FLOW = {"revenue", "ebit", "interest", "pretax", "tax", "net_income", "capex", "capex_sw", "capex_re", "da", "amort_intang",
        "acquisitions", "sbc", "shares_dil"}
ANNUAL_FORMS = {"10-K", "10-K/A", "10-KT", "20-F", "40-F"}
YEARS = 5
TAX_CLIP = (0.0, 0.40)
INV_CLIP = (-1.0, 2.0)
MIN_DSALES = 0.10   # Δventas mínimo (vs. ventas iniciales) para que la tasa de inversión tenga sentido

_DF = None


def facts():
    global _DF
    if _DF is None:
        _DF = pd.read_parquet(OUT)
    return _DF


def annual(campo, as_of=None, df=None):
    """Valores anuales por (ticker, cierre de ejercicio). Para flujos exige duración ~1 año; para saldos,
    el dato al cierre informado en el 10-K. Si un ejercicio tiene varios tags, gana el de mayor prioridad;
    si hay re-expresiones, la presentación más reciente (hasta as_of)."""
    d = facts() if df is None else df
    d = d[(d.campo == campo) & d.form.isin(ANNUAL_FORMS) & (d.unit.isin(["USD", "shares"]))]
    if as_of is not None:
        d = d[d.filed <= pd.Timestamp(as_of)]
    if campo in FLOW:
        dur = (d.end - d.start).dt.days
        d = d[(dur >= 350) & (dur <= 380)]
    else:
        d = d[d.start.isna()]
    if d.empty:
        return pd.DataFrame({"ticker": pd.Series(dtype=object), "end": pd.Series(dtype=d.end.dtype),
                             "val": pd.Series(dtype=float)})
    prio = {t: i for i, t in enumerate(CAMPOS.get(campo, []))}
    d = d.assign(prio=d.tag.map(prio).fillna(99))
    d = d.sort_values(["ticker", "end", "prio", "filed"], ascending=[True, True, True, False])
    return d.drop_duplicates(["ticker", "end"])[["ticker", "end", "val"]]


def _fy_ends(as_of=None):
    """Cierres de ejercicio por ticker: los de la serie de ventas (o EBIT/utilidad si no hay ventas)."""
    ends = pd.concat([annual(c, as_of) for c in ("revenue", "net_income")])
    return ends.drop_duplicates(["ticker", "end"])[["ticker", "end"]]


def tabla_anual(as_of=None):
    """Panel ancho ticker x cierre con todos los campos anuales."""
    base = _fy_ends(as_of)
    for c in CAMPOS:
        a = annual(c, as_of).rename(columns={"val": c})
        base = base.merge(a, on=["ticker", "end"], how="left")
    return base.sort_values(["ticker", "end"])


def _cerca(panel_t, fecha, tol_dias=45):
    """Fila del panel con cierre más cercano a `fecha` (±tol)."""
    dif = (panel_t.end - fecha).abs()
    if dif.empty or dif.min().days > tol_dias:
        return None
    return panel_t.loc[dif.idxmin()]


def metricas_compania(as_of=None):
    """Por ticker: tasa impositiva, tasa de inversión incremental, CAGR de ventas 3 años y ventas del último FY."""
    p = tabla_anual(as_of)
    out = []
    for t, g in p.groupby("ticker"):
        g = g.dropna(subset=["revenue"]).sort_values("end")
        if g.empty:
            out.append(dict(ticker=t))
            continue
        last = g.iloc[-1]
        win = g[g.end > last.end - pd.DateOffset(years=YEARS, days=45)]
        r = dict(ticker=t, fy_end=last.end, ventas_fy=last.revenue, ebit_fy=last.ebit, ni_fy=last.net_income,
                 acciones_fy=last.shares_dil, ebit_aprox=False)
        if pd.isna(last.ebit) and pd.notna(last.pretax):
            # Sin línea de resultado operativo: EBIT ≈ resultado antes de impuestos + intereses (SUPUESTOS.md)
            r["ebit_fy"] = last.pretax + (last.interest if pd.notna(last.interest) else 0.0)
            r["ebit_aprox"] = True
        prev = _cerca(g, last.end - pd.DateOffset(years=1))
        if prev is not None and prev.revenue > 0:
            r["g_fy"] = float(last.revenue / prev.revenue - 1)
        # Tasa impositiva
        w = win.dropna(subset=["tax", "pretax"])
        if len(w) >= 3 and w.pretax.sum() > 0:
            r["tax_rate"] = float(np.clip(w.tax.sum() / w.pretax.sum(), *TAX_CLIP))
            r["tax_n"] = len(w)
        # Tasa de inversión incremental: ventana de 5 años (o 4 o 3 si no hay historia suficiente)
        ini, k = None, YEARS
        for k in range(YEARS, 2, -1):
            ini = _cerca(g, last.end - pd.DateOffset(years=k))
            if ini is not None:
                break
        if ini is not None:
            yrs = g[(g.end > ini.end) & (g.end <= last.end)]
            ds = last.revenue - ini.revenue
            capex = yrs.capex.fillna(0) + yrs.capex_sw.fillna(0) + yrs.capex_re.fillna(0)
            capex = capex.where(yrs[["capex", "capex_sw", "capex_re"]].notna().any(axis=1))
            dep = yrs.da - yrs.amort_intang.where(yrs.amort_intang < yrs.da, 0).fillna(0)
            capex_neto = capex - dep
            nwc = lambda x: ((x.assets_cur - (0 if pd.isna(x.cash) else x.cash) - (0 if pd.isna(x.st_invest) else x.st_invest))
                             - (x.liab_cur - (0 if pd.isna(x.debt_cur) else x.debt_cur)))
            dnwc = nwc(last) - nwc(ini)
            if ds > MIN_DSALES * ini.revenue and capex_neto.notna().sum() >= k - 1:
                inv = capex_neto.sum() + (dnwc if pd.notna(dnwc) else 0.0)
                r["inv_rate"] = float(np.clip(inv / ds, *INV_CLIP))
                r["inv_sin_nwc"] = bool(pd.isna(dnwc))
            r["inv_anios"] = k
            r["ma_5a"] = float(yrs.acquisitions.sum()) if yrs.acquisitions.notna().any() else 0.0
            r["dventas_5a"] = float(ds)
        # CAGR de ventas 3 años (crecimiento previo para base rates)
        i3 = _cerca(g, last.end - pd.DateOffset(years=3))
        if i3 is not None and i3.revenue > 0 and last.revenue > 0:
            r["cagr3"] = float((last.revenue / i3.revenue) ** (1 / 3) - 1)
        out.append(r)
    return pd.DataFrame(out)


def ultimo_saldo(campo, as_of, con_fecha=False):
    """Último saldo (dato instantáneo) por ticker presentado hasta as_of, de 10-K o 10-Q. Si hay varios tags
    para la misma fecha de cierre, gana el de mayor prioridad. Devuelve Serie ticker -> valor."""
    d = facts()
    d = d[(d.campo == campo) & d.start.isna() & (d.filed <= pd.Timestamp(as_of))
          & d.form.isin(ANNUAL_FORMS | {"10-Q", "10-Q/A"})]
    if d.empty:
        return pd.DataFrame(columns=["val", "end"]) if con_fecha else pd.Series(dtype=float)
    prio = {t: i for i, t in enumerate(CAMPOS.get(campo, ["EntityCommonStockSharesOutstanding"]))}
    d = d.assign(prio=d.tag.map(prio).fillna(99))
    d = d.sort_values(["ticker", "end", "prio", "filed"], ascending=[True, False, True, False])
    d = d.drop_duplicates("ticker").set_index("ticker")
    return d[["val", "end"]] if con_fecha else d.val
