"""Exporta el screen y los escenarios a Excel con colores por recomendación.

Uso: python exportar_excel.py  -> resultados/screen_AAAA-MM-DD.xlsx

Corre el screen (paso 1) y los escenarios (pasos 2-3). La recomendación es una fórmula de Excel
que lee los umbrales de la hoja "Criterios", así que cambiar un umbral recalcula todo.
"""
import contextlib
import copy
import datetime as dt
import io
import os

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import escenarios as S
import expectations_screen as E

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = "Arial"
BLUE = Font(name=FONT, color="0000FF")
BOLD = Font(name=FONT, bold=True)
HDR = Font(name=FONT, bold=True, color="FFFFFF")
HDR_FILL = PatternFill("solid", fgColor="1F3864")
YELLOW = PatternFill("solid", fgColor="FFFF00")
THIN = Border(bottom=Side(style="thin", color="BFBFBF"))
COLORS = {  # texto de la recomendación -> (relleno, fuente)
    "COMPRA": ("C6EFCE", "006100"),
    "MANTENER": ("FFEB9C", "9C5700"),
    "VENTA": ("FFC7CE", "9C0006"),
    "REVISAR DATOS": ("D9D9D9", "404040"),
    "WATCHLIST": ("FFEB9C", "9C5700"),
}


