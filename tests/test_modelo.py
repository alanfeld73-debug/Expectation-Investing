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
