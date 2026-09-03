from portfolio_checker.plotly_view import build_stacked_figure


def test_build_stacked_figure_has_four_traces_summing_to_total_value():
    rows = [
        {"year": 0, "contributed_total": 1000.0, "dividend_income": 0.0, "growth_gain": 0.0, "total_value": 1000.0},
        {"year": 1, "contributed_total": 1500.0, "dividend_income": 10.0, "growth_gain": 40.0, "total_value": 1550.0},
    ]

    fig = build_stacked_figure(rows, currency="USD", title="AAPL")

    # 3 stacked layers (contributed, dividends, growth) + 1 total-value line
    assert len(fig.data) == 4
    assert fig.layout.title.text == "AAPL"
    assert fig.layout.yaxis.title.text == "Value (USD)"

    total_trace = fig.data[-1]
    assert list(total_trace.y) == [1000.0, 1550.0]


def test_build_stacked_figure_defaults_to_dollar_sign_without_currency():
    rows = [
        {"year": 0, "contributed_total": 1000.0, "dividend_income": 0.0, "growth_gain": 0.0, "total_value": 1000.0},
    ]

    fig = build_stacked_figure(rows)

    assert fig.layout.yaxis.title.text == "Value ($)"
