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
- Rf = 4,85% está fijo en el código sin fecha de toma. Hay que actualizarlo y anotar la fecha.
- SEC_USER_AGENT: definir el mail de contacto de Criteria.
- Prima de riesgo país: hoy va ad hoc por compañía (`crp` en `A`), sin tabla por país.

## Historial
| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-26 | Código base v0.2 importado (screen, base rates, escenarios). | Inicio del repo. |
| 2026-11-26 | baserates: si las ventas son < USD 100 M, `prob` devuelve None. Antes caía al bucket > USD 50 bn. | Bug: TOYO, RX y CTEK recibían la distribución de megacaps. |
| 2026-11-26 | baserates: el caché solo escribe cuando la descarga terminó; ignora archivos vacíos. | Bug: una descarga fallida dejaba un JSON vacío que bloqueaba los reintentos. |
| 2026-11-26 | baserates: User-Agent desde SEC_USER_AGENT (se sacó el mail hardcodeado); caché en data/sec_frames; sin descarga al importar. | El brief pide el mail de Criteria y caché en data/. |
| 2026-11-26 | screen: scan de TradingView cacheado por día en data/; omite tickers con campos faltantes en vez de cortar la corrida; salida en data/screen_output.csv. | Robustez y caché. |
