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
    series = [("Q1", "Q1", "var(--accent)", 2.6), ("SPY", "SPY", "var(--ink)", 1.6),
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
    st = r["stats"]
    c1, c2a, c2b = r["criterio1"], r["criterio2a"], r["criterio2b"]
    reg = pd.DataFrame(r["regresion"])

    filas_anio = ""
    for y, f in A.iterrows():
        g = f.Q1 > f.SPY
        filas_anio += (f'<tr><td>{y}{"" if f.completo else " (parcial)"}</td><td class="r num">{pct(f.Q1)}</td>'
                       f'<td class="r num">{pct(f.SPY)}</td><td class="r num">{pct(f["Universo (pesos iguales)"])}</td>'
                       f'<td class="r num {"pos" if g else "neg"}">{pct(f.Q1 - f.SPY)}</td>'
                       f'<td>{("Gana" if g else "Pierde") if f.completo else "no cuenta"}</td></tr>')
    nombres = {"alfa": "Alfa (retorno sin explicar)", "Mkt-RF": "Mercado", "SMB": "Tamaño (chicas)",
               "HML": "Value (baratas)", "RMW": "Rentabilidad", "CMA": "Inversión conservadora", "UMD": "Momentum"}
    filas_reg = "".join(
        f'<tr><td>{nombres[k]}</td><td class="r num">{num(reg.loc[k, "coef"] * (12 if k == "alfa" else 1), 2 if k != "alfa" else 3)}'
        f'{" anual" if k == "alfa" else ""}</td><td class="r num">{num(reg.loc[k, "t"])}</td>'
        f'<td>{"significativo" if abs(reg.loc[k, "t"]) >= 2 else "no significativo"}</td></tr>' for k in reg.index)
    filas_ds = "".join(
        f'<tr><td>Nivel {k} {"(más barato)" if k == "1" else "(más caro)" if k == "5" else ""}</td>'
        f'<td class="r num {"pos" if v > 0 else "neg"}">{pct(v)}</td></tr>' for k, v in c2b["spreads"].items())
    variantes = [("Q1 principal (base rate)", "Q1"), ("Q1 brecha 4%", "Q1 brecha 4%"),
                 ("Q1 P(base rate)", "Q1 P(base rate)"), ("Q1 neutral por sector", "Q1 neutral sector"),
                 ("Universo con pesos iguales", "Universo (pesos iguales)"), ("SPY", "SPY")]
    filas_var = "".join(
        f'<tr><td>{n}</td><td class="r num">{pct(st[c]["cagr"])}</td><td class="r num">{pct(st[c]["vol"])}</td>'
        f'<td class="r num">{num(st[c]["sharpe"])}</td><td class="r num">{pct(st[c]["max_dd"])}</td></tr>' for n, c in variantes)
    excl = r["exclusiones"]
    filas_excl = "".join(f'<tr><td>{f}</td><td class="r num">{v["miembros"]}</td><td class="r num">{v["afuera"]}</td>'
                         f'<td class="r num">{pct(v["afuera"] / v["miembros"], 0)}</td></tr>' for f, v in excl.items())

    html = f"""<title>Backtest v1</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap">
<style>{ESTILO}
.verdict {{ border-left: 6px solid var(--sell); background: var(--sell-bg); border-radius: 12px; padding: 18px 20px; display: grid; gap: 8px; }}
.verdict h2 {{ margin: 0; color: var(--sell); font-size: 22px; }}
.verdict p {{ margin: 0; max-width: 80ch; }}
.crit {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
.crit .panel {{ display: grid; gap: 6px; align-content: start; }}
.crit .pill {{ justify-self: start; }}
.crit .big {{ font-family: var(--f-num); font-size: 24px; }}
.prose p, .prose li {{ max-width: 85ch; }}
.prose ul {{ padding-left: 20px; display: grid; gap: 6px; margin: 6px 0; }}
@media (max-width: 860px) {{ .crit {{ grid-template-columns: minmax(0, 1fr); }} }}
</style>
<div class="wrap">
  <header>
    <div class="eyebrow">Expectations Investing · backtest v1 · {r["desde"]} a {r["hasta"]}</div>
    <h1>Backtest v1</h1>
    <p class="lede">¿El quintil de mayor brecha de expectativas del S&amp;P 500 le gana al SPY después de costos, y no se
      explica solo por value? Criterio fijado antes de ver resultados (PREREGISTRO.md). Rebalanceo anual a fin de abril,
      pesos iguales, 20 pb por lado.</p>
  </header>

  <section class="verdict">
    <h2>No aprobado: no cumple ninguna de las tres condiciones</h2>
    <p>El quintil 1 rindió <b>{pct(st["Q1"]["cagr"])}</b> anual contra <b>{pct(st["SPY"]["cagr"])}</b> del SPY y le ganó
      en {c1["gana"]} de {c1["anios"]} años. No hay retorno sin explicar después de controlar por factores (alfa
      {pct(c2a["alfa_anual"], 2)} anual, t = {num(c2a["t"])}): lo que rinde se explica por su inclinación a value,
      rentabilidad y empresas más chicas. Y los quintiles no van en orden: la brecha, tal como está construida, no
      ordena los retornos futuros.</p>
  </section>

  <section class="crit">
    <div class="panel"><div class="eyebrow">1 · Le gana al SPY</div><div class="big">{c1["gana"]} de {c1["anios"]} años</div>
      <div>Hacía falta la mayoría ({c1["anios"] // 2 + 1}).</div>{chip(c1["cumple"])}
      <p class="note">Contra el promedio de su propio universo gana en {c1["gana_universo"]} de {c1["anios"]}.</p></div>
    <div class="panel"><div class="eyebrow">2a · Alfa con factores</div><div class="big">{pct(c2a["alfa_anual"], 2)} anual</div>
      <div>t = {num(c2a["t"])}; hacía falta alfa &gt; 0 y t ≥ 2.</div>{chip(c2a["cumple"])}
      <p class="note">Carga en value (HML) {num(c2a["hml"])}, t = {num(c2a["t_hml"])}. R² {num(c2a["r2"])}.</p></div>
    <div class="panel"><div class="eyebrow">2b · Doble orden por múltiplo</div><div class="big">{c2b["positivos"]} de 5 niveles</div>
      <div>Q1 &gt; Q5 hacía falta en 3 de 5 y en promedio.</div>{chip(c2b["cumple"])}
      <p class="note">Diferencia promedio {pct(c2b["promedio"])} anual: casi toda viene del nivel más barato.</p></div>
  </section>

  <section class="panel">
    <h2>Crecimiento de 1 dólar</h2>
    {curva_svg(M)}
    <p class="note">Q1 = estrategia (quintil de mayor brecha). Universo = promedio con pesos iguales de las rankeadas.
      Retornos totales mensuales (dividendos reinvertidos), netos de costos. El último mes es parcial.</p>
  </section>

  <section class="two">
    <div class="panel"><h2>Retorno anual compuesto</h2>{barras_quintiles(st)}
      <p class="note">Si la brecha predijera retornos, Q1 &gt; Q2 &gt; … &gt; Q5. No pasa.</p></div>
    <div class="panel"><h2>Año por año</h2><div class="scroll"><table><thead><tr><th>Año</th><th class="r">Q1</th>
      <th class="r">SPY</th><th class="r">Universo</th><th class="r">Q1 − SPY</th><th></th></tr></thead>
      <tbody>{filas_anio}</tbody></table></div></div>
  </section>

  <section class="two">
    <div class="panel"><h2>Regresión de factores (Q1)</h2><div class="scroll"><table><thead><tr><th>Factor</th>
      <th class="r">Exposición</th><th class="r">t</th><th></th></tr></thead><tbody>{filas_reg}</tbody></table></div>
      <p class="note">Fama-French 5 + momentum, {c2a["n"]} meses, errores Newey-West. El Q1 es una cartera de empresas
      baratas, rentables, de inversión conservadora y con momentum negativo. Esas inclinaciones explican su retorno.</p></div>
    <div class="panel"><h2>Doble orden: Q1 − Q5 dentro de cada nivel de múltiplo</h2><div class="scroll"><table><thead>
      <tr><th>Nivel de rendimiento operativo</th><th class="r">Q1 − Q5 anual</th></tr></thead><tbody>{filas_ds}</tbody></table></div>
      <p class="note">Entre empresas igual de baratas, una brecha mayor no anticipa mejor retorno, salvo en el grupo más barato.</p></div>
  </section>

  <section class="two">
    <div class="panel"><h2>Variantes (secundarias)</h2><div class="scroll"><table><thead><tr><th>Cartera</th>
      <th class="r">Retorno anual</th><th class="r">Volatilidad</th><th class="r">Sharpe</th><th class="r">Peor caída</th></tr>
      </thead><tbody>{filas_var}</tbody></table></div>
      <p class="note">Ninguna variante cambia la conclusión: todas quedan entre el universo y el SPY.</p></div>
    <div class="panel"><h2>Compañías afuera por sesgo de supervivencia</h2><div class="scroll"><table><thead><tr><th>Fecha</th>
      <th class="r">Miembros</th><th class="r">Afuera</th><th class="r">%</th></tr></thead><tbody>{filas_excl}</tbody></table></div>
      <p class="note">Deslistadas o compradas, sin precios gratis. El sesgo favorece al Q1, así que el resultado real
      probablemente es peor.</p></div>
  </section>

  <section class="panel prose">
    <h2>Cómo leerlo</h2>
    <ul>
      <li><b>Qué se probó.</b> La versión cruda: defaults por sector, sin normalizar M&amp;A ni ítems no recurrentes, y con
        el crecimiento del último ejercicio en lugar del consenso (no hay consenso histórico gratis).</li>
      <li><b>Qué no dice.</b> No prueba que el método de Expectations Investing no funcione. Prueba que este screen
        automático, aplicado mecánicamente a 400 compañías, no agrega valor sobre factores conocidos. El método original
        incluye el análisis competitivo y los escenarios (pasos 2 y 3), que este test no tiene.</li>
      <li><b>El período.</b> 2016-2026 fue de dominio de las megacaps de crecimiento: el SPY le ganó a su versión con
        pesos iguales por 2,2 puntos al año. Cualquier screen con pesos iguales arrancaba en desventaja.</li>
      <li><b>Límites del test.</b> Sesgo de supervivencia (favorece al Q1); base rates con datos 2015-2025; 21% de las
        valuaciones con EBIT aproximado (resultado antes de impuestos + intereses).</li>
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
