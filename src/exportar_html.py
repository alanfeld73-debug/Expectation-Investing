"""Página HTML de la corrida del S&P 500 (tabla filtrable y ordenable, resumen por quintil y sector).

Uso: python exportar_html.py  -> resultados/screen_sp500_AAAA-MM-DD.html (lee data/screen_sp500.csv y
data/defaults_sector.csv; correr antes screen_sp500.py o exportar_sp500.py).

La recomendación usa los mismos umbrales que el Excel (Criterios): COMPRA si brecha >= 20%, VENTA si <= -20%,
REVISAR DATOS si la nota tiene [revisar] o el valor sin crecimiento supera 150% del EV.
"""
import datetime as dt
import json
import math
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
COMPRA, VENTA, SS_MAX = 0.20, -0.20, 1.50


def recomendacion(r):
    if pd.isna(r.brecha):
        return "SIN DATO"
    if (pd.notna(r.ss_share) and r.ss_share > SS_MAX) or "[revisar]" in str(r.nota or ""):
        return "REVISAR"
    if r.brecha >= COMPRA:
        return "COMPRA"
    if r.brecha <= VENTA:
        return "VENTA"
    return "MANTENER"


def _num(x, nd=4):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(float(x), nd)


def datos():
    df = pd.read_csv(os.path.join(DATA, "screen_sp500.csv"))
    sec = pd.read_csv(os.path.join(DATA, "defaults_sector.csv"))
    df["rec"] = df.apply(recomendacion, axis=1)
    df["nota"] = df.nota.fillna("").str.replace("[revisar] ", "", regex=False)
    cols = ["ticker", "nombre", "sector", "modelo", "precio", "mcap_bn", "g_impl", "g_ref", "g_hist3", "p_base_rate",
            "mifp", "v_fade", "brecha", "quintil", "ss_share", "wacc", "rec", "nota", "brecha_4", "quintil_sector",
            "quintil_dentro_ey", "g_term"]
    filas = []
    for r in df[cols].itertuples(index=False):
        f = []
        for k, v in zip(cols, r):
            if k == "mifp" and isinstance(v, float) and math.isinf(v):
                f.append(99)
            elif isinstance(v, float):
                v = _num(v, 2 if k in ("precio", "v_fade", "mcap_bn") else 4)
                f.append(int(v) if k.startswith("quintil") and v is not None else v)
            else:
                f.append(v if v == v else None)
        filas.append(f)
    sectores = [dict(sector=s.sector, tax=_num(s.tax_default), inv=_num(s.inv_default), n=int(s.n)) for s in sec.itertuples()]
    diag = pd.read_csv(os.path.join(DATA, "sesgo_value.csv"))
    sesgo = [dict(v=r.variante, rho=_num(r.rho_rendimiento), q1=_num(r.q1_en_ey1)) for r in diag.itertuples()]
    meta = dict(fecha=f"{dt.date.today():%d-%m-%Y}", rf=_num(df.rf.iloc[0]), rf_fecha=str(df.rf_fecha.iloc[0]))
    return dict(cols=cols, filas=filas, sectores=sectores, meta=meta, sesgo=sesgo)


