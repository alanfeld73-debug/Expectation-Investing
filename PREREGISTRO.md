# Pre-registro del backtest v1

Fijado el 2026-11-26, **antes de ver cualquier resultado del backtest**. Cambiar algo de este archivo después
de ver resultados invalida la prueba: si se cambia, se anota la fecha, el motivo y que fue posterior.

## Pregunta
¿El quintil de mayor brecha de expectativas le gana al SPY después de costos, y no se explica solo por value?

## Estrategia principal (la única que decide)
- **Métrica:** brecha = valor por acción / precio - 1, con crecimiento año 1 = consenso y desaceleración lineal
  hasta la mediana del base rate de su tamaño y crecimiento previo en el año 10; residual NOPAT/WACC.
- **En el backtest el consenso se reemplaza** por el crecimiento real de ventas del último ejercicio conocido a la
  fecha (SEC, con fecha de presentación): no hay consenso histórico gratis. Medido el 2026-11-26, el ranking con uno u
  otro tiene correlación 0,91 y comparte el 80% del quintil 1 (aprobado por el usuario).
- **Cartera:** quintil 1 de brecha, pesos iguales. Excluye las marcadas `[revisar]`.
- **Universo:** en cada fecha, las compañías que estaban en el S&P 500 en esa fecha (composición histórica)
  **y que siguen cotizando hoy**. Las deslistadas (quiebras, compras, fusiones) quedan afuera porque no hay
  precios gratis de ellas (decisión del usuario, 2026-11-26).
- **Rebalanceo:** anual (confirmado por el usuario, 2026-11-26).
- **Costos:** 20 pb por lado sobre el volumen operado (confirmado por el usuario, 2026-11-26).
- **Período:** desde que la base point-in-time permite calcular la métrica (fundamentals SEC desde 2012).
- **Referencia:** SPY con dividendos reinvertidos.

## Sesgo de supervivencia (aceptado)
Sin las deslistadas, todos los quintiles se ven mejor que en la realidad: faltan las que quebraron o cayeron
fuerte. El sesgo probablemente favorece más al Q1, porque las que parecen baratas son las que más seguido terminan
mal. Para acotarlo:
- Se reporta, además del SPY, el **promedio con pesos iguales del mismo universo** (que tiene el mismo sesgo).
  Que el Q1 le gane a ese promedio es la comparación más limpia.
- Se reporta cuántas compañías del índice histórico quedan afuera por año.
- Si el resultado depende de un margen chico, se considera no concluyente hasta testear con deslistadas.

## Criterio de éxito (las dos condiciones)
1. **Le gana al SPY:** retorno del Q1 después de costos > SPY en la mayoría de los años calendario.
2. **No es solo value:**
   - a. Alfa positivo con t ≥ 2 (Newey-West) en la regresión contra Fama-French 5 + momentum (incluye HML).
   - b. Doble orden: dentro de cada quintil de rendimiento operativo (NOPAT/EV), el Q1 de brecha le gana al Q5
     en promedio y en al menos 3 de los 5 quintiles.

## Variantes secundarias (se reportan, no deciden)
- Brecha con desaceleración a 4% fijo (versión anterior).
- P(base rate) del crecimiento implícito.
- Brecha neutral por sector (quintiles dentro de cada sector).

## Diagnóstico previo (corrida del 2026-11-26, sin retornos)
Correlación de rangos con el rendimiento operativo (1 = value puro):

| Variante | Correlación | Q1 en el quintil más barato |
|---|---|---|
| Brecha (base rate), principal | 0,76 | 69% |
| Brecha (4% fijo) | 0,77 | 67% |
| P(base rate) | 0,77 | 61% |
| Brecha neutral por sector | 0,61 | 56% |
| Brecha dentro de cada nivel de múltiplo | 0,05 | 20% (por construcción) |

La métrica principal está muy cargada de value: la condición 2 es exigente y es la que va a decidir.

## Cambios a este pre-registro
| Fecha | Cambio | ¿Antes de ver resultados? |
|---|---|---|
| 2026-11-26 | Universo sin deslistadas; se agrega como referencia el promedio con pesos iguales del universo. | Sí |
| 2026-11-26 | Rebalanceo anual y costos de 20 pb por lado confirmados por el usuario. | Sí |
| 2026-11-26 | En el backtest, consenso año 1 reemplazado por el crecimiento real de ventas del último ejercicio (SEC). | Sí |

## Resultado (2026-11-26) — no se modificó nada de lo anterior
Período 2016-05 a 2026-11. **No aprobado: no cumple ninguna condición.**
- Condición 1: Q1 > SPY en 3 de 9 años (hacía falta la mayoría). Q1 13.1% anual vs SPY 14.3% y universo 12.1%.
- Condición 2a: alfa -0.75% anual, t = -0.56 (hacía falta > 0 y t ≥ 2).
- Condición 2b: Q1 > Q5 en 2 de 5 niveles de múltiplo (hacían falta 3).
Detalle en resultados/backtest_v1.html.

## Extensión v1b (fijada el 2026-11-26, antes de correr)
Pedido del usuario: más historia y RSP como referencia.
- **Período:** desde abril de 2010 (primer balance XBRL de la SEC con comparativos de 2007-2009; no hay fundamentals
  estructurados gratis antes de 2009, así que 20 años no son posibles). Hasta noviembre de 2026.
- **Prueba fuera de muestra:** el tramo **2010-04 a 2016-04 no fue visto**. Se le aplica el mismo criterio de éxito
  (condiciones 1, 2a y 2b) y se reporta por separado. El veredicto del tramo 2016-2026 no cambia.
- **RSP (S&P 500 con pesos iguales):** se agrega como referencia. Para 2016-2026 es posterior a ver los resultados;
  para 2010-2016 queda fijado ahora. La condición 1 se evalúa contra SPY (como estaba) y se reporta también contra RSP.
- **Sin cambios** en la métrica, la cartera, el rebalanceo, los costos ni las variantes.
- Ajuste técnico necesario: en 2010-2011 hay menos historia por compañía, así que la tasa de inversión acepta ventanas
  de 2 años (antes, mínimo 3) y el crecimiento previo de 3 años puede faltar (el base rate usa solo el tamaño).

## Resultado de la extensión v1b (2026-11-26)
**No aprobado en ningún tramo.**
| Condición | 2010-2016 (fuera de muestra) | 2016-2026 | Completo |
|---|---|---|---|
| 1. Q1 > SPY (años) | 3 de 5 — cumple | 3 de 9 — no | 7 de 15 — no |
| 2a. Alfa anual (t) | 1.73% (1.22) — no | -0.65% (-0.49) — no | 0.50% (0.47) — no |
| 2b. Doble orden (niveles) | 4 de 5 — cumple | 1 de 5 — no | 4 de 5 — cumple |
| Referencia: alfa Q1 − RSP (t) | 1.26% (1.13) | 1.37% (1.38) | 1.49% (1.78) |
