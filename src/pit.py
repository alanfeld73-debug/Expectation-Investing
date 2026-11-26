"""Base point-in-time de fundamentals (SEC companyfacts) para el universo.

Uso:  python pit.py            -> descarga (con caché) y arma data/pit/facts.parquet

Cada fila es un dato tal como fue presentado: (cik, ticker, campo, tag, unidad, inicio, cierre, valor,
formulario, fy, fp, fecha de presentación, accn). El campo `filed` permite reconstruir qué sabía el
mercado en cada fecha (sin look-ahead): para una fecha D, usar solo filas con filed <= D.
Desde 2012 en adelante (fecha de cierre).
"""
import os
import sys

import pandas as pd

import sec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "pit", "facts.parquet")
UNIVERSO = os.path.join(ROOT, "data", "universo", "constituents.csv")
DESDE = "2012-01-01"

# campo normalizado -> tags XBRL en orden de prioridad (se guardan todos; la prioridad se aplica al usar)
CAMPOS = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
                "RevenueFromContractWithCustomerIncludingAssessedTax", "RevenuesNetOfInterestExpense"],
    "ebit": ["OperatingIncomeLoss"],
    "pretax": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
               "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
               "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic"],
    "tax": ["IncomeTaxExpenseBenefit"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
              "PaymentsForCapitalImprovements"],
    "da": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
           "DepreciationAmortizationAndAccretionNet", "Depreciation"],
    "acquisitions": ["PaymentsToAcquireBusinessesNetOfCashAcquired"],
    "sbc": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
    "assets_cur": ["AssetsCurrent"],
    "liab_cur": ["LiabilitiesCurrent"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue",
             "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "st_invest": ["ShortTermInvestments", "MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesDebtSecuritiesCurrent"],
    "debt_cur": ["LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings", "CommercialPaper"],
    "debt_lt": ["LongTermDebtNoncurrent", "LongTermDebt", "LongTermDebtAndCapitalLeaseObligations"],
    "equity": ["StockholdersEquity",
               "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "shares_dil": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
}
TAG2CAMPO = {t: c for c, tags in CAMPOS.items() for t in tags}
DEI = {"EntityCommonStockSharesOutstanding": "shares_out"}


def extraer(cik, ticker):
    facts = sec.companyfacts(cik)["facts"]
    rows = []
    for tax, mapa in (("us-gaap", TAG2CAMPO), ("dei", DEI)):
        for tag, campo in mapa.items():
            for unit, items in facts.get(tax, {}).get(tag, {}).get("units", {}).items():
                for x in items:
                    if x["end"] < DESDE:
                        continue
                    rows.append((cik, ticker, campo, tag, unit, x.get("start"), x["end"], x["val"],
                                 x.get("form"), x.get("fy"), x.get("fp"), x.get("filed"), x.get("accn")))
    return rows


def universo():
    u = pd.read_csv(UNIVERSO)
    u = u.rename(columns={"Symbol": "ticker", "Security": "nombre", "GICS Sector": "sector",
                          "GICS Sub-Industry": "subindustria", "CIK": "cik"})
    return u[["ticker", "nombre", "sector", "subindustria", "cik"]]


def main():
    u = universo()
    rows, fallas = [], []
    for i, r in enumerate(u.itertuples(), 1):
        try:
            rows += extraer(int(r.cik), r.ticker)
        except Exception as e:
            fallas.append((r.ticker, str(e)[:80]))
        if i % 50 == 0:
            print(f"[pit] {i}/{len(u)}", flush=True)
    df = pd.DataFrame(rows, columns=["cik", "ticker", "campo", "tag", "unit", "start", "end", "val", "form",
                                     "fy", "fp", "filed", "accn"])
    for c in ("start", "end", "filed"):
        df[c] = pd.to_datetime(df[c])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"[pit] {len(df):,} filas, {df.ticker.nunique()} compañías -> {OUT}")
    if fallas:
        print(f"[pit] fallas ({len(fallas)}):", fallas)
    return df


if __name__ == "__main__":
    sys.exit(0 if main() is not None else 1)