PLANTILLA = r"""<title>Screen S&amp;P 500</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap">
<style>
/* Layout: encabezado con veredicto, fila de conteos que filtran, quintiles + sectores, tabla completa. */
:root {
  --bg: #f6f7fa; --surface: #ffffff; --ink: #141a2a; --muted: #5b6478; --line: #dfe3ec;
  --accent: #1f3864; --accent-soft: #e6ebf5;
  --buy: #1d7a46; --buy-bg: #dff3e6; --hold: #8a5a00; --hold-bg: #fbefd2;
  --sell: #b0263a; --sell-bg: #fbe3e6; --rev: #4d5566; --rev-bg: #e8eaef; --na: #8a90a0;
  --f-ui: "Archivo", system-ui, -apple-system, "Segoe UI", sans-serif;
  --f-num: "JetBrains Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #0f131c; --surface: #171c28; --ink: #e8ebf2; --muted: #9aa3b6; --line: #2a3142;
  --accent: #8fb0ea; --accent-soft: #1e2840;
  --buy: #5fd394; --buy-bg: #12301f; --hold: #f0c063; --hold-bg: #33280f;
  --sell: #ff8a99; --sell-bg: #3a161d; --rev: #b5bccb; --rev-bg: #262c39; --na: #6f778a; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #0f131c; --surface: #171c28; --ink: #e8ebf2; --muted: #9aa3b6; --line: #2a3142;
  --accent: #8fb0ea; --accent-soft: #1e2840;
  --buy: #5fd394; --buy-bg: #12301f; --hold: #f0c063; --hold-bg: #33280f;
  --sell: #ff8a99; --sell-bg: #3a161d; --rev: #b5bccb; --rev-bg: #262c39; --na: #6f778a; color-scheme: dark }
* { box-sizing: border-box; }
body { background: var(--bg); color: var(--ink); font-family: var(--f-ui); font-size: 14px; line-height: 1.45; }
.wrap { max-width: 1320px; margin: 0 auto; padding-block: 28px 56px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; gap: 28px; }
header { display: grid; gap: 8px; }
.eyebrow { font-size: 12px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); font-weight: 600; }
h1 { font-size: clamp(26px, 4vw, 36px); line-height: 1.1; margin: 0; font-weight: 700; text-wrap: balance; }
h2 { font-size: 18px; margin: 0 0 12px; font-weight: 600; }
.lede { color: var(--muted); max-width: 75ch; margin: 0; }
.meta { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 13px; color: var(--muted); }
.meta b { color: var(--ink); font-family: var(--f-num); font-weight: 500; }
.num { font-family: var(--f-num); font-variant-numeric: tabular-nums; }
/* Conteos */
.counts { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }
.count { border: 1px solid var(--line); background: var(--surface); border-radius: 10px; padding: 12px 14px; text-align: left;
  cursor: pointer; font: inherit; color: inherit; display: grid; gap: 2px; border-left: 4px solid var(--c); }
.count:hover { border-color: var(--c); }
.count[aria-pressed="true"] { background: var(--cbg); border-color: var(--c); }
.count .n { font-family: var(--f-num); font-size: 26px; font-weight: 500; color: var(--c); }
.count .l { font-size: 12px; letter-spacing: .06em; text-transform: uppercase; font-weight: 600; }
.count .d { font-size: 12px; color: var(--muted); }
.c-COMPRA { --c: var(--buy); --cbg: var(--buy-bg); } .c-MANTENER { --c: var(--hold); --cbg: var(--hold-bg); }
.c-VENTA { --c: var(--sell); --cbg: var(--sell-bg); } .c-REVISAR { --c: var(--rev); --cbg: var(--rev-bg); }
.c-SIN { --c: var(--na); --cbg: var(--rev-bg); }
/* Paneles */
.two { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 7fr); gap: 20px; }
.panel { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 18px; min-width: 0; }
.note { font-size: 12px; color: var(--muted); margin: 10px 0 0; }
svg text { fill: var(--muted); font-family: var(--f-num); font-size: 11px; }
svg .lbl { fill: var(--ink); font-family: var(--f-ui); font-size: 12px; font-weight: 600; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { padding: 7px 10px; text-align: left; border-bottom: 1px solid var(--line); white-space: nowrap; }
th { font-size: 11px; letter-spacing: .05em; text-transform: uppercase; color: var(--muted); font-weight: 600; background: var(--surface); }
td.r, th.r { text-align: right; }
/* Filtros */
.filters { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 12px; }
.filters input, .filters select { font: inherit; color: var(--ink); background: var(--bg); border: 1px solid var(--line);
  border-radius: 8px; padding: 7px 10px; min-width: 0; }
.filters input { flex: 1 1 220px; }
.filters label { font-size: 12px; color: var(--muted); display: flex; gap: 6px; align-items: center; }
.btn { font: inherit; font-size: 13px; border: 1px solid var(--line); background: var(--surface); color: var(--ink);
  border-radius: 8px; padding: 7px 12px; cursor: pointer; }
.btn:hover { border-color: var(--accent); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
#tabla th { position: sticky; top: 0; z-index: 1; cursor: pointer; user-select: none; }
#tabla th[aria-sort="ascending"]::after { content: " ▲"; } #tabla th[aria-sort="descending"]::after { content: " ▼"; }
#tabla tbody tr { cursor: pointer; }
#tabla tbody tr:hover td { background: var(--accent-soft); }
.tk { font-family: var(--f-num); font-weight: 500; }
.nm { max-width: 220px; overflow: hidden; text-overflow: ellipsis; }
.pill { display: inline-block; font-size: 11px; font-weight: 600; letter-spacing: .04em; padding: 2px 8px; border-radius: 99px;
  color: var(--c); background: var(--cbg); }
.neg { color: var(--sell); } .pos { color: var(--buy); }
.q { display: inline-grid; place-items: center; width: 22px; height: 22px; border-radius: 6px; font-family: var(--f-num);
  font-size: 12px; background: var(--accent-soft); color: var(--accent); }
.q1 { background: var(--buy-bg); color: var(--buy); font-weight: 600; } .q5 { background: var(--sell-bg); color: var(--sell); }
tr.detail td { white-space: normal; background: var(--bg); color: var(--muted); font-size: 12.5px; }
.tablewrap { max-height: 72vh; overflow: auto; border: 1px solid var(--line); border-radius: 10px; }
.foot { font-size: 12px; color: var(--muted); display: grid; gap: 6px; max-width: 90ch; }
@media (max-width: 860px) { .two { grid-template-columns: minmax(0, 1fr); } .counts { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .count:last-child { grid-column: span 2; } }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>

<div class="wrap">
  <header>
    <div class="eyebrow">Expectations Investing · Semana 1 · corrida cruda</div>
    <h1>Screen S&amp;P 500</h1>
    <p class="lede">Qué crecimiento descuenta el precio de cada compañía y cuánto vale si cumple el consenso del año 1 y luego
      desacelera hasta el crecimiento histórico típico de su tamaño (base rate, 3-7%). La <b>brecha</b> es ese valor sobre el precio. Defaults de impuestos e inversión por sector, sin
      normalizar: sirve para elegir los candidatos de la Semana 2, no para decidir compras.</p>
    <div class="meta" id="meta"></div>
  </header>

  <section class="counts" id="counts" aria-label="Filtrar por recomendación"></section>

  <section class="two">
    <div class="panel">
      <h2>Brecha mediana por quintil</h2>
      <div id="quint"></div>
      <p class="note">Valor a la derecha: brecha mediana · compañías. Quintil 1 = mayor brecha (más barato contra el consenso). Las marcadas para revisar no entran.
        El nivel es negativo para casi todo el índice porque el modelo es conservador; importa el orden.</p>
    </div>
    <div class="panel">
      <h2>Por sector</h2>
      <div class="scroll"><table id="sect"><thead><tr>
        <th>Sector</th><th class="r">Cías.</th><th class="r">En Q1</th><th class="r">Brecha med.*</th>
        <th class="r">Tasa imp.</th><th class="r">Tasa inv.</th></tr></thead><tbody></tbody></table></div>
      <p class="note">* Mediana de las rankeadas (sin las marcadas para revisar). Tasas = defaults del sector (medianas SEC, últimos 5 ejercicios). Financieras y utilities usan el
        modelo de equity (ROE), sin tasa de inversión.</p>
    </div>
  </section>

  <section class="panel">
    <h2>Sesgo value</h2>
    <p class="note" style="margin:0 0 12px">¿Cuánto se parece cada ranking a ordenar por múltiplo barato (NOPAT / EV)? Correlación 1 =
      es value puro. El backtest exige que el método gane también dentro de cada nivel de múltiplo (ver PREREGISTRO.md).</p>
    <div class="scroll"><table id="sesgo"><thead><tr><th>Ranking</th><th class="r">Correlación con value</th>
      <th>Q1 en el quintil más barato</th></tr></thead><tbody></tbody></table></div>
  </section>

  <section class="panel">
    <h2>Todas las compañías</h2>
    <div class="filters">
      <input id="q" type="search" placeholder="Buscar ticker o compañía" aria-label="Buscar">
      <label for="fsec">Sector <select id="fsec"><option value="">Todos</option></select></label>
      <label for="fq">Quintil <select id="fq"><option value="">Todos</option><option>1</option><option>2</option>
        <option>3</option><option>4</option><option>5</option></select></label>
      <button class="btn" id="limpiar" type="button">Limpiar filtros</button>
      <span class="note" id="shown" style="margin:0"></span>
    </div>
    <div class="tablewrap"><table id="tabla"><thead><tr></tr></thead><tbody></tbody></table></div>
    <p class="note">Orden inicial: quintil y, dentro de cada uno, brecha. Las marcadas para revisar quedan al final.
      Tocá una fila para ver la nota y un encabezado para ordenar.</p>
  </section>

  <footer class="foot">
    <div><b>Brecha.</b> Valor por acción si la empresa crece al consenso en el año 1 y desacelera en línea recta hasta la
      mediana histórica de empresas de su tamaño y crecimiento previo (base rate) en el año 10; después, sin crecimiento
      (residual de Rappaport). Brecha 4%: la misma cuenta desacelerando a 4% fijo. Q sector: quintil dentro de su sector.
      Q en su múltiplo: quintil de brecha entre empresas con múltiplo parecido.</div>
    <div><b>Cómo leer cada columna.</b> g implícito: CAGR de ventas a 10 años que justifica el precio. g consenso: crecimiento
      de ventas del ejercicio en curso según analistas. CAGR 3a: crecimiento real de los últimos 3 ejercicios (SEC).
      P(base rate): porcentaje de compañías de tamaño y crecimiento previo similares que lograron el g implícito en 10 años.
      MIFP: años de crecimiento de consenso que hacen falta para justificar el precio.</div>
    <div><b>Recomendación.</b> Compra si la brecha es de 20% o más; venta si es de −20% o menos; revisar si hay M&amp;A o
      hipercrecimiento (consenso &gt; 30%), ventas que no concilian con la SEC, EBIT negativo, valor negativo o valor sin
      crecimiento mayor a 150% del EV. La regla de venta es provisoria.</div>
    <div><b>Fuentes.</b> Precios, TTM y consenso: TradingView. Fundamentals históricos: SEC (XBRL). Tasa libre de riesgo:
      FRED DGS10. Beta 5 años acotada 0,8–1,8; prima de riesgo 5%.</div>
  </footer>
</div>

<script id="datos" type="application/json">__DATOS__</script>
<script>
(function () {
  const D = JSON.parse(document.getElementById("datos").textContent);
  const I = Object.fromEntries(D.cols.map((c, i) => [c, i]));
  const rows = D.filas;
  const REC = [["COMPRA", "Compra", "brecha ≥ 20%"], ["MANTENER", "Mantener", "entre −20% y 20%"],
               ["VENTA", "Venta", "brecha ≤ −20%"], ["REVISAR", "Revisar datos", "fuera del ranking"],
               ["SIN DATO", "Sin dato", "faltan datos"]];
  const pct = (x, d = 0) => x == null ? "—" : (x * 100).toFixed(d).replace(".", ",") + "%";
  const fmt = (x, d = 2) => x == null ? "—" : x.toLocaleString("es-AR", { minimumFractionDigits: d, maximumFractionDigits: d });
  const median = a => { a = a.filter(v => v != null).sort((x, y) => x - y); if (!a.length) return null;
    const m = Math.floor(a.length / 2); return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2; };
  const cls = r => "c-" + (r === "SIN DATO" ? "SIN" : r);

  // Meta
  const m = D.meta;
  document.getElementById("meta").innerHTML =
    `<span>Corrida <b>${m.fecha}</b></span><span>Rf (UST 10a) <b>${pct(m.rf, 2)}</b> al ${m.rf_fecha}</span>` +
    `<span>Compañías <b>${rows.length}</b></span>` +
    `<span>Rankeadas <b>${rows.filter(r => r[I.quintil] != null).length}</b></span>`;

  // Conteos (filtran la tabla)
  const state = { rec: null, q: "", sec: "", quint: "", sort: "quintil", dir: 1, open: null };
  const counts = document.getElementById("counts");
  REC.forEach(([k, l, d]) => {
    const b = document.createElement("button");
    b.type = "button"; b.className = "count " + cls(k); b.setAttribute("aria-pressed", "false"); b.dataset.rec = k;
    b.innerHTML = `<span class="n">${rows.filter(r => r[I.rec] === k).length}</span><span class="l">${l}</span><span class="d">${d}</span>`;
    b.onclick = () => { state.rec = state.rec === k ? null : k; render(); };
    counts.appendChild(b);
  });

  // Quintiles (barras horizontales, escala única)
  const qs = [1, 2, 3, 4, 5].map(q => ({ q, med: median(rows.filter(r => r[I.quintil] === q).map(r => r[I.brecha])),
    n: rows.filter(r => r[I.quintil] === q).length }));
  const lo = Math.min(0, ...qs.map(x => x.med)), hi = Math.max(0, ...qs.map(x => x.med));
  const W = 460, H = 200, L = 40, R = 64, rowH = 34, top = 14;
  const x = v => L + (v - lo) / (hi - lo) * (W - L - R);
  let svg = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Brecha mediana por quintil">`;
  const ticks = []; for (let t = Math.ceil(lo * 4) / 4; t <= hi + 1e-9; t += 0.25) ticks.push(+t.toFixed(2));
  ticks.forEach(t => { svg += `<line x1="${x(t)}" x2="${x(t)}" y1="${top - 4}" y2="${top + rowH * 5}" stroke="var(--line)"/>` +
    `<text x="${x(t)}" y="${top + rowH * 5 + 14}" text-anchor="middle">${pct(t)}</text>`; });
  qs.forEach((d, i) => {
    const y = top + i * rowH, x0 = x(Math.min(0, d.med)), w = Math.abs(x(d.med) - x(0));
    const col = d.med >= 0 ? "var(--buy)" : (d.q >= 4 ? "var(--sell)" : "var(--hold)");
    svg += `<text class="lbl" x="${L - 10}" y="${y + 20}" text-anchor="end">Q${d.q}</text>` +
      `<rect x="${x0}" y="${y + 7}" width="${Math.max(w, 1)}" height="20" rx="3" fill="${col}" opacity=".85"/>` +
      `<text x="${W - 4}" y="${y + 21}" text-anchor="end" style="fill:var(--ink)">${pct(d.med)} · ${d.n}</text>`;
  });
  svg += `<line x1="${x(0)}" x2="${x(0)}" y1="${top - 4}" y2="${top + rowH * 5}" stroke="var(--muted)"/></svg>`;
  document.getElementById("quint").innerHTML = svg;

  // Sectores
  const sbody = document.querySelector("#sect tbody"), fsec = document.getElementById("fsec");
  D.sectores.forEach(s => {
    const rs = rows.filter(r => r[I.sector] === s.sector);
    const rk = rs.filter(r => r[I.quintil] != null);
    const eq = s.sector === "Financials" || s.sector === "Utilities";
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${s.sector}</td><td class="r num">${rs.length}</td><td class="r num">${rs.filter(r => r[I.quintil] === 1).length}</td>` +
      `<td class="r num">${pct(median(rk.map(r => r[I.brecha])))}</td><td class="r num">${pct(s.tax, 1)}</td>` +
      `<td class="r num">${eq ? "ROE" : pct(s.inv)}</td>`;
    sbody.appendChild(tr);
    fsec.insertAdjacentHTML("beforeend", `<option>${s.sector}</option>`);
  });

  // Sesgo value
  const sb = document.querySelector("#sesgo tbody");
  D.sesgo.forEach(r => { const w = Math.round((r.q1 || 0) * 100);
    sb.insertAdjacentHTML("beforeend", `<tr><td>${r.v}</td><td class="r num">${r.rho == null ? "—" : r.rho.toFixed(2).replace(".", ",")}</td>` +
      `<td><span style="display:inline-block;vertical-align:middle;height:10px;width:${w * 1.6}px;background:var(--hold);border-radius:2px;margin-right:8px"></span>` +
      `<span class="num">${w}%</span></td></tr>`); });

  // Tabla principal
  const COLS = [["ticker", "Ticker"], ["nombre", "Compañía"], ["sector", "Sector"], ["precio", "Precio", "r"],
    ["mcap_bn", "Mkt cap bn", "r"], ["g_impl", "g implícito", "r"], ["g_ref", "g consenso", "r"], ["g_hist3", "CAGR 3a", "r"],
    ["p_base_rate", "P(base rate)", "r"], ["mifp", "MIFP", "r"], ["v_fade", "Valor", "r"], ["brecha", "Brecha", "r"],
    ["quintil", "Q", "r"], ["brecha_4", "Brecha 4%", "r"], ["quintil_sector", "Q sector", "r"],
    ["quintil_dentro_ey", "Q en su múltiplo", "r"], ["rec", "Recomendación"]];
  const thead = document.querySelector("#tabla thead tr");
  COLS.forEach(([k, l, a]) => { const th = document.createElement("th"); th.textContent = l; if (a) th.className = a;
    th.dataset.k = k; th.tabIndex = 0; th.onclick = th.onkeydown = e => { if (e.type === "keydown" && e.key !== "Enter") return;
      if (state.sort === k) state.dir *= -1; else { state.sort = k; state.dir = (k === "ticker" || k === "nombre" || k === "sector") ? 1 : -1; }
      render(); }; thead.appendChild(th); });
  const tbody = document.querySelector("#tabla tbody");
  const cell = (k, r) => {
    const v = r[I[k]];
    switch (k) {
      case "ticker": return `<td class="tk">${v}</td>`;
      case "nombre": return `<td class="nm" title="${v}">${v}</td>`;
      case "precio": case "v_fade": return `<td class="r num">${fmt(v)}</td>`;
      case "mcap_bn": return `<td class="r num">${fmt(v, 1)}</td>`;
      case "g_impl": case "g_ref": case "g_hist3": return `<td class="r num">${pct(v, 1)}</td>`;
      case "p_base_rate": return `<td class="r num">${pct(v)}</td>`;
      case "mifp": return `<td class="r num">${v == null ? "—" : v >= 99 ? "&gt;40" : fmt(v, 1)}</td>`;
      case "brecha": case "brecha_4": return `<td class="r num ${v == null ? "" : v >= 0 ? "pos" : "neg"}">${pct(v)}</td>`;
      case "quintil": case "quintil_sector": case "quintil_dentro_ey": return `<td class="r">${v == null ? "—" : `<span class="q q${v}">${v}</span>`}</td>`;
      case "rec": return `<td><span class="pill ${cls(v)}">${(REC.find(x => x[0] === v) || [, v])[1]}</span></td>`;
      default: return `<td>${v ?? "—"}</td>`;
    }
  };
  ["q", "fsec", "fq"].forEach(id => document.getElementById(id).addEventListener("input", e => {
    state[{ q: "q", fsec: "sec", fq: "quint" }[id]] = e.target.value; render(); }));
  document.getElementById("limpiar").onclick = () => { Object.assign(state, { rec: null, q: "", sec: "", quint: "" });
    ["q", "fsec", "fq"].forEach(id => document.getElementById(id).value = ""); render(); };

  function render() {
    counts.querySelectorAll(".count").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.rec === state.rec)));
    const q = state.q.trim().toLowerCase();
    let rs = rows.filter(r => (!state.rec || r[I.rec] === state.rec) && (!state.sec || r[I.sector] === state.sec) &&
      (!state.quint || r[I.quintil] === +state.quint) &&
      (!q || r[I.ticker].toLowerCase().includes(q) || (r[I.nombre] || "").toLowerCase().includes(q)));
    const k = I[state.sort];
    rs.sort((a, b) => { const x = a[k], y = b[k]; if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1;
      const c = (typeof x === "string" ? x.localeCompare(y) : x - y) * state.dir;
      return c || (b[I.brecha] ?? -1e9) - (a[I.brecha] ?? -1e9); });
    thead.querySelectorAll("th").forEach(th => th.setAttribute("aria-sort", th.dataset.k === state.sort ? (state.dir > 0 ? "ascending" : "descending") : "none"));
    tbody.innerHTML = rs.map(r => {
      const main = `<tr data-t="${r[I.ticker]}">${COLS.map(([c]) => cell(c, r)).join("")}</tr>`;
      if (state.open !== r[I.ticker]) return main;
      const det = [`Modelo ${r[I.modelo] || "—"}`, `WACC/Ke ${pct(r[I.wacc], 1)}`, `Crecimiento año 10 (base rate) ${pct(r[I.g_term], 1)}`, `Valor sin crecimiento / EV ${pct(r[I.ss_share])}`]
        .join(" · ") + (r[I.nota] ? ` · <b>Nota:</b> ${r[I.nota]}` : "");
      return main + `<tr class="detail"><td colspan="${COLS.length}">${det}</td></tr>`;
    }).join("");
    document.getElementById("shown").textContent = `${rs.length} de ${rows.length}`;
  }
  tbody.addEventListener("click", e => { const tr = e.target.closest("tr[data-t]"); if (!tr) return;
    state.open = state.open === tr.dataset.t ? null : tr.dataset.t; render(); });
  render();
})();
</script>
"""


def main():
    d = datos()
    html = PLANTILLA.replace("__DATOS__", json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    path = os.path.join(ROOT, "resultados", f"screen_sp500_{dt.date.today():%Y-%m-%d}.html")
    with open(path, "w") as f:
        f.write(html)
    print(path, f"{len(html) / 1024:.0f} KB")
    return path


if __name__ == "__main__":
    main()
