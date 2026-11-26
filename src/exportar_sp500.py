"""Excel de la corrida cruda del S&P 500 (Semana 1).

Uso: python exportar_sp500.py  -> resultados/screen_sp500_AAAA-MM-DD.xlsx

Hojas: Resumen, Screen S&P 500 (colores por recomendación), Defaults sector (para revisar),
Por compañía (tasas calculadas de cada una) y Criterios (umbrales editables).
"""
import datetime as dt
import os

import pandas as pd
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import screen_sp500 as SP
from exportar_excel import BLUE, BOLD, COLORS, FONT, THIN, YELLOW, _style_header, hoja_criterios
from pit import ROOT

F = Font(name=FONT)


def _tabla(ws, df, cols, fila0=1, freeze=True):
    """cols: lista de (columna df, encabezado, ancho, formato). Devuelve la última fila."""
    for j, (_, h, w, _) in enumerate(cols, 1):
        ws.cell(row=fila0, column=j, value=h)
        ws.column_dimensions[get_column_letter(j)].width = w
    _style_header(ws, fila0, len(cols))
    for i, rec in enumerate(df.to_dict("records"), start=fila0 + 1):
        for j, (k, _, _, fmt) in enumerate(cols, 1):
            if k is None:
                continue
            v = rec.get(k)
            if isinstance(v, float) and (pd.isna(v) or v in (float("inf"), float("-inf"))):
                v = ">40" if k == "mifp" and v == float("inf") else None
            c = ws.cell(row=i, column=j, value=v)
            c.font, c.border = F, THIN
            if fmt:
                c.number_format = fmt
    last = fila0 + len(df)
    if freeze:
        ws.freeze_panes = ws.cell(row=fila0 + 1, column=3)
    ws.auto_filter.ref = f"A{fila0}:{get_column_letter(len(cols))}{last}"
    return last


def hoja_screen(wb, df):
    ws = wb.active
    ws.title = "Screen S&P 500"
    cols = [("ticker", "Ticker", 8, None), ("nombre", "Compañía", 26, None), ("sector", "Sector", 20, None),
            ("modelo", "Modelo", 9, None), ("precio", "Precio", 10, "#,##0.00"), ("mcap_bn", "Mkt cap (USD bn)", 10, "#,##0.0"),
            ("margen_ebit", "Margen EBIT TTM", 9, "0.0%"), ("roe", "ROE TTM", 8, "0.0%"),
            ("tasa_imp", "Tasa imp. (default)", 9, "0.0%"), ("tasa_inv", "Tasa inv. (default)", 9, "0%"),
            ("wacc", "WACC / Ke", 8, "0.0%"), ("ss_share", "Valor sin crec. / EV", 9, "0%"),
            ("g_impl", "g implícito (10a)", 9, "0.0%"), ("g_hist3", "CAGR ventas 3a (SEC)", 9, "0.0%"),
            ("p_base_rate", "P(base rate)", 8, "0%"), ("g_ref", "g consenso año 1", 9, "0.0%"),
            ("mifp", "MIFP (años)", 8, "0.0"), ("v_fade", "Valor (consenso + fade)", 11, "#,##0.00"),
            ("brecha", "Brecha (upside)", 9, "0%"), ("quintil", "Quintil", 7, "0"),
            (None, "Recomendación", 15, None), ("nota", "Nota", 60, None)]
    last = _tabla(ws, df, cols)
    rec_col, nota_col = 21, 22
    for i in range(2, last + 1):
        ws.cell(row=i, column=rec_col, value=(
            f'=IF(S{i}="","SIN DATO",IF(OR(L{i}>Criterios!$B$6,ISNUMBER(SEARCH("conciliar",V{i})),'
            f'ISNUMBER(SEARCH("EBIT ≤ 0",V{i}))),"REVISAR DATOS",'
            f'IF(S{i}>=Criterios!$B$4,"COMPRA",IF(S{i}<=Criterios!$B$5,"VENTA","MANTENER"))))'))
        c = ws.cell(row=i, column=rec_col)
        c.font, c.border, c.alignment = F, THIN, Alignment(horizontal="center")
    colors = dict(COLORS, **{"SIN DATO": ("FFFFFF", "808080")})
    for txt, (fill, font) in colors.items():
        ws.conditional_formatting.add(f"A2:U{last}", FormulaRule(
            formula=[f'$U2="{txt}"'], fill=PatternFill("solid", fgColor=fill), font=Font(name=FONT, color=font)))
    ws.cell(row=1, column=9).comment = Comment("Default del sector (mediana SEC, últimos 5 años). Ver hoja Defaults sector.", "screen")
    ws.cell(row=1, column=19).comment = Comment("Valor con consenso año 1 + fade lineal a 4% en el año 10, sobre precio - 1.", "screen")
    return last


