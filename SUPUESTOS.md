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
