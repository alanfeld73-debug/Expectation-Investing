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
