"""Página HTML con los resultados del backtest v1 contra el criterio pre-registrado.

Uso: python reporte_backtest.py  -> resultados/backtest_v1.html (lee data/backtest/*)
"""
import json
import os

import pandas as pd

from exportar_html import PLANTILLA
from pit import ROOT

DIR = os.path.join(ROOT, "data", "backtest")

# Reutiliza los tokens de color y tipografía de la página del screen.
ESTILO = PLANTILLA.split("<style>")[1].split("</style>")[0]


def pct(x, d=1):
    return "—" if x is None or pd.isna(x) else f"{x * 100:.{d}f}%".replace(".", ",")


def num(x, d=2):
    return "—" if x is None or pd.isna(x) else f"{x:.{d}f}".replace(".", ",")


def chip(ok):
    return ('<span class="pill c-COMPRA">Cumple</span>' if ok else '<span class="pill c-VENTA">No cumple</span>')


def curva_svg(M):
    series = [("Q1", "Q1", "var(--accent)", 2.6), ("SPY", "SPY", "var(--ink)", 1.6), ("RSP", "RSP", "var(--muted)", 1.4),
              ("Universo", "Universo (pesos iguales)", "var(--hold)", 1.6),
              ("Q5", "Q5", "var(--sell)", 1.2)]
    C = {k: (1 + M[c]).cumprod() for _, c, _, _ in series for k in [c]}
    W, H, L, R, T, B = 900, 340, 48, 130, 12, 28
    lo = min(min(v.min() for v in C.values()), 1.0)
    hi = max(v.max() for v in C.values())
    n = len(M)
    x = lambda i: L + i / (n - 1) * (W - L - R)
    y = lambda v: T + (hi - v) / (hi - lo) * (H - T - B)
    s = f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Crecimiento de 1 dólar">'
    paso = 0.5 if hi < 4 else 1.0
    v = 1.0
    while v <= hi + 1e-9:
        s += (f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="var(--line)"/>'
              f'<text x="{L - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{num(v, 1)}</text>')
        v += paso
    for i, mes in enumerate(M.index):
        if mes.month == 1 and mes.year % 2 == 0:
            s += f'<text x="{x(i):.1f}" y="{H - 8}" text-anchor="middle">{mes.year}</text>'
    corte = [i for i, mes in enumerate(M.index) if str(mes) == "2016-05"]
    if corte:
        xc = x(corte[0])
        s += (f'<line x1="{xc:.1f}" x2="{xc:.1f}" y1="{T}" y2="{H - B}" stroke="var(--muted)" stroke-dasharray="4 4"/>'
              f'<text x="{xc - 6:.1f}" y="{T + 12}" text-anchor="end">fuera de muestra</text>'
              f'<text x="{xc + 6:.1f}" y="{T + 12}" text-anchor="start">v1</text>')
    ys_fin = []
    for nombre, c, col, w in series:
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(C[c]))
        s += f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="{w}" stroke-linejoin="round"/>'
        ys_fin.append([y(C[c].iloc[-1]), nombre, col, C[c].iloc[-1]])
    ys_fin.sort()
    for k in range(1, len(ys_fin)):          # separa etiquetas superpuestas
        if ys_fin[k][0] - ys_fin[k - 1][0] < 14:
            ys_fin[k][0] = ys_fin[k - 1][0] + 14
    for yy, nombre, col, v in ys_fin:
        s += (f'<circle cx="{x(n - 1):.1f}" cy="{y(v):.1f}" r="3" fill="{col}"/>'
              f'<text x="{x(n - 1) + 8:.1f}" y="{yy + 4:.1f}" style="fill:{col}">{nombre} · {num(v)}</text>')
    return s + "</svg>"


def barras_quintiles(st):
    filas = [(f"Q{q}", st[f"Q{q}"]["cagr"]) for q in range(1, 6)] + [("SPY", st["SPY"]["cagr"]),
                                                                    ("Universo", st["Universo (pesos iguales)"]["cagr"])]
    W, L, R, rowH = 460, 80, 70, 30
    H = rowH * len(filas) + 10
    hi = max(v for _, v in filas)
    x = lambda v: L + v / hi * (W - L - R)
    s = f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Retorno anual por quintil">'
    for i, (n, v) in enumerate(filas):
        yy = 6 + i * rowH
        col = "var(--accent)" if n == "Q1" else ("var(--ink)" if n == "SPY" else ("var(--hold)" if n == "Universo" else "var(--muted)"))
        s += (f'<text class="lbl" x="{L - 10}" y="{yy + 17}" text-anchor="end">{n}</text>'
              f'<rect x="{L}" y="{yy + 4}" width="{x(v) - L:.1f}" height="18" rx="3" fill="{col}" opacity=".85"/>'
              f'<text x="{x(v) + 6:.1f}" y="{yy + 17}" style="fill:var(--ink)">{pct(v)}</text>')
    return s + "</svg>"