def hoja_resumen(wb, df, last_screen):
    ws = wb.create_sheet("Resumen", 0)
    ws["A1"] = f"Semana 1 — corrida cruda del S&P 500 ({dt.date.today():%d-%m-%Y})"
    ws["A1"].font = Font(name=FONT, bold=True, size=13)
    notas = [
        "Corrida CRUDA: defaults por sector, sin normalizar ítems no recurrentes, M&A ni guías ajustadas.",
        "Sirve para ordenar el universo y elegir los 40-60 candidatos de la Semana 2, no para decidir compras.",
        f"Rf = {df.rf.iloc[0]:.2%} (FRED DGS10 al {df.rf_fecha.iloc[0]}). ERP 5%. Beta 5 años acotada 0,8-1,8.",
        "Recomendación: umbrales en la hoja Criterios. REVISAR DATOS = EBIT ≤ 0, ventas TV vs SEC no concilian o valor sin crecimiento > 150% del EV.",
    ]
    for i, n in enumerate(notas, 3):
        ws.cell(row=i, column=1, value=n).font = F
    S = "'Screen S&P 500'"
    ws["A8"], ws["B8"] = "Recomendación", "Compañías"
    _style_header(ws, 8, 2)
    for i, txt in enumerate(["COMPRA", "MANTENER", "VENTA", "REVISAR DATOS", "SIN DATO"], 9):
        ws.cell(row=i, column=1, value=txt).font = BOLD
        ws.cell(row=i, column=2, value=f'=COUNTIF({S}!$U$2:$U${last_screen},A{i})').font = F
        fill, font = dict(COLORS, **{"SIN DATO": ("FFFFFF", "808080")})[txt]
        ws.cell(row=i, column=1).fill = PatternFill("solid", fgColor=fill)
    ws["A15"], ws["B15"] = "Total", "=SUM(B9:B13)"
    ws["A15"].font = ws["B15"].font = BOLD
    ws["D8"], ws["E8"], ws["F8"], ws["G8"] = "Quintil de brecha", "Compañías", "Brecha mediana", "g implícito mediano"
    _style_header(ws, 8, 7)
    for c in ("A", "B", "C"):
        pass
    for i, q in enumerate(range(1, 6), 9):
        sub = df[df.quintil == q]
        ws.cell(row=i, column=4, value=q).font = BOLD
        ws.cell(row=i, column=5, value=f'=COUNTIF({S}!$T$2:$T${last_screen},D{i})').font = F
        c = ws.cell(row=i, column=6, value=float(sub.brecha.median()) if len(sub) else None)
        c.number_format, c.font = "0%", F
        c = ws.cell(row=i, column=7, value=float(sub.g_impl.median()) if sub.g_impl.notna().any() else None)
        c.number_format, c.font = "0.0%", F
    ws["D15"] = "Quintil 1 = mayor brecha (más barato vs. consenso). Es el que testea el backtest de la Semana 2."
    ws["D15"].font = Font(name=FONT, italic=True)
    # Por sector
    ws["A18"] = "Por sector"
    ws["A18"].font = BOLD
    hdr = ["Sector", "Compañías", "En quintil 1", "Brecha mediana", "Tasa imp. default", "Tasa inv. default"]
    for j, h in enumerate(hdr, 1):
        ws.cell(row=19, column=j, value=h)
    _style_header(ws, 19, len(hdr))
    for i, (s, g) in enumerate(df.groupby("sector"), 20):
        ws.cell(row=i, column=1, value=s).font = F
        ws.cell(row=i, column=2, value=f'=COUNTIF({S}!$C$2:$C${last_screen},A{i})').font = F
        ws.cell(row=i, column=3, value=f'=COUNTIFS({S}!$C$2:$C${last_screen},A{i},{S}!$T$2:$T${last_screen},1)').font = F
        c = ws.cell(row=i, column=4, value=float(g.brecha.median()) if g.brecha.notna().any() else None)
        c.number_format, c.font = "0%", F
        for j, k, fmt in ((5, "C", "0.0%"), (6, "D", "0%")):
            c = ws.cell(row=i, column=j, value=f"=INDEX('Defaults sector'!${k}:${k},MATCH(A{i},'Defaults sector'!$A:$A,0))")
            c.number_format, c.font = fmt, Font(name=FONT, color="008000")
    ws.column_dimensions["A"].width = 26
    for col in "BCDEFG":
        ws.column_dimensions[col].width = 15
    ws.column_dimensions["D"].width = 18


