import pytest

from portfolio_checker.finance_math import annual_rate_to_periodic_rate
from portfolio_checker.simulation import TickerConfig, compute_dividend_cash, simulate_month, simulate_portfolio


def test_compute_dividend_cash_multi_ticker():
    # annualized rates (12.0/year, 24.0/year) must convert to the same monthly cash
    # as the old monthly rates (1.0/month, 2.0/month) did.
    configs = {
        "A": TickerConfig("A", 10.0, 0.0, 0.0, 12.0, "CASH"),
        "B": TickerConfig("B", 5.0, 0.0, 0.0, 24.0, "CASH"),
    }
    shares = {"A": 10.0, "B": 5.0}

    dividend_cash = compute_dividend_cash(shares, configs)

    assert dividend_cash == pytest.approx({"A": 10.0, "B": 10.0})


def test_simulate_month_growth_only():
    configs = {
        "A": TickerConfig(
            ticker="A",
            initial_shares=10.0,
            annual_growth_rate=0.12,
            monthly_dca_amount=0.0,
            annual_dividend_per_share=0.0,
            dividend_reinvest_target=None,
        )
    }
    shares = {"A": 10.0}
    prices = {"A": 100.0}
    cash = 0.0

    new_shares, new_prices, new_cash = simulate_month(shares, prices, cash, configs)

    monthly_rate = annual_rate_to_periodic_rate(0.12, 12)
    assert new_prices["A"] == pytest.approx(100.0 * (1 + monthly_rate))
    assert new_shares["A"] == pytest.approx(10.0)
    assert new_cash == pytest.approx(0.0)


def test_simulate_month_dca_only_at_zero_growth():
    configs = {
        "A": TickerConfig(
            ticker="A",
            initial_shares=10.0,
            annual_growth_rate=0.0,
            monthly_dca_amount=50.0,
            annual_dividend_per_share=0.0,
            dividend_reinvest_target=None,
        )
    }
    shares = {"A": 10.0}
    prices = {"A": 100.0}
    cash = 0.0

    new_shares, new_prices, new_cash = simulate_month(shares, prices, cash, configs)

    # 0% growth -> price unchanged, so DCA buys $50 / $100 = 0.5 new shares
    assert new_prices["A"] == pytest.approx(100.0)
    assert new_shares["A"] == pytest.approx(10.5)
    assert new_cash == pytest.approx(0.0)


def test_simulate_month_multi_ticker_independent_rates():
    configs = {
        "A": TickerConfig("A", 10.0, 0.12, 0.0, 0.0, None),
        "B": TickerConfig("B", 5.0, 0.06, 0.0, 0.0, None),
    }
    shares = {"A": 10.0, "B": 5.0}
    prices = {"A": 100.0, "B": 200.0}
    cash = 0.0

    new_shares, new_prices, new_cash = simulate_month(shares, prices, cash, configs)

    rate_a = annual_rate_to_periodic_rate(0.12, 12)
    rate_b = annual_rate_to_periodic_rate(0.06, 12)
    assert new_prices["A"] == pytest.approx(100.0 * (1 + rate_a))
    assert new_prices["B"] == pytest.approx(200.0 * (1 + rate_b))
    assert new_shares["A"] == pytest.approx(10.0)
    assert new_shares["B"] == pytest.approx(5.0)


def test_simulate_month_dividend_reinvested_into_self():
    configs = {
        "A": TickerConfig(
            ticker="A",
            initial_shares=10.0,
            annual_growth_rate=0.0,
            monthly_dca_amount=0.0,
            annual_dividend_per_share=12.0,
            dividend_reinvest_target="A",
        )
    }
    shares = {"A": 10.0}
    prices = {"A": 100.0}
    cash = 0.0

    new_shares, new_prices, new_cash = simulate_month(shares, prices, cash, configs)

    # dividend cash = 10 shares * $1/share = $10, reinvested at post-growth price ($100, 0% growth)
    assert new_prices["A"] == pytest.approx(100.0)
    assert new_shares["A"] == pytest.approx(10.0 + 10.0 / 100.0)
    assert new_cash == pytest.approx(0.0)