def main():
    r = json.load(open(os.path.join(DIR, "resultado.json")))
    M = pd.read_csv(os.path.join(DIR, "mensual.csv"), index_col=0)
    M.index = pd.PeriodIndex(M.index, freq="M")
    A = pd.read_csv(os.path.join(DIR, "anual.csv"), index_col=0)
    T = r["tramos"]
    oos, v1, full = T["2010-2016 (fuera de muestra)"], T["2016-2026 (v1)"], T["Completo 2010-2026"]
    st = full["stats"]

    def fila_crit(nombre, f):
        return (f"<tr><td>{nombre}</td>" + "".join(f"<td>{f(t)}</td>" for t in (oos, v1, full)) + "</tr>")
    crit = "".join([
        fila_crit("1 · Q1 &gt; SPY en la mayoría de los años", lambda t: f'{t["criterio1"]["gana"]} de {t["criterio1"]["anios"]} {chip(t["criterio1"]["cumple"])}'),
        fila_crit("2a · Alfa &gt; 0 con t ≥ 2 (Fama-French 5 + momentum)", lambda t: f'{pct(t["criterio2a"]["alfa_anual"], 2)}, t = {num(t["criterio2a"]["t"])} {chip(t["criterio2a"]["cumple"])}'),
        fila_crit("2b · Doble orden: Q1 &gt; Q5 en ≥ 3 de 5 niveles", lambda t: f'{t["criterio2b"]["positivos"]} de 5 {chip(t["criterio2b"]["cumple"])}'),
        fila_crit("<b>Veredicto</b>", lambda t: '<span class="pill c-COMPRA">Aprobado</span>' if t["aprobado"] else '<span class="pill c-VENTA">No aprobado</span>'),
        fila_crit("Referencia: Q1 &gt; RSP (años)", lambda t: f'{t["criterio1"]["gana_rsp"]} de {t["criterio1"]["anios"]}'),
        fila_crit("Referencia: alfa de Q1 − RSP", lambda t: f'{pct(t["criterio2a"]["alfa_vs_rsp_anual"], 2)}, t = {num(t["criterio2a"]["t_vs_rsp"])}'),
    ])
    filas_q = "".join(
        f"<tr><td>{n}</td>" + "".join(f'<td class="r num">{pct(t["stats"][c]["cagr"])}</td>' for t in (oos, v1, full)) + "</tr>"
        for n, c in [("Q1", "Q1"), ("Q2", "Q2"), ("Q3", "Q3"), ("Q4", "Q4"), ("Q5", "Q5"),
                     ("Universo (pesos iguales)", "Universo (pesos iguales)"), ("RSP", "RSP"), ("SPY", "SPY")])
    filas_anio = ""
    for y, f in A.iterrows():
        g = f.Q1 > f.SPY
        filas_anio += (f'<tr><td>{y}{"" if f.completo else " (parcial)"}</td><td class="r num">{pct(f.Q1)}</td>'
                       f'<td class="r num">{pct(f.SPY)}</td><td class="r num">{pct(f.RSP)}</td>'
                       f'<td class="r num {"pos" if g else "neg"}">{pct(f.Q1 - f.SPY)}</td>'
                       f'<td class="r num {"pos" if f.Q1 > f.RSP else "neg"}">{pct(f.Q1 - f.RSP)}</td></tr>')
    nombres = {"alfa": "Alfa anual (retorno sin explicar)", "Mkt-RF": "Mercado", "SMB": "Tamaño (chicas)",
               "HML": "Value (baratas)", "RMW": "Rentabilidad", "CMA": "Inversión conservadora", "UMD": "Momentum"}
    def filas_reg(t):
        reg = pd.DataFrame(t["regresion"])
        return "".join(f'<tr><td>{nombres[k]}</td><td class="r num">{pct(reg.loc[k, "coef"] * 12, 2) if k == "alfa" else num(reg.loc[k, "coef"])}</td>'
                       f'<td class="r num">{num(reg.loc[k, "t"])}</td></tr>' for k in reg.index)
    filas_ds = "".join(
        f'<tr><td>Nivel {k}{" (más barato)" if k == "1" else " (más caro)" if k == "5" else ""}</td>' +
        "".join(f'<td class="r num {"pos" if t["criterio2b"]["spreads"][k] > 0 else "neg"}">{pct(t["criterio2b"]["spreads"][k])}</td>' for t in (oos, v1, full)) +
        "</tr>" for k in ["1", "2", "3", "4", "5"])
    variantes = [("Q1 principal (base rate)", "Q1"), ("Q1 brecha 4%", "Q1 brecha 4%"), ("Q1 P(base rate)", "Q1 P(base rate)"),
                 ("Q1 neutral por sector", "Q1 neutral sector"), ("Universo con pesos iguales", "Universo (pesos iguales)"),
                 ("RSP", "RSP"), ("SPY", "SPY")]
    filas_var = "".join(
        f'<tr><td>{n}</td><td class="r num">{pct(st[c]["cagr"])}</td><td class="r num">{pct(st[c]["vol"])}</td>'
        f'<td class="r num">{num(st[c]["sharpe"])}</td><td class="r num">{pct(st[c]["max_dd"])}</td></tr>' for n, c in variantes)
    filas_excl = "".join(f'<tr><td>{f}</td><td class="r num">{v["miembros"]}</td><td class="r num">{v["afuera"]}</td>'
                         f'<td class="r num">{pct(v["afuera"] / v["miembros"], 0)}</td></tr>' for f, v in r["exclusiones"].items())
    n_ok = sum(t["aprobado"] for t in (oos, v1, full))
    titulo = ("No aprobado en ningún tramo" if n_ok == 0 else
              "Aprobado fuera de muestra" if oos["aprobado"] else f"Aprobado en {n_ok} de 3 tramos")
    color = "var(--sell)" if not oos["aprobado"] else "var(--buy)"
    fondo = "var(--sell-bg)" if not oos["aprobado"] else "var(--buy-bg)"
    resumen = (f'En todo el período el quintil 1 rindió <b>{pct(st["Q1"]["cagr"])}</b> anual, contra <b>{pct(st["SPY"]["cagr"])}</b> '
               f'del SPY y <b>{pct(st["RSP"]["cagr"])}</b> del RSP. En el tramo nuevo, 2010-2016 (fuera de muestra), le ganó al SPY '
               f'en {oos["criterio1"]["gana"]} de {oos["criterio1"]["anios"]} años, con alfa {pct(oos["criterio2a"]["alfa_anual"], 2)} '
               f'(t = {num(oos["criterio2a"]["t"])}).')

    html = f"""<title>Backtest v1</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap">
<style>{ESTILO}
.verdict {{ border-left: 6px solid {color}; background: {fondo}; border-radius: 12px; padding: 18px 20px; display: grid; gap: 8px; }}
.verdict h2 {{ margin: 0; color: {color}; font-size: 22px; }}
.verdict p {{ margin: 0; max-width: 85ch; }}
.prose p, .prose li {{ max-width: 85ch; }}
.prose ul {{ padding-left: 20px; display: grid; gap: 6px; margin: 6px 0; }}
table.crit td {{ white-space: normal; vertical-align: middle; }}
.three {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }}
@media (max-width: 860px) {{ .three {{ grid-template-columns: minmax(0, 1fr); }} }}
</style>
<div class="wrap">
  <header>
    <div class="eyebrow">Expectations Investing · backtest v1 + extensión · {r["desde"]} a {r["hasta"]}</div>
    <h1>Backtest v1</h1>
    <p class="lede">¿El quintil de mayor brecha de expectativas del S&amp;P 500 le gana al SPY después de costos, y no se
      explica solo por value? Criterio fijado antes de ver resultados (PREREGISTRO.md). Rebalanceo anual a fin de abril,
      pesos iguales, 20 pb por lado. El tramo 2010-2016 es fuera de muestra: se pre-registró antes de correrlo.</p>
  </header>

  <section class="verdict"><h2>{titulo}</h2><p>{resumen}</p></section>

  <section class="panel">
    <h2>Criterio por tramo</h2>
    <div class="scroll"><table class="crit"><thead><tr><th>Condición</th><th>2010-2016 · fuera de muestra</th>
      <th>2016-2026 · v1</th><th>Completo 2010-2026</th></tr></thead><tbody>{crit}</tbody></table></div>
    <p class="note">Las filas de RSP son referencia: se agregaron después de ver 2016-2026 y no cambian el veredicto.</p>
  </section>

  <section class="panel">
    <h2>Crecimiento de 1 dólar</h2>
    {curva_svg(M)}
    <p class="note">Q1 = estrategia (quintil de mayor brecha). Universo = promedio con pesos iguales de las rankeadas.
      Retornos totales mensuales, netos de costos. El último mes es parcial.</p>
  </section>

  <section class="three">
    <div class="panel"><h2>Retorno anual por quintil</h2><div class="scroll"><table><thead><tr><th>Cartera</th>
      <th class="r">2010-16</th><th class="r">2016-26</th><th class="r">Completo</th></tr></thead><tbody>{filas_q}</tbody></table></div>
      <p class="note">Si la brecha predijera retornos, Q1 &gt; Q2 &gt; … &gt; Q5 en cada columna.</p></div>
    <div class="panel"><h2>Doble orden: Q1 − Q5 por nivel de múltiplo</h2><div class="scroll"><table><thead><tr><th>Nivel</th>
      <th class="r">2010-16</th><th class="r">2016-26</th><th class="r">Completo</th></tr></thead><tbody>{filas_ds}</tbody></table></div>
      <p class="note">Entre empresas igual de baratas: ¿una brecha mayor anticipa mejor retorno?</p></div>
  </section>

  <section class="three">
    <div class="panel"><h2>Año por año</h2><div class="scroll"><table><thead><tr><th>Año</th><th class="r">Q1</th>
      <th class="r">SPY</th><th class="r">RSP</th><th class="r">Q1 − SPY</th><th class="r">Q1 − RSP</th></tr></thead>
      <tbody>{filas_anio}</tbody></table></div></div>
    <div class="panel"><h2>Factores del Q1</h2>
      <h3 style="font-size:13px;margin:4px 0">Completo 2010-2026</h3><div class="scroll"><table><thead><tr><th>Factor</th>
      <th class="r">Exposición</th><th class="r">t</th></tr></thead><tbody>{filas_reg(full)}</tbody></table></div>
      <h3 style="font-size:13px;margin:14px 0 4px">Fuera de muestra 2010-2016</h3><div class="scroll"><table><thead><tr><th>Factor</th>
      <th class="r">Exposición</th><th class="r">t</th></tr></thead><tbody>{filas_reg(oos)}</tbody></table></div>
      <p class="note">Fama-French 5 + momentum, errores Newey-West. |t| ≥ 2 = significativo.</p></div>
  </section>

  <section class="three">
    <div class="panel"><h2>Variantes (completo)</h2><div class="scroll"><table><thead><tr><th>Cartera</th>
      <th class="r">Retorno</th><th class="r">Volatilidad</th><th class="r">Sharpe</th><th class="r">Peor caída</th></tr>
      </thead><tbody>{filas_var}</tbody></table></div></div>
    <div class="panel"><h2>Afuera por sesgo de supervivencia</h2><div class="scroll"><table><thead><tr><th>Fecha</th>
      <th class="r">Miembros</th><th class="r">Afuera</th><th class="r">%</th></tr></thead><tbody>{filas_excl}</tbody></table></div>
      <p class="note">Deslistadas o compradas, sin precios gratis. El sesgo favorece a las carteras de nuestro universo frente
      a SPY y RSP, que sí las incluyen; pesa más en los primeros años.</p></div>
  </section>

  <section class="panel prose">
    <h2>Cómo leerlo</h2>
    <ul>
      <li><b>Qué se probó.</b> La versión cruda del screen: defaults por sector, sin normalizar M&amp;A ni ítems no
        recurrentes, y con el crecimiento del último ejercicio en lugar del consenso (no hay consenso histórico gratis).</li>
      <li><b>Qué no dice.</b> No prueba ni descarta el método de Expectations Investing completo: el test no incluye el
        análisis competitivo ni los escenarios (pasos 2 y 3).</li>
      <li><b>Por qué desde 2010.</b> La SEC publica estados contables estructurados (XBRL) desde 2009; antes no hay datos
        gratis confiables para 500 empresas.</li>
      <li><b>Límites.</b> Sesgo de supervivencia (hasta 29% del índice afuera en 2010); base rates con ventas 2015-2025;
        parte de las valuaciones con EBIT aproximado (resultado antes de impuestos + intereses).</li>
    </ul>
  </section>
</div>
"""
    path = os.path.join(ROOT, "resultados", "backtest_v1.html")
    with open(path, "w") as f:
        f.write(html)
    print(path)
    return path


if __name__ == "__main__":
    main()
