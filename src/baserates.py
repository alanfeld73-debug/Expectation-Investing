"""Base rates de crecimiento de ventas a 10 años (Mauboussin, The Base Rate Book).
Fuente: SEC XBRL frames (todas las compañías que reportan a la SEC), CY2015 -> CY2025.
Sesgo de supervivencia: solo entran compañías que siguen reportando en 2025.

User-Agent de la SEC: config.SEC_USER_AGENT (sobreescribible por variable de entorno).
Caché: data/sec_frames/ en la raíz del proyecto."""
import glob
import json
import os
import time
import urllib.request

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "data", "sec_frames")
YEARS = (2012, 2015, 2022, 2025)
CONCEPTS = ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet")
BUCK = [(1e8, 5e8), (5e8, 2e9), (2e9, 1e10), (1e10, 5e10), (5e10, 1e13)]
PRIOR = [(-1, 0), (0, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 10)]


def _user_agent():
    from config import SEC_USER_AGENT
    return SEC_USER_AGENT


def _download():
    os.makedirs(DIR, exist_ok=True)
    for y in YEARS:
        for c in CONCEPTS:
            p = os.path.join(DIR, f"{c}_{y}.json")
            if os.path.exists(p) and os.path.getsize(p) > 0:
                continue
            req = urllib.request.Request(f"https://data.sec.gov/api/xbrl/frames/us-gaap/{c}/USD/CY{y}.json",
                                         headers={"User-Agent": _user_agent()})
            try:
                body = urllib.request.urlopen(req, timeout=60).read()
            except Exception as e:  # concepto inexistente para ese año (404) o red caída
                print(f"[baserates] no se pudo bajar {c} CY{y}: {e}")
                continue
            # Se escribe solo si la descarga terminó: un archivo vacío envenenaría el caché.
            tmp = p + ".tmp"
            with open(tmp, "wb") as f:
                f.write(body)
            os.replace(tmp, p)
            time.sleep(0.2)


def load(y):
    r = {}
    for f in glob.glob(os.path.join(DIR, f"*_{y}.json")):
        try:
            with open(f) as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        for x in d["data"]:
            r[x["cik"]] = max(r.get(x["cik"], 0), x["val"])
    return r


_ROWS = None


def rows():
    """(ventas 2015, CAGR 2015-25, CAGR 2012-15 o None) por compañía. Descarga y cachea la primera vez."""
    global _ROWS
    if _ROWS is None:
        _download()
        R = {y: load(y) for y in YEARS}
        _ROWS = []
        for cik, s15 in R[2015].items():
            s25, s12 = R[2025].get(cik), R[2012].get(cik)
            if s25 and s15 > 1e8 and s25 > 0:
                _ROWS.append((s15, (s25 / s15) ** 0.1 - 1, (s15 / s12) ** (1 / 3) - 1 if s12 and s12 > 0 else None))
        if not _ROWS:
            raise RuntimeError(f"Sin datos de base rates en {DIR}: revisar descarga de la SEC.")
    return _ROWS


def dist(lo, hi, prior=None):
    return np.array([g for s, g, p in rows() if lo <= s < hi
                     and (prior is None or (p is not None and prior[0] <= p < prior[1]))])


def bucket(sales):
    for lo, hi in BUCK:
        if lo <= sales < hi:
            return lo, hi
    return None


def prob(sales, g_req, prior_g=None):
    """P(CAGR 10 años >= g_req) en compañías de tamaño similar (y crecimiento previo similar si hay n>=30).
    Devuelve (prob, n, mediana) o (None, 0, None) si las ventas caen fuera de los buckets (< USD 100 M)."""
    b = bucket(sales)
    if b is None:
        return None, 0, None
    lo, hi = b
    pr = next((x for x in PRIOR if x[0] <= prior_g < x[1]), None) if prior_g is not None else None
    d = dist(lo, hi, pr)
    if len(d) < 30:
        d = dist(lo, hi)
    return float((d >= g_req).mean()), len(d), float(np.median(d))


if __name__ == "__main__":
    print("N companies", len(rows()))
    for lo, hi in BUCK:
        d = dist(lo, hi)
        print(f"{lo/1e9:>6.1f}-{hi/1e9:<8.0f}bn n={len(d):4d} p25={np.percentile(d,25):.1%} med={np.median(d):.1%} "
              f"p75={np.percentile(d,75):.1%} p90={np.percentile(d,90):.1%}")
    for b in PRIOR:
        d = dist(1e10, 1e13, b)
        print("large, prior", b, len(d), f"{np.median(d):.1%}" if len(d) else "")
