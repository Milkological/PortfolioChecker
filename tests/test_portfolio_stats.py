from datetime import date

from portfolio_checker.portfolio_stats import (
    breakdown_by_attribute,
    annualised_volatility,
    correlation,
    correlation_pairs,
    effective_holdings,
    herfindahl_index,
    max_drawdown,
    month_end_prices,
    monthly_returns,
    position_values,
    weights_by_attribute,
)
from portfolio_checker.report_builder import TickerInput


def series(prices, start_year=2020):
    """Build a monthly (date, close) series from a list of prices."""
    out = []
    year, month = start_year, 1
    for price in prices:
        out.append((date(year, month, 28), float(price)))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return out


def test_month_end_prices_keeps_the_last_close_of_each_month():
    price_series = [
        (date(2020, 1, 5), 10.0),
        (date(2020, 1, 30), 12.0),
        (date(2020, 2, 10), 14.0),
    ]

    assert month_end_prices(price_series) == {(2020, 1): 12.0, (2020, 2): 14.0}


def test_monthly_returns_computes_month_over_month_change():
    returns = monthly_returns(series([100.0, 110.0, 99.0]))

    assert round(returns[(2020, 2)], 6) == 0.1
    assert round(returns[(2020, 3)], 6) == -0.1


def test_monthly_returns_is_empty_for_a_single_point():
    assert monthly_returns(series([100.0])) == {}


def test_correlation_of_identical_series_is_one():
    prices = [100, 110, 105, 120, 118, 130, 125, 140, 138, 150, 147, 160, 155]
    returns = monthly_returns(series(prices))

    assert round(correlation(returns, returns), 6) == 1.0


def test_correlation_of_mirrored_series_is_minus_one():
    up = monthly_returns(series([100, 110, 105, 120, 118, 130, 125, 140, 138, 150, 147, 160, 155]))
    down = {key: -value for key, value in up.items()}

    assert round(correlation(up, down), 6) == -1.0


def test_correlation_needs_a_year_of_overlap():
    short = monthly_returns(series([100, 110, 120]))

    assert correlation(short, short) is None


def test_correlation_is_none_for_a_flat_series():
    flat = monthly_returns(series([100] * 14))

    assert correlation(flat, flat) is None


def test_correlation_pairs_are_sorted_strongest_first():
    rising = [100, 110, 105, 120, 118, 130, 125, 140, 138, 150, 147, 160, 155]
    falling = [100, 90, 95, 80, 82, 70, 75, 60, 62, 50, 53, 40, 45]

    pairs = correlation_pairs(
        {"UP": series(rising), "ALSO_UP": series(rising), "DOWN": series(falling)}
    )

    assert pairs[0][2] > pairs[-1][2]
    assert {pairs[0][0], pairs[0][1]} == {"UP", "ALSO_UP"}


def test_correlation_pairs_skips_tickers_without_history():
    pairs = correlation_pairs({"A": series([100, 110, 120]), "B": []})

    assert pairs == []


def test_max_drawdown_measures_peak_to_trough():
    assert round(max_drawdown(series([100, 120, 60, 80])), 6) == 0.5


def test_max_drawdown_is_zero_for_a_rising_series():
    assert max_drawdown(series([100, 110, 120])) == 0.0


def test_max_drawdown_of_empty_series_is_zero():
    assert max_drawdown([]) == 0.0


def test_annualised_volatility_is_zero_for_a_flat_series():
    assert annualised_volatility(series([100] * 13)) == 0.0


def test_annualised_volatility_is_positive_when_prices_move():
    assert annualised_volatility(series([100, 120, 90, 130, 85, 140])) > 0


def test_herfindahl_index_of_a_single_position_is_one():
    assert herfindahl_index([1000.0]) == 1.0


def test_herfindahl_index_of_four_even_positions():
    assert round(herfindahl_index([25.0, 25.0, 25.0, 25.0]), 6) == 0.25


def test_herfindahl_index_of_nothing_is_zero():
    assert herfindahl_index([]) == 0.0
    assert herfindahl_index([0.0, 0.0]) == 0.0


def test_effective_holdings_counts_even_positions():
    assert round(effective_holdings([25.0, 25.0, 25.0, 25.0]), 6) == 4.0


def test_effective_holdings_penalises_concentration():
    assert effective_holdings([90.0, 5.0, 5.0]) < 2.0


def test_position_values_multiply_shares_by_price():
    inputs = [TickerInput("A", 10.0, 5.0, 0.0, 0.0, 0.0)]

    assert position_values(inputs) == {"A": 50.0}


def test_weights_by_attribute_groups_and_sorts():
    inputs = [
        TickerInput("A", 10.0, 10.0, 0.0, 0.0, 0.0, sector="Financials"),
        TickerInput("B", 10.0, 5.0, 0.0, 0.0, 0.0, sector="Financials"),
        TickerInput("C", 10.0, 5.0, 0.0, 0.0, 0.0, sector="Energy"),
    ]

    weights = weights_by_attribute(inputs, "sector")

    assert list(weights) == ["Financials", "Energy"]
    assert round(weights["Financials"], 6) == 0.75


def test_weights_by_attribute_labels_missing_values():
    inputs = [TickerInput("A", 10.0, 10.0, 0.0, 0.0, 0.0)]

    assert weights_by_attribute(inputs, "sector") == {"Unknown": 1.0}


def test_weights_by_attribute_is_empty_for_a_worthless_portfolio():
    inputs = [TickerInput("A", 0.0, 0.0, 0.0, 0.0, 0.0, sector="Financials")]

    assert weights_by_attribute(inputs, "sector") == {}


def test_breakdown_by_attribute_groups_value_and_tickers():
    inputs = [
        TickerInput("A", 10.0, 10.0, 0.0, 0.0, 0.0, sector="Financials"),
        TickerInput("B", 10.0, 5.0, 0.0, 0.0, 0.0, sector="Financials"),
        TickerInput("C", 10.0, 5.0, 0.0, 0.0, 0.0, sector="Energy"),
    ]

    groups = breakdown_by_attribute(inputs, "sector")

    assert groups[0]["key"] == "Financials"
    assert groups[0]["value"] == 150.0
    assert round(groups[0]["weight"], 6) == 0.75
    assert groups[0]["tickers"] == ["A", "B"]


def test_breakdown_by_attribute_labels_missing_values():
    inputs = [TickerInput("A", 1.0, 10.0, 0.0, 0.0, 0.0)]

    groups = breakdown_by_attribute(inputs, "industry", unknown_label="Unclassified")

    assert groups[0]["key"] == "Unclassified"


def test_breakdown_by_attribute_handles_a_worthless_portfolio():
    inputs = [TickerInput("A", 0.0, 0.0, 0.0, 0.0, 0.0, sector="Financials")]

    groups = breakdown_by_attribute(inputs, "sector")

    assert groups[0]["weight"] == 0.0


def test_breakdown_by_attribute_is_empty_for_no_holdings():
    assert breakdown_by_attribute([], "sector") == []