def test_simulate_month_dividend_reinvested_into_another_ticker():
    configs = {
        "A": TickerConfig("A", 10.0, 0.0, 0.0, 12.0, "B"),
        "B": TickerConfig("B", 5.0, 0.0, 0.0, 0.0, None),
    }
    shares = {"A": 10.0, "B": 5.0}
    prices = {"A": 100.0, "B": 50.0}
    cash = 0.0

    new_shares, new_prices, new_cash = simulate_month(shares, prices, cash, configs)

    # A's dividend cash = 10 * ($12/yr / 12) = $10, buys $10 / $50 = 0.2 shares of B
    assert new_shares["A"] == pytest.approx(10.0)
    assert new_shares["B"] == pytest.approx(5.2)
    assert new_cash == pytest.approx(0.0)


def test_simulate_month_dividend_not_reinvested_goes_to_cash():
    configs = {
        "A": TickerConfig("A", 10.0, 0.0, 0.0, 12.0, "CASH"),
    }
    shares = {"A": 10.0}
    prices = {"A": 100.0}
    cash = 0.0

    new_shares, new_prices, new_cash = simulate_month(shares, prices, cash, configs)

    assert new_shares["A"] == pytest.approx(10.0)
    assert new_cash == pytest.approx(10.0)


def test_simulate_month_zero_dividend_ticker_contributes_nothing():
    configs = {
        "A": TickerConfig("A", 10.0, 0.0, 0.0, 0.0, "CASH"),
    }
    shares = {"A": 10.0}
    prices = {"A": 100.0}
    cash = 0.0

    new_shares, new_prices, new_cash = simulate_month(shares, prices, cash, configs)

    assert new_shares["A"] == pytest.approx(10.0)
    assert new_cash == pytest.approx(0.0)


def test_simulate_month_invalid_reinvest_target_raises():
    configs = {
        "A": TickerConfig("A", 10.0, 0.0, 0.0, 12.0, "DOES_NOT_EXIST"),
    }
    shares = {"A": 10.0}
    prices = {"A": 100.0}
    cash = 0.0

    with pytest.raises(ValueError):
        simulate_month(shares, prices, cash, configs)


def test_simulate_portfolio_two_months_growth_and_dca():
    configs = [
        TickerConfig("A", 10.0, 0.0, 50.0, 0.0, None),
    ]
    initial_prices = {"A": 100.0}

    result = simulate_portfolio(configs, initial_prices, months=2)

    # 0% growth, price stays $100 the whole time; DCA adds 0.5 shares/month
    assert result.ticker_values["A"] == pytest.approx([1000.0, 1050.0, 1100.0])
    assert result.cash_balance == pytest.approx([0.0, 0.0, 0.0])
    assert result.total_value == pytest.approx([1000.0, 1050.0, 1100.0])


def test_simulate_portfolio_tracks_dividend_income_per_ticker():
    configs = [
        TickerConfig("A", 10.0, 0.0, 0.0, 12.0, "CASH"),
        TickerConfig("B", 5.0, 0.0, 0.0, 0.0, "CASH"),
    ]
    initial_prices = {"A": 100.0, "B": 50.0}

    result = simulate_portfolio(configs, initial_prices, months=2)

    # month 0 (initial snapshot) has no dividend yet; months 1-2 each pay $10 for A, $0 for B
    assert result.dividend_income["A"] == pytest.approx([0.0, 10.0, 10.0])
    assert result.dividend_income["B"] == pytest.approx([0.0, 0.0, 0.0])


def test_simulate_portfolio_zero_months_returns_single_snapshot():
    configs = [
        TickerConfig("A", 10.0, 0.12, 50.0, 0.0, None),
    ]
    initial_prices = {"A": 100.0}

    result = simulate_portfolio(configs, initial_prices, months=0)

    assert result.ticker_values["A"] == pytest.approx([1000.0])
    assert result.cash_balance == pytest.approx([0.0])
    assert result.total_value == pytest.approx([1000.0])
