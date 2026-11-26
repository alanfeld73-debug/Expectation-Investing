# Sistema de selección de acciones — Expectations Investing

## Objetivo
Seleccionar acciones que le ganen al SPY en horizontes de 3 a 5 años con el método de Expectations
Investing (Rappaport & Mauboussin). Destino final: dashboard confiable para decisiones (posible módulo de Alyc.IA).

## Método
1. Leer expectativas: DCF inverso (crecimiento, margen y duración de ventaja que descuenta el precio).
2. Oportunidades de revisión: turbina de value triggers (ventas, costos, inversión) + análisis competitivo.
3. Comprar/vender: escenarios con probabilidades, valor esperado vs. precio, margen de seguridad 20%.
4. Cartera y monitoreo: pesos vs. SPY, reglas de salida, alertas.

## Convenciones del modelo (no cambiar sin preguntar)
- NOPAT = EBIT GAAP x (1 - tasa). La SBC es gasto (no se suma).
- FCF = NOPAT - inversión incremental, con inversión = tasa x ΔVentas.
- Residual de Rappaport: NOPAT_N / WACC, sin crecimiento después del horizonte (10 años).
- WACC: Rf (UST 10 años) + beta 5 años (acotada 0,8-1,8) x ERP 5% + prima riesgo país.
- Modelos: FCF (estándar), RAMP (margen converge a objetivo), EQUITY (bancos y generadores sobre
  utilidad o FCF ajustado de guía, ROE incremental).
- Base rates: CAGR de ventas a 10 años (SEC frames), por tamaño y crecimiento previo.
- `tests/test_modelo.py` verifica estas convenciones: correrlo (`python -m pytest -q tests`) después de cada cambio.

## Archivos
- `src/expectations_screen.py`: paso 1 (screen). Supuestos por compañía en el diccionario `A`.
- `src/baserates.py`: distribución de crecimiento histórico (visión externa).
- `src/escenarios.py`: pasos 2-3 (turbina, escenarios, regla de compra).
- `src/reverse_dcf.py`: análisis individual con grilla de sensibilidad.
- `src/config.py`: User-Agent de la SEC (sobreescribible con la variable SEC_USER_AGENT).
- `SUPUESTOS.md`: registro de supuestos y cambios con fecha y motivo.

## Fuentes de datos
- SEC (data.sec.gov): fuente principal de fundamentals. www.sec.gov puede estar bloqueado: mantener mapa ticker->CIK propio.
- TradingView scanner (API no oficial): precios, consenso y TTM de no listados en EE.UU. Puede cambiar sin aviso; conciliar contra SEC.
- Cachear todo en `data/` (no versionado) para no repetir descargas.

## Problemas conocidos
- Generadores (CEG, VST, TLN): EBIT GAAP distorsionado por MTM de coberturas -> guía ajustada.
- Ítems no recurrentes y M&A distorsionan TTM y consenso -> overrides documentados.
- El residual castiga franquicias de ventaja larga (V, UBER): mirar MIFP.
- Base rates con sesgo de supervivencia.
- Microcaps con datos de TradingView sin validar.

## Plan de trabajo
- Semana 1: corrida cruda del S&P 500 con defaults por sector + base point-in-time (SEC, desde 2012).
- Semana 2: normalización manual de 40-60 candidatos + backtest v1 (quintiles de brecha vs. SPY).
- Semana 3: resultados y decisión. Criterio definido ANTES de ver resultados: el quintil de mayor brecha
  le gana al SPY después de costos en la mayoría de los años y no se explica solo por value.

## Cómo trabajar
- Idioma: español.
- Commit en git al cerrar cada hito, con mensaje descriptivo.
- Todo supuesto nuevo queda registrado en SUPUESTOS.md con fecha y motivo.
- Antes de cambiar una convención del modelo, preguntar.
