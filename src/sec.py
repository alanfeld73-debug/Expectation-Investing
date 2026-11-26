"""Acceso a la SEC (data.sec.gov / www.sec.gov) con caché en data/sec/.

- cik(ticker): mapa ticker->CIK propio (data/sec/cik_map.json), armado desde company_tickers.json
  y completado con CIK_MANUAL para lo que no figure (o si www.sec.gov está bloqueado).
- annual_revenue(cik): ventas anuales de 10-K/20-F/40-F (us-gaap o ifrs-full), en la moneda de reporte.
- revenue_cagr(ticker, years=3): CAGR de ventas de los últimos `years` ejercicios.
"""
import datetime as dt
import json
import os
import time
import urllib.request

from config import SEC_USER_AGENT

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "data", "sec")
FACTS_MAX_AGE_DAYS = 7

# Overrides manuales ticker -> CIK (agregar acá con fecha en SUPUESTOS.md).
CIK_MANUAL: dict[str, int] = {}

REVENUE_CONCEPTS = [
    ("us-gaap", "Revenues"),
    ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
    ("us-gaap", "SalesRevenueNet"),
    ("us-gaap", "RevenueFromContractWithCustomerIncludingAssessedTax"),
    ("ifrs-full", "Revenue"),
]
ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": SEC_USER_AGENT})
    body = urllib.request.urlopen(req, timeout=60).read()
    time.sleep(0.12)  # SEC: máximo 10 requests/segundo
    return body


def _cached_json(path, url, max_age_days):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        age = (time.time() - os.path.getmtime(path)) / 86400
        if age <= max_age_days:
            with open(path) as f:
                return json.load(f)
    try:
        body = _get(url)
    except Exception:
        if os.path.exists(path) and os.path.getsize(path) > 0:  # sin red: usar el caché viejo
            with open(path) as f:
                return json.load(f)
        raise
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(body)
    os.replace(tmp, path)
    return json.loads(body)


_MAP = None


def cik_map():
    global _MAP
    if _MAP is None:
        path = os.path.join(DIR, "cik_map.json")
        try:
            raw = _cached_json(os.path.join(DIR, "company_tickers.json"),
                               "https://www.sec.gov/files/company_tickers.json", 30)
            _MAP = {v["ticker"].upper(): int(v["cik_str"]) for v in raw.values()}
            with open(path, "w") as f:
                json.dump(_MAP, f)
        except Exception:
            _MAP = json.load(open(path)) if os.path.exists(path) else {}
        _MAP.update(CIK_MANUAL)
    return _MAP


def cik(ticker):
    return cik_map().get(ticker.upper())


def companyfacts(cik_):
    return _cached_json(os.path.join(DIR, f"companyfacts_{cik_:010d}.json"),
                        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_:010d}.json", FACTS_MAX_AGE_DAYS)


def _annual_series(items):
    """{fecha de cierre: valor} con duración ~1 año en formularios anuales; si hay re-expresiones,
    gana la presentación más reciente."""
    out = {}
    for x in items:
        if x.get("form") not in ANNUAL_FORMS or "start" not in x:
            continue
        days = (dt.date.fromisoformat(x["end"]) - dt.date.fromisoformat(x["start"])).days
        if not 350 <= days <= 380:
            continue
        prev = out.get(x["end"])
        if prev is None or x["filed"] > prev[1]:
            out[x["end"]] = (x["val"], x["filed"])
    return {k: v for k, (v, _) in out.items()}


def annual_revenue(cik_):
    """Serie anual de ventas del concepto con el dato más reciente. Devuelve ({cierre: valor}, concepto, moneda)."""
    facts = companyfacts(cik_)["facts"]
    best = ({}, None, None)
    for tax, concept in REVENUE_CONCEPTS:
        units = facts.get(tax, {}).get(concept, {}).get("units", {})
        for cur, items in units.items():
            s = _annual_series(items)
            if s and (not best[0] or max(s) > max(best[0]) or (max(s) == max(best[0]) and len(s) > len(best[0]))):
                best = (s, f"{tax}:{concept}", cur)
    return best


def revenue_cagr(ticker, years=3):
    """CAGR de ventas de los últimos `years` ejercicios según la SEC. None si no hay datos suficientes."""
    c = cik(ticker)
    if c is None:
        return None
    try:
        s, _, _ = annual_revenue(c)
    except Exception:
        return None
    if not s:
        return None
    last = max(s)
    last_d = dt.date.fromisoformat(last)
    # Ejercicio de `years` años antes: cierre más cercano a la misma fecha (±45 días).
    target = last_d.replace(year=last_d.year - years)
    cands = [k for k in s if abs((dt.date.fromisoformat(k) - target).days) <= 45]
    if not cands:
        return None
    first = min(cands, key=lambda k: abs((dt.date.fromisoformat(k) - target).days))
    if s[first] <= 0 or s[last] <= 0:
        return None
    return (s[last] / s[first]) ** (1 / years) - 1