def _style_header(ws, row, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font, cell.fill = HDR, HDR_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[row].height = 32


def hoja_criterios(wb, rf, rf_date):
    ws = wb.create_sheet("Criterios")
    ws["A1"] = "Criterios de recomendación (celdas amarillas editables)"
    ws["A1"].font = Font(name=FONT, bold=True, size=13)
    rows = [
        ("Compra si upside ≥", 0.20, "0%", "Margen de seguridad del método (CLAUDE.md)."),
        ("Venta si upside ≤", -0.20, "0%", "Propuesto 2026-11-26, simétrico a la compra. Pendiente: reglas de salida definitivas."),
        ("Revisar datos si valor sin crecimiento / EV >", 1.50, "0%",
         "Propuesto 2026-11-26: un valor sin crecimiento 50% mayor al EV suele ser error de datos."),
        ("Revisar datos si EV < (USD bn)", 0.50, "0.0", "Propuesto 2026-11-26: microcaps con datos de TradingView sin validar."),
    ]
    ws["A3"], ws["B3"], ws["C3"] = "Criterio", "Valor", "Fuente / motivo"
    _style_header(ws, 3, 3)
    for i, (lab, val, fmt, src) in enumerate(rows, start=4):
        ws.cell(row=i, column=1, value=lab).font = Font(name=FONT)
        c = ws.cell(row=i, column=2, value=val)
        c.font, c.fill, c.number_format = BLUE, YELLOW, fmt
        ws.cell(row=i, column=3, value=src).font = Font(name=FONT, italic=True)
    ws["A9"] = "También va a REVISAR DATOS si la nota dice \"sin TTM\" (sin datos de los últimos 12 meses)."
    ws["A11"], ws["B11"] = "Rf (UST 10 años)", rf
    ws["B11"].number_format, ws["B11"].font = "0.00%", BLUE
    ws["C11"] = f"FRED DGS10 al {rf_date}"
    ws["A12"], ws["B12"] = "Margen de seguridad escenarios", S.HURDLE
    ws["B12"].number_format, ws["B12"].font, ws["B12"].fill = "0%", BLUE, YELLOW
    ws["C12"] = "src/escenarios.py (HURDLE)"
    ws["A14"] = "Leyenda de colores"
    ws["A14"].font = BOLD
    for i, (txt, desc) in enumerate([
            ("COMPRA", "Upside sobre la trayectoria de consenso + fade ≥ umbral de compra."),
            ("MANTENER", "Entre ambos umbrales: el precio descuenta aproximadamente el consenso."),
            ("VENTA", "Upside ≤ umbral de venta: el precio descuenta más que el consenso."),
            ("REVISAR DATOS", "Dato sospechoso o microcap sin validar: no decidir hasta normalizar."),
            ("WATCHLIST", "(Escenarios) valor esperado por debajo del margen de seguridad.")], start=15):
        c = ws.cell(row=i, column=1, value=txt)
        fill, font = COLORS[txt]
        c.fill, c.font = PatternFill("solid", fgColor=fill), Font(name=FONT, bold=True, color=font)
        ws.cell(row=i, column=2, value=desc).font = Font(name=FONT)
    ws["A21"] = ("Aclaración: la hoja Screen es el paso 1 (consenso + fade, sin juicio del analista). "
                 "La decisión de compra del método sale de la hoja Escenarios.")
    ws["A21"].font = Font(name=FONT, italic=True)
    ws.column_dimensions["A"].width = 46
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 80
    return ws


def hoja_screen(ws, rows):
    ws.title = "Screen"
    ws["A1"] = f"Screen Expectations Investing — {dt.date.today():%d-%m-%Y}"
    ws["A1"].font = Font(name=FONT, bold=True, size=13)
    ws["A2"] = "Ordenado por upside. Valores de mercado: TradingView; ventas históricas: SEC; Rf: FRED."
    ws["A2"].font = Font(name=FONT, italic=True, color="595959")
    cols = [("Ticker", 9, None), ("Modelo", 9, None), ("Precio", 10, "#,##0.00"),
            ("EV / Mkt cap (USD bn)", 12, "#,##0.0"), ("WACC / Ke", 9, "0.0%"),
            ("Valor sin crecimiento / EV", 12, "0%"), ("g implícito (CAGR 10a)", 12, "0.0%"),
            ("CAGR ventas 3a (SEC)", 11, "0.0%"), ("P(base rate)", 10, "0%"), ("g consenso año 1", 11, "0.0%"),
            ("MIFP (años)", 9, "0.0"), ("Valor (consenso + fade)", 12, "#,##0.00"), ("Upside", 9, "0%"),
            ("Recomendación", 16, None), ("Nota", 70, None)]
    H = 4
    for j, (name, w, _) in enumerate(cols, 1):
        ws.cell(row=H, column=j, value=name)
        ws.column_dimensions[get_column_letter(j)].width = w
    _style_header(ws, H, len(cols))
    ws.cell(row=H, column=11).comment = Comment("Market-Implied Forecast Period: años de crecimiento de consenso que "
                                                "justifican el precio. '>40' = no alcanza en 40 años.", "screen")
    ws.cell(row=H, column=6).comment = Comment("NOPAT actual / WACC sobre EV (o utilidad / Ke sobre market cap). "
                                               ">100%: el precio descuenta caída.", "screen")
    for i, r in enumerate(rows, start=H + 1):
        mifp = r["mifp"]
        vals = [r["ticker"], r["modelo"], r["precio"], r["ev_bn"], r["wacc"], r["ss_share"], r["g_impl"],
                r["g_hist3"], r["p_base_rate"], r["g_ref"], ">40" if mifp == float("inf") else mifp, r["v_fade"]]
        for j, v in enumerate(vals, 1):
            c = ws.cell(row=i, column=j, value=v)
            c.font, c.border = Font(name=FONT), THIN
            if cols[j - 1][2]:
                c.number_format = cols[j - 1][2]
            if j == 11:
                c.alignment = Alignment(horizontal="right")
        ws.cell(row=i, column=13, value=f"=L{i}/C{i}-1").number_format = "0%"
        ws.cell(row=i, column=14, value=(
            f'=IF(OR(F{i}>Criterios!$B$6,D{i}<Criterios!$B$7,ISNUMBER(SEARCH("sin TTM",O{i}))),"REVISAR DATOS",'
            f'IF(M{i}>=Criterios!$B$4,"COMPRA",IF(M{i}<=Criterios!$B$5,"VENTA","MANTENER")))'))
        ws.cell(row=i, column=15, value=r["nota"])
        for j in (13, 14, 15):
            c = ws.cell(row=i, column=j)
            c.font, c.border = Font(name=FONT), THIN
        ws.cell(row=i, column=14).alignment = Alignment(horizontal="center")
    last = H + len(rows)
    for txt, (fill, font) in COLORS.items():
        ws.conditional_formatting.add(f"A{H+1}:N{last}", FormulaRule(
            formula=[f'$N{H+1}="{txt}"'], fill=PatternFill("solid", fgColor=fill),
            font=Font(name=FONT, color=font, bold=False)))
    ws.freeze_panes = f"B{H+1}"
    ws.auto_filter.ref = f"A{H}:O{last}"
    return last


def hoja_escenarios(wb, cos):
    ws = wb.create_sheet("Escenarios")
    ws["A1"] = "Pasos 2-3: escenarios ponderados (probabilidades editables en azul)"
    ws["A1"].font = Font(name=FONT, bold=True, size=13)
    ws["A2"] = ("Valor por acción de cada escenario calculado en Python (src/escenarios.py) con g año 1 + fade "
                "a 4% y los ajustes de driver indicados. El valor esperado y la decisión se recalculan en Excel.")
    ws["A2"].font = Font(name=FONT, italic=True, color="595959")
    heads = ["Ticker", "Escenario", "Probabilidad", "g año 1", "Ajuste de driver", "Valor / acción",
             "Upside vs. precio", "Precio actual"]
    widths = [9, 12, 12, 10, 22, 13, 13, 12]
    r = 4
    summary = []
    for t, sc in S.SC.items():
        if t not in cos:
            continue
        base = cos[t]
        for j, (h, w) in enumerate(zip(heads, widths), 1):
            ws.cell(row=r, column=j, value=h)
            ws.column_dimensions[get_column_letter(j)].width = w
        _style_header(ws, r, len(heads))
        first = r + 1
        for name, p, g1, kw in sc:
            r += 1
            c = copy.deepcopy(base)
            c.g_ref = g1
            v = c.value_per_share(c.fade_path(), **kw)
            adj = ", ".join(f"{k} {val:+.0%}" if k == "m_shift" else f"{k} {val:.0%}" for k, val in kw.items()) or "—"
            vals = [t, name, p, g1, adj, v, f"=F{r}/H{r}-1", base.price]
            fmts = [None, None, "0%", "0.0%", None, "#,##0.00", "0%", "#,##0.00"]
            for j, (val, fmt) in enumerate(zip(vals, fmts), 1):
                cell = ws.cell(row=r, column=j, value=val)
                cell.font = BLUE if j == 3 else Font(name=FONT)
                if fmt:
                    cell.number_format = fmt
        lastr = r
        r += 1
        ws.cell(row=r, column=2, value="Valor esperado").font = BOLD
        ws.cell(row=r, column=3, value=f"=SUM(C{first}:C{lastr})").number_format = "0%"
        ws.cell(row=r, column=6, value=f"=SUMPRODUCT(C{first}:C{lastr},F{first}:F{lastr})").number_format = "#,##0.00"
        ws.cell(row=r, column=7, value=f"=F{r}/H{lastr}-1").number_format = "0%"
        ev_row = r
        r += 1
        ws.cell(row=r, column=2, value="Precio de entrada").font = BOLD
        ws.cell(row=r, column=6, value=f"=F{ev_row}/(1+Criterios!$B$12)").number_format = "#,##0.00"
        ws.cell(row=r, column=7, value="Decisión").font = BOLD
        ws.cell(row=r, column=8, value=f'=IF(G{ev_row}>=Criterios!$B$12,"COMPRA","WATCHLIST")')
        for txt in ("COMPRA", "WATCHLIST"):
            fill, font = COLORS[txt]
            ws.conditional_formatting.add(f"H{r}", FormulaRule(
                formula=[f'$H${r}="{txt}"'], fill=PatternFill("solid", fgColor=fill),
                font=Font(name=FONT, bold=True, color=font)))
        for row in ws.iter_rows(min_row=ev_row, max_row=r):
            for cell in row:
                if not cell.font.bold:
                    cell.font = Font(name=FONT)
        summary.append((t, ev_row, r))
        r += 3
    return summary


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        cos = E.main()
    import csv
    with open(os.path.join(E.DATA, "screen_output.csv")) as f:
        rows = list(csv.DictReader(f))
    num = lambda x: float(x) if x not in ("", None) else None
    for r in rows:
        for k in ("precio", "ev_bn", "wacc", "ss_share", "g_impl", "g_hist3", "p_base_rate", "g_ref", "mifp",
                  "v_fade", "upside"):
            r[k] = num(r[k])
    wb = Workbook()
    hoja_screen(wb.active, rows)
    hoja_escenarios(wb, cos)
    hoja_criterios(wb, E.RF, E.RF_DATE)
    out_dir = os.path.join(ROOT, "resultados")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"screen_{dt.date.today():%Y-%m-%d}.xlsx")
    wb.save(path)
    print(path)
    return path


if __name__ == "__main__":
    main()
