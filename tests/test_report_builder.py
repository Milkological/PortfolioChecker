import pytest

from portfolio_checker.report_builder import (
    TickerInput,
    build_report_data,
    portfolio_share_percentage,
    total_annual_dividend_income,
    total_portfolio_value,
    weighted_average_growth_rate,
)


def test_build_report_data_single_ticker_no_growth_no_dividends():
    inputs = [
        TickerInput(
            ticker="A",
            initial_shares=10.0,
            current_price=100.0,
            annual_growth_rate=0.0,
            annual_dividend_per_share=0.0,
            monthly_dca_amount=50.0,
        )
    ]

    total_rows, ticker_rows = build_report_data(inputs, years=1)

    assert set(ticker_rows.keys()) == {"A"}
    assert total_rows == ticker_rows["A"]  # single ticker -> total equals that ticker
    assert total_rows[0]["contributed_total"] == pytest.approx(1000.0)
    assert total_rows[1]["contributed_total"] == pytest.approx(1600.0)
    assert total_rows[1]["total_value"] == pytest.approx(1600.0)  # 0% growth, DCA only, no dividends


def test_build_report_data_multi_ticker_total_aggregates_dividends_and_growth():
    inputs = [
        TickerInput(
            ticker="A",
            initial_shares=10.0,
            current_price=100.0,
            annual_growth_rate=0.0,
            annual_dividend_per_share=12.0,
            monthly_dca_amount=0.0,
        ),
        TickerInput(
            ticker="B",
            initial_shares=5.0,
            current_price=200.0,
            annual_growth_rate=0.0,
            annual_dividend_per_share=0.0,
            monthly_dca_amount=0.0,
        ),
    ]

    total_rows, ticker_rows = build_report_data(inputs, years=1)

    # A: $12/share/year dividend ($1/month equivalent), not reinvested (sits as cash), so shares
    # stay flat at 10 and dividend income is a flat $10/month * 12 months = $120 for the year.
    assert ticker_rows["A"][1]["dividend_income"] == pytest.approx(120.0)
    assert ticker_rows["B"][1]["dividend_income"] == pytest.approx(0.0)
    # total dividend income = sum across tickers
    assert total_rows[1]["dividend_income"] == pytest.approx(120.0)
    # total contributed = 1000 (A) + 1000 (B), unchanged (no DCA)
    assert total_rows[0]["contributed_total"] == pytest.approx(2000.0)
    assert total_rows[1]["contributed_total"] == pytest.approx(2000.0)


def test_total_annual_dividend_income_sums_shares_times_rate():
    inputs = [
        TickerInput("A", 10.0, 100.0, 0.0, 12.0, 0.0),
        TickerInput("B", 5.0, 200.0, 0.0, 24.0, 0.0),
    ]

    assert total_annual_dividend_income(inputs) == pytest.approx(10 * 12.0 + 5 * 24.0)


def test_total_portfolio_value_sums_shares_times_price():
    inputs = [
        TickerInput("A", 10.0, 100.0, 0.0, 0.0, 0.0),
        TickerInput("B", 5.0, 200.0, 0.0, 0.0, 0.0),
    ]

    assert total_portfolio_value(inputs) == pytest.approx(10 * 100.0 + 5 * 200.0)


def test_portfolio_share_percentage_basic():
    assert portfolio_share_percentage(250.0, 1000.0) == pytest.approx(25.0)


def test_portfolio_share_percentage_zero_total_returns_zero():
    assert portfolio_share_percentage(250.0, 0.0) == pytest.approx(0.0)


def test_ticker_input_dividend_history_defaults_to_empty_list():
    t = TickerInput("A", 10.0, 100.0, 0.0, 0.0, 0.0)
    assert t.dividend_history == []


def test_ticker_input_dividend_history_can_be_set_explicitly():
    from datetime import date

    history = [(date(2026, 1, 1), 0.5)]
    t = TickerInput("A", 10.0, 100.0, 0.0, 0.0, 0.0, dividend_history=history)
    assert t.dividend_history == history


def test_weighted_average_growth_rate_weights_by_position_value():
    inputs = [
        TickerInput("A", 10.0, 100.0, 0.10, 0.0, 0.0),  # position value 1000, weight 2/3
        TickerInput("B", 10.0, 50.0, 0.40, 0.0, 0.0),  # position value 500, weight 1/3
    ]

    # weighted average = (1000*0.10 + 500*0.40) / 1500 = 0.20
    assert weighted_average_growth_rate(inputs) == pytest.approx(0.20)


def test_weighted_average_growth_rate_zero_total_value_returns_zero():
    inputs = [TickerInput("A", 0.0, 100.0, 0.10, 0.0, 0.0)]

    assert weighted_average_growth_rate(inputs) == pytest.approx(0.0)
