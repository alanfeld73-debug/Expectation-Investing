"""Pasos 2 y 3 — turbina de value triggers y escenarios ponderados para la short list.
Escenario = (nombre, probabilidad, crecimiento año 1 con fade a 4%, ajustes de driver).
Las probabilidades y los parámetros son juicio del analista: editar acá."""
import io, contextlib
import expectations_screen as E

HURDLE = 0.20  # margen de seguridad exigido sobre el valor esperado

SC = {
    "BKNG": [("Bajista", 0.25, 0.00, dict(m_shift=-0.04)),   # IA desintermedia, take rate cae
             ("Base", 0.50, 0.063, {}),                      # consenso
             ("Alcista", 0.25, 0.10, dict(m_shift=0.02))],   # connected trip + apalancamiento
    "NVO":  [("Bajista", 0.30, -0.08, dict(m_shift=-0.06)),  # recortes de precio 2027 + Lilly
             ("Base", 0.45, 0.00, dict(m_shift=-0.02)),
             ("Alcista", 0.25, 0.06, {})],                   # Wegovy pill + CagriSema
    "DLO":  [("Bajista", 0.30, 0.10, dict(m_shift=-0.05)),   # take rate sigue cayendo + FX
             ("Base", 0.45, 0.25, {}),                       # guía de margen bruto
             ("Alcista", 0.25, 0.35, dict(m_shift=0.03))],   # take rate toca piso
    "NU":   [("Bajista", 0.30, 0.10, dict(roe=0.22)),        # mora sube + tasa efectiva
             ("Base", 0.45, 0.22, dict(roe=0.28)),
             ("Alcista", 0.25, 0.30, dict(roe=0.32))],       # México replica Brasil
}

if __name__ == "__main__":
    with contextlib.redirect_stdout(io.StringIO()):
        cos = E.main()
    for t, sc in SC.items():
        c = cos[t]
        print(f"\n== {t}  precio {c.price:.2f}")
        for k, v in c.turbine().items():
            print(f"   turbina {k:<22}{v:+.1%}")
        ev = 0.0
        for name, p, g1, kw in sc:
            c.g_ref = g1
            v = c.value_per_share(c.fade_path(), **kw)
            ev += p * v
            print(f"   {name:<8} p={p:.0%} g1={g1:+.1%} -> {v:8.2f} ({v / c.price - 1:+.0%})")
        verdict = "COMPRA" if ev / c.price - 1 >= HURDLE else "WATCHLIST"
        print(f"   Valor esperado {ev:.2f} ({ev / c.price - 1:+.0%}) | precio de entrada con "
              f"{HURDLE:.0%} de margen: {ev / (1 + HURDLE):.2f} | {verdict}")
