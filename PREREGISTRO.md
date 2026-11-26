# Pre-registro del backtest v1

Fijado el 2026-11-26, **antes de ver cualquier resultado del backtest**. Cambiar algo de este archivo después
de ver resultados invalida la prueba: si se cambia, se anota la fecha, el motivo y que fue posterior.

## Pregunta
¿El quintil de mayor brecha de expectativas le gana al SPY después de costos, y no se explica solo por value?

## Estrategia principal (la única que decide)
- **Métrica:** brecha = valor por acción / precio - 1, con crecimiento año 1 = consenso y desaceleración lineal
  hasta la mediana del base rate de su tamaño y crecimiento previo en el año 10; residual NOPAT/WACC.
- **Cartera:** quintil 1 de brecha, pesos iguales, dentro del universo S&P 500 vigente en cada fecha
  (composición histórica, sin sesgo de supervivencia). Excluye las marcadas `[revisar]`.
- **Rebalanceo:** anual. *Propuesto, a confirmar por el usuario antes de correr.*
- **Costos:** 20 pb por lado sobre el volumen operado. *Propuesto, a confirmar.*
- **Período:** desde que la base point-in-time permite calcular la métrica (fundamentals SEC desde 2012).
- **Referencia:** SPY con dividendos reinvertidos.

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
