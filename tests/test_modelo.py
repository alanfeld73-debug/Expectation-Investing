"""Tests de las convenciones del modelo con datos sintéticos (sin red)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import expectations_screen as E  # noqa: E402


def co(**kw):
    base = dict(t="X", model="FCF", price=10.0, mcap=1000.0, sales0=1000.0, m0=0.10, tax=0.25, inv=0.20,
                wacc=0.09, ke=0.09, net_debt=0.0, g_ref=0.05, m_target=0.10, ramp=0)
    base.update(kw)
    return E.Co(**base)


def test_sin_crecimiento_es_nopat_sobre_wacc():
    c = co()
    nopat = 1000 * 0.10 * 0.75
    assert c.op_value([0.0] * E.H) == pytest.approx(nopat / 0.09)


def test_fcf_resta_inversion_incremental():
    # Un año: ventas 1000 -> 1100, FCF = NOPAT - 0,2 x 100; residual NOPAT_1 / WACC sin crecimiento.
    c = co()
    nopat1 = 1100 * 0.10 * 0.75
    esperado = (nopat1 - 0.20 * 100) / 1.09 + nopat1 / 0.09 / 1.09
    assert c.op_value([0.10]) == pytest.approx(esperado)


def test_implied_g_reproduce_el_precio():
    c = co(mcap=1500.0)
    g = c.implied_g()
    assert c.op_value([g] * E.H) == pytest.approx(c.target, rel=1e-6)


def test_ramp_converge_al_margen_objetivo():
    c = co(m0=-0.05, m_target=0.20, ramp=5)
    assert c.margin(0) == pytest.approx(-0.05)
    assert c.margin(5) == pytest.approx(0.20)
    assert c.margin(9) == pytest.approx(0.20)


def test_equity_retiene_g_sobre_roe():
    c = co(model="EQUITY", ni0=100.0, roe=0.20, ke=0.10)
    v = c.op_value([0.10])
    ni1 = 110.0
    assert v == pytest.approx(ni1 * (1 - 0.10 / 0.20) / 1.10 + ni1 / 0.10 / 1.10)


def test_mifp_cero_si_el_valor_sin_crecimiento_alcanza():
    c = co(mcap=500.0)  # valor sin crecimiento = 833
    assert c.mifp() == 0.0


def test_fade_termina_en_g_terminal():
    p = co(g_ref=0.30).fade_path()
    assert p[0] == pytest.approx(0.30) and p[-1] == pytest.approx(E.G_TERMINAL) and len(p) == E.H


def test_base_rates_no_usa_bucket_megacap_para_microcaps():
    import baserates  # importar no debe descargar nada
    assert baserates.prob(5e7, 0.10) == (None, 0, None)
    assert baserates.bucket(3e8) == (1e8, 5e8)


def test_reverse_dcf_y_screen_dan_el_mismo_valor():
    import reverse_dcf as R
    i = R.BKNG
    c = co(sales0=i.sales0, m0=i.ebit_margin, m_target=i.ebit_margin, tax=i.tax, inv=i.inv_rate, wacc=i.wacc)
    for g in (0.0, 0.05, 0.10):
        assert c.op_value([g] * E.H) == pytest.approx(R.operating_value(i, g))
    g = R.implied_growth(i)
    assert R.operating_value(i, g) == pytest.approx(i.target_op_value, rel=1e-6)


def test_rates_parsea_ultimo_dato_valido():
    import rates
    assert rates._parse("observation_date,DGS10\n2026-11-21,4.90\n2026-11-24,4.91\n2026-11-25,\n") == \
        (pytest.approx(0.0491), "2026-11-24")


def test_sec_serie_anual_filtra_trimestres_y_usa_ultima_reexpresion():
    import sec
    items = [
        dict(start="2022-01-01", end="2022-12-31", val=100, form="10-K", filed="2023-02-01"),
        dict(start="2022-01-01", end="2022-12-31", val=105, form="10-K", filed="2024-02-01"),  # re-expresado
        dict(start="2025-07-01", end="2025-09-30", val=40, form="10-Q", filed="2025-10-30"),    # trimestre
        dict(start="2025-01-01", end="2025-12-31", val=140, form="10-K", filed="2026-02-01"),
    ]
    assert sec._annual_series(items) == {"2022-12-31": 105, "2025-12-31": 140}


def test_fundamentals_tasa_impositiva_e_inversion_incremental():
    import pandas as pd
    import fundamentals as F
    rows = []
    for k, y in enumerate(range(2019, 2026)):           # 7 ejercicios, cierre 31-dic
        end, start, filed = f"{y}-12-31", f"{y}-01-01", f"{y+1}-02-15"
        ventas = 1000 * 1.10 ** k
        flujos = dict(revenue=ventas, pretax=200, tax=42, capex=80, da=50)
        saldos = dict(assets_cur=300 + 10 * k, cash=100, liab_cur=150, debt_cur=20)
        for c, v in flujos.items():
            rows.append(("X", c, c, "USD", start, end, v, "10-K", filed))
        for c, v in saldos.items():
            rows.append(("X", c, c, "USD", None, end, v, "10-K", filed))
    df = pd.DataFrame(rows, columns=["ticker", "campo", "tag", "unit", "start", "end", "val", "form", "filed"])
    for c in ("start", "end", "filed"):
        df[c] = pd.to_datetime(df[c])
    F._DF = df
    try:
        m = F.metricas_compania().set_index("ticker").loc["X"]
        assert m.tax_rate == pytest.approx(0.21)
        # Ventana 2020->2025: Σ(capex - D&A) = 5 x 30; ΔNWC = 10 x 5 = 50; Δventas = 1000 x (1,1^6 - 1,1^1)
        ds = 1000 * (1.1 ** 6 - 1.1)
        assert m.inv_rate == pytest.approx((150 + 50) / ds)
        assert m.cagr3 == pytest.approx(0.10)
        # Point-in-time: con as_of a mediados de 2024 el último ejercicio conocido es 2023
        assert F.metricas_compania(as_of="2024-06-30").set_index("ticker").loc["X"].fy_end == pd.Timestamp("2023-12-31")
    finally:
        F._DF = None


def test_fade_con_punto_de_llegada_propio():
    c = co(g_ref=0.20)
    c.g_term = 0.07
    p = c.fade_path()
    assert p[0] == pytest.approx(0.20) and p[-1] == pytest.approx(0.07)
    assert c.fade_path(12)[-1] == pytest.approx(0.07)


def test_factores_recupera_alfa_y_betas_sinteticos():
    import numpy as np
    import pandas as pd
    import factores as FF
    rng = np.random.default_rng(0)
    idx = pd.period_range("2012-01", periods=168, freq="M")
    cols = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD"]
    F = pd.DataFrame(rng.normal(0, 0.04, (len(idx), 6)), index=idx, columns=cols)
    y = 0.003 + 1.0 * F["Mkt-RF"] + 0.6 * F["HML"] + rng.normal(0, 0.005, len(idx))
    r = FF.alfa(pd.Series(y, index=idx), F)
    assert r.loc["alfa", "coef"] == pytest.approx(0.003, abs=0.0015)
    assert r.loc["HML", "coef"] == pytest.approx(0.6, abs=0.05)
    assert r.loc["alfa", "t"] > 2


def test_factores_parsea_formato_french():
    import factores as FF
    txt = ("This file was created...\n\n,Mkt-RF,SMB,HML,RF\n202401,  1.00, -0.50,  0.20, 0.40\n"
           "202402,  2.00,  0.10, -0.30, 0.42\n\n Annual Factors: January-December\n,Mkt-RF,SMB,HML,RF\n2024, 5.0, 1.0, 1.0, 5.0\n")
    df = FF._parse_mensual(txt)
    assert list(df.columns) == ["Mkt-RF", "SMB", "HML", "RF"] and len(df) == 2
    assert df.iloc[0]["Mkt-RF"] == pytest.approx(0.01)


def test_backtest_cartera_pesos_iguales_deriva_y_costos():
    import pandas as pd
    import backtest as B
    idx = pd.period_range("2020-04", periods=4, freq="M")
    R = pd.DataFrame({"A": [None, 0.10, 0.00, 0.10], "B": [None, 0.00, 0.00, -0.10]}, index=idx)
    s = B.cartera(R, [(idx[0], ["A", "B"])], "x")
    # Mes 1: (10% + 0%) / 2 = 5%, menos 20 pb de costo por comprar el 100% de la cartera
    assert s.iloc[0] == pytest.approx(0.998 * 1.05 - 1)
    # Mes 3: pesos derivados A = 1,1 / 2,1 y B = 1 / 2,1
    assert s.iloc[2] == pytest.approx((1.1 * 0.10 + 1.0 * -0.10) / 2.1)


def test_backtest_costo_por_rotacion():
    import pandas as pd
    import backtest as B
    idx = pd.period_range("2020-04", periods=3, freq="M")
    R = pd.DataFrame({"A": [None, 0.0, 0.0], "B": [None, 0.0, 0.0]}, index=idx)
    s = B.cartera(R, [(idx[0], ["A"]), (idx[1], ["B"])], "x")
    # Segundo rebalanceo: vende 100% de A y compra 100% de B -> volumen 2 x 20 pb = 40 pb
    assert s.iloc[1] == pytest.approx(-0.004)
