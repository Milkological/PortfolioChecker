import pytest

from portfolio_checker.contributions import (
    cumulative_contributions,
    initial_portfolio_value,
    total_dividend_income_monthly,
)


def test_initial_portfolio_value_basic_sum():
    shares = {"A": 10.0, "B": 2.0}
    prices = {"A": 100.0, "B": 50.0}
    assert initial_portfolio_value(shares, prices) == pytest.approx(1100.0)


def test_cumulative_contributions_basic():
    result = cumulative_contributions(initial_investment=1000.0, total_monthly_dca=100.0, months=3)
    assert result == pytest.approx([1000.0, 1100.0, 1200.0, 1300.0])


def test_cumulative_contributions_zero_dca_stays_flat():
    result = cumulative_contributions(initial_investment=500.0, total_monthly_dca=0.0, months=3)
    assert result == pytest.approx([500.0, 500.0, 500.0, 500.0])


def test_cumulative_contributions_zero_months_returns_single_value():
    result = cumulative_contributions(initial_investment=500.0, total_monthly_dca=100.0, months=0)
    assert result == pytest.approx([500.0])


def test_total_dividend_income_monthly_sums_across_tickers():
    dividend_income = {"A": [0.0, 10.0, 10.0], "B": [0.0, 0.0, 0.0]}
    result = total_dividend_income_monthly(dividend_income, ["A", "B"], months=2)
    assert result == pytest.approx([0.0, 10.0, 10.0])
