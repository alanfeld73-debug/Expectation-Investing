# Registro de supuestos y cambios

Formato: fecha | qué | motivo. Los supuestos por compañía viven en `src/expectations_screen.py` (dict `A`);
todo cambio a ellos se anota acá.

## Convenciones vigentes (no cambiar sin consultar)
- NOPAT = EBIT GAAP x (1 - tasa); SBC es gasto.
- FCF = NOPAT - tasa de inversión x ΔVentas.
- Residual Rappaport: NOPAT_N / WACC, sin crecimiento después de 10 años.
- WACC: Rf (UST 10a) + beta 5a acotada [0,8; 1,8] x ERP 5% + prima riesgo país.
- Modelos FCF / RAMP / EQUITY.

## Pendientes de definir
- Prima de riesgo país: hoy va ad hoc por compañía (`crp` en `A`), sin tabla por país.

## Historial
| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-26 | Código base v0.2 importado (screen, base rates, escenarios). | Inicio del repo. |
| 2026-11-26 | baserates: si las ventas son < USD 100 M, `prob` devuelve None. Antes caía al bucket > USD 50 bn. | Bug: TOYO, RX y CTEK recibían la distribución de megacaps. |
| 2026-11-26 | baserates: el caché solo escribe cuando la descarga terminó; ignora archivos vacíos. | Bug: una descarga fallida dejaba un JSON vacío que bloqueaba los reintentos. |
| 2026-11-26 | baserates: User-Agent desde SEC_USER_AGENT (se sacó el mail hardcodeado); caché en data/sec_frames; sin descarga al importar. | El brief pide el mail de Criteria y caché en data/. |
| 2026-11-26 | screen: scan de TradingView cacheado por día en data/; omite tickers con campos faltantes en vez de cortar la corrida; salida en data/screen_output.csv. | Robustez y caché. |
| 2026-11-26 | reverse_dcf.py v0.1 importado (caso BKNG). User-Agent de la SEC centralizado en src/config.py. | Archivo faltante; un solo lugar para el contacto. |
| 2026-11-26 | Test de consistencia: reverse_dcf y screen dan el mismo valor operativo con los mismos inputs. | Evitar que los dos motores diverjan. |
| 2026-11-26 | Rf = UST 10 años de FRED (DGS10), con fecha en la salida y caché en data/rates. Primera toma: 4,91% al 2026-11-24 (antes 4,85% fijo). Sin red usa el caché; sin caché, 4,85% marcado como respaldo. | Aprobado por el usuario (pregunta 2). |
| 2026-11-26 | Crecimiento previo para base rates = CAGR de ventas de 3 ejercicios desde la SEC (10-K/20-F/40-F, us-gaap o ifrs-full, moneda de reporte). Antes: crecimiento interanual TTM de TradingView. Si no hay datos en la SEC (TOYO, CTEK, GGGOF, RX, VU), se usa solo el tamaño y se marca en la nota. | Aprobado por el usuario (pregunta 1): alinea con el prior de los buckets (CAGR 2012-15). |
| 2026-11-26 | Mapa ticker->CIK propio en data/sec/cik_map.json (desde company_tickers.json) con overrides en sec.CIK_MANUAL. | Brief: www.sec.gov puede bloquearse. |
| 2026-11-26 | Excel de salida (src/exportar_excel.py). Recomendación del screen: COMPRA si upside ≥ 20%; VENTA si upside ≤ -20% (propuesto, simétrico; faltan las reglas de salida definitivas); REVISAR DATOS si valor sin crecimiento > 150% del EV, EV < USD 0,5 bn o "sin TTM". Umbrales editables en la hoja Criterios. | Pedido del usuario: Excel con colores por recomendación. Venta y revisar datos están pendientes de validar. |
| 2026-11-26 | Universo S&P 500: lista actual de datasets/s-and-p-500-companies (503, con GICS y CIK). Composición histórica desde 1996 de fja05680/sp500 en data/universo (para la Semana 2). | Semana 1. La lista actual tiene sesgo de supervivencia: el backtest debe usar la histórica. |
| 2026-11-26 | Base point-in-time: SEC companyfacts desde 2012 con fecha de presentación (filed) en data/pit/facts.parquet (1,45 M filas, 503 compañías). XOM agrega el CIK predecesor 34088 (holding nuevo en 2026). APA reporta ventas con etiqueta propia: sin ventas en la SEC. | Semana 1. |
| 2026-11-26 | Defaults por sector = medianas de la SEC, últimos 5 ejercicios. Tasa impositiva = Σ impuesto / Σ resultado antes de impuestos (acotada 0-40%). Tasa de inversión = [Σ (capex - depreciación) + Δ capital de trabajo] / Δ ventas (acotada -100% a 200%), con capex = PP&E + software capitalizado + inmuebles, y depreciación = D&A - amortización de intangibles (el M&A no cuenta como inversión, así que su amortización tampoco se resta). | Pedido del usuario: los toma Claude y el usuario los revisa después. Primera versión daba tasas negativas por la amortización de intangibles comprados. |
| 2026-11-26 | Utilities pasan al modelo EQUITY (utilidad TTM y ROE TTM, acotado 5-30%), como los generadores. | Su tasa de inversión mediana topea en 200% (capex sigue a la base tarifaria, no a las ventas): con FCF cualquier crecimiento destruiría valor. |
| 2026-11-26 | Modelo EQUITY también para bancos, aseguradoras, brokers, consumer finance y holdings (BRK). FCF para pagos, bolsas/datos y brokers de seguros. | Clasificación por subindustria GICS. |
| 2026-11-26 | Marcas [revisar] que sacan a la compañía de los quintiles: consenso año 1 > 30% (hipercrecimiento o M&A), TTM fuera del rango [último FY, consenso] por más de 15 pp, ventas TV vs SEC fuera de 0,85-1,6x, EBIT ≤ 0, valor negativo (financieras cautivas, leases), valor sin crecimiento > 150% del EV. Resultado: 420 rankeadas, 81 a revisar, 2 sin dato. | Corrida cruda sin overrides: separar lo que necesita normalización manual (Semana 2). |
| 2026-11-26 | Brecha principal: la desaceleración llega en el año 10 a la mediana del base rate (tamaño + crecimiento previo, acotada 0-15%) en vez de 4% fijo. Se conserva la brecha a 4% como variante (brecha_4). | Punto 1 del plan contra el sesgo value (aprobado). Efecto chico: las medianas dan 3-7% (3,5-3,9% en empresas > USD 10 bn). |
| 2026-11-26 | Rankings adicionales (src/sesgo.py): neutral por sector, P(base rate), rendimiento operativo (NOPAT/EV) y doble orden (brecha dentro de cada quintil de rendimiento). Diagnóstico en data/sesgo_value.csv: la brecha principal tiene correlación 0,76 con value. | Medir y controlar el sesgo value. |
| 2026-11-26 | src/factores.py: regresión contra Fama-French 5 + momentum con errores Newey-West. La biblioteca de Ken French (mba.tuck.dartmouth.edu) está bloqueada por la red del entorno: hay que habilitarla. | Condición 2a del pre-registro. |
| 2026-11-26 | PREREGISTRO.md: estrategia principal, criterio de éxito y variantes secundarias fijados antes de ver resultados. Rebalanceo anual y costos de 20 pb por lado quedan propuestos, a confirmar. | Evitar elegir la variante después de ver los números. |
