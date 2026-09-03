from portfolio_checker.dashboard_app import (
    build_chart_for_selection,
    chart_title_for_tickers,
    row_style_for_selection,
    select_chart_tickers,
    toggle_display_style,
)
from portfolio_checker.report_builder import TickerInput


def test_build_chart_for_selection_uses_given_title():
    inputs = [
        TickerInput("A", 10.0, 100.0, 0.0, 0.0, 50.0),
        TickerInput("B", 5.0, 200.0, 0.0, 0.0, 0.0),
    ]

    fig = build_chart_for_selection(inputs, years=1, currency="USD", title="Total Portfolio")

    assert fig.layout.title.text == "Total Portfolio"


def test_build_chart_for_selection_single_ticker_subset():
    inputs = [TickerInput("A", 10.0, 100.0, 0.0, 0.0, 50.0)]

    fig = build_chart_for_selection(inputs, years=1, currency="USD", title="A")

    assert fig.layout.title.text == "A"
    # A's total value line should reflect only A's own contributions (1000 initial + 600 DCA)
    total_trace = fig.data[-1]
    assert list(total_trace.y) == [1000.0, 1600.0]


def test_toggle_display_style_opens_when_closed():
    assert toggle_display_style({"display": "none"}) == {"display": "block"}


def test_toggle_display_style_closes_when_open():
    assert toggle_display_style({"display": "block"}) == {"display": "none"}


def test_select_chart_tickers_returns_all_when_none_open():
    assert select_chart_tickers(["A", "B", "C"], set()) == ["A", "B", "C"]


def test_select_chart_tickers_returns_open_subset_in_original_order():
    assert select_chart_tickers(["A", "B", "C"], {"C", "A"}) == ["A", "C"]


def test_chart_title_for_tickers_is_total_portfolio_when_none_open():
    assert chart_title_for_tickers(["A", "B", "C"], ["A", "B", "C"]) == "Total Portfolio"


def test_chart_title_for_tickers_joins_selected_tickers():
    assert chart_title_for_tickers(["A", "C"], ["A", "B", "C"]) == "A + C"


def test_row_style_for_selection_highlights_when_selected():
    style = row_style_for_selection(True)
    assert style.get("backgroundColor") == "#fff8db"


def test_row_style_for_selection_default_when_not_selected():
    style = row_style_for_selection(False)
    assert "backgroundColor" not in style
