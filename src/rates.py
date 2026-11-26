"""Tasa libre de riesgo: UST 10 años (FRED DGS10), con caché en data/rates/DGS10.csv.

rf10() -> (tasa decimal, fecha del dato, fuente). Sin red, usa el último valor cacheado;
sin caché, cae al valor de respaldo RF_FALLBACK y lo indica en la fuente."""
import os
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "rates", "DGS10.csv")
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"
RF_FALLBACK = (0.0485, None, "respaldo fijo (sin FRED ni caché)")


def _parse(text):
    """Último dato válido del CSV de FRED (las fechas sin dato vienen como '.' o vacías)."""
    for line in reversed(text.strip().splitlines()[1:]):
        date, _, val = line.partition(",")
        try:
            return float(val) / 100, date
        except ValueError:
            continue
    return None


def rf10(max_age_hours=12):
    fresh = os.path.exists(PATH) and (time.time() - os.path.getmtime(PATH)) < max_age_hours * 3600
    if not fresh:
        try:
            # Sin User-Agent propio: FRED corta UAs desconocidos o de navegador falsos, acepta el de urllib.
            text = urllib.request.urlopen(URL, timeout=30).read().decode()
            if _parse(text):
                os.makedirs(os.path.dirname(PATH), exist_ok=True)
                with open(PATH + ".tmp", "w") as f:
                    f.write(text)
                os.replace(PATH + ".tmp", PATH)
        except Exception as e:
            print(f"[rates] FRED no disponible ({e}); se usa el caché si existe")
    if os.path.exists(PATH):
        with open(PATH) as f:
            p = _parse(f.read())
        if p:
            return p[0], p[1], "FRED DGS10"
    return RF_FALLBACK
