import pytest

from portfolio_checker.finance_math import annual_rate_to_periodic_rate, compute_cagr


def test_compute_cagr_happy_path():
    # Price doubles over 10 years -> CAGR = 2**(1/10) - 1
    result = compute_cagr(start_price=100.0, end_price=200.0, years=10.0)
    assert result == pytest.approx(2 ** (1 / 10) - 1)


def test_compute_cagr_zero_years_raises():
    with pytest.raises(ValueError):
        compute_cagr(start_price=100.0, end_price=200.0, years=0)


def test_compute_cagr_negative_years_raises():
    with pytest.raises(ValueError):
        compute_cagr(start_price=100.0, end_price=200.0, years=-5)


def test_compute_cagr_zero_start_price_raises():
    with pytest.raises(ValueError):
        compute_cagr(start_price=0.0, end_price=200.0, years=10.0)


def test_compute_cagr_negative_start_price_raises():
    with pytest.raises(ValueError):
        compute_cagr(start_price=-10.0, end_price=200.0, years=10.0)


def test_compute_cagr_negative_growth():
    # Price halves over 5 years -> CAGR = 0.5**(1/5) - 1 (negative)
    result = compute_cagr(start_price=200.0, end_price=100.0, years=5.0)
    assert result == pytest.approx(0.5 ** (1 / 5) - 1)
    assert result < 0


def test_annual_rate_to_periodic_rate_round_trip():
    annual_rate = 0.12
    monthly_rate = annual_rate_to_periodic_rate(annual_rate, periods_per_year=12)
    assert (1 + monthly_rate) ** 12 - 1 == pytest.approx(annual_rate)


def test_annual_rate_to_periodic_rate_zero_periods_raises():
    with pytest.raises(ValueError):
        annual_rate_to_periodic_rate(0.12, periods_per_year=0)


def test_annual_rate_to_periodic_rate_negative_periods_raises():
    with pytest.raises(ValueError):
        annual_rate_to_periodic_rate(0.12, periods_per_year=-1)