def hoja_defaults(wb, sec):
    ws = wb.create_sheet("Defaults sector")
    cols = [("sector", "Sector", 26, None), ("n", "Compañías", 10, "0"),
            ("tax_default", "Tasa imp. default", 12, "0.0%"), ("inv_default", "Tasa inv. default", 12, "0%"),
            ("tax_n", "n válidas (imp.)", 10, "0"), ("tax_p25", "Imp. p25", 9, "0.0%"), ("tax_p75", "Imp. p75", 9, "0.0%"),
            ("inv_n", "n válidas (inv.)", 10, "0"), ("inv_p25", "Inv. p25", 9, "0%"), ("inv_p75", "Inv. p75", 9, "0%")]
    last = _tabla(ws, sec, cols, freeze=False)
    for i in range(2, last + 1):
        for j in (3, 4):
            c = ws.cell(row=i, column=j)
            c.font, c.fill = BLUE, YELLOW
    r = last + 2
    txt = [
        "Celdas amarillas = defaults a revisar. Hoy son medianas de la SEC; para cambiarlos en la corrida, editar",
        "src/defaults_sector.py (overrides) y volver a correr. Editarlos acá no cambia el screen (los valores vienen de Python).",
        "Tasa impositiva = Σ impuesto / Σ resultado antes de impuestos, últimos 5 ejercicios, acotada 0-40%.",
        "Tasa de inversión = [Σ (capex - D&A) + Δ capital de trabajo operativo] / Δ ventas, 5 ejercicios, acotada -100% a 200%. Sin M&A.",
        "Financials: el modelo EQUITY no usa la tasa de inversión (usa ROE). Real Estate: los REIT casi no pagan impuesto.",
    ]
    for k, t in enumerate(txt):
        ws.cell(row=r + k, column=1, value=t).font = Font(name=FONT, italic=True)


def hoja_companias(wb, co):
    ws = wb.create_sheet("Por compañía")
    co = co.copy()
    co["ma_sobre_dventas"] = co.ma_5a / co.dventas_5a.where(co.dventas_5a > 0)
    cols = [("ticker", "Ticker", 8, None), ("nombre", "Compañía", 26, None), ("sector", "Sector", 20, None),
            ("fy_end", "Último FY (SEC)", 12, "yyyy-mm-dd"), ("ventas_fy", "Ventas FY (USD mm)", 12, "#,##0"),
            ("tax_rate", "Tasa imp. propia", 10, "0.0%"), ("tax_n", "Años", 6, "0"),
            ("inv_rate", "Tasa inv. propia", 10, "0%"), ("inv_sin_nwc", "Sin capital de trabajo", 10, None),
            ("ma_sobre_dventas", "M&A 5a / Δventas", 10, "0%"), ("cagr3", "CAGR ventas 3a", 10, "0.0%")]
    co["ventas_fy"] = co.ventas_fy / 1e6
    co["fy_end"] = pd.to_datetime(co.fy_end).dt.date
    _tabla(ws, co.sort_values(["sector", "ticker"]), cols)
    ws.cell(row=1, column=10).comment = Comment("Adquisiciones de los últimos 5 años sobre el aumento de ventas. "
                                                "Alto = crecimiento comprado: la tasa de inversión sin M&A lo subestima.", "screen")


def main():
    df, co, sec = SP.main()
    wb = Workbook()
    last = hoja_screen(wb, df)
    hoja_resumen(wb, df, last)
    hoja_defaults(wb, sec)
    hoja_companias(wb, co)
    hoja_criterios(wb, df.rf.iloc[0], df.rf_fecha.iloc[0])
    path = os.path.join(ROOT, "resultados", f"screen_sp500_{dt.date.today():%Y-%m-%d}.xlsx")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb.save(path)
    print(path)
    return path


if __name__ == "__main__":
    main()
