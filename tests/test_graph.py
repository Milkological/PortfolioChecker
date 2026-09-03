import os

import matplotlib.pyplot as plt
import pytest

from portfolio_checker.graph import (
    build_year_labels,
    cumulative_stack_series,
    extract_yearly_points,
    plot_portfolio_report,
    plot_stacked_breakdown,
)


def test_extract_yearly_points_samples_every_12_months():
    monthly_values = list(range(25))  # 0..24, representing 24 months (2 years)
    result = extract_yearly_points(monthly_values)
    assert result == [0, 12, 24]


def test_build_year_labels():
    assert build_year_labels(3) == [0, 1, 2, 3]


def test_cumulative_stack_series_sums_to_total_value():
    rows = [
        {"year": 0, "contributed_total": 1000.0, "dividend_income": 0.0, "growth_gain": 0.0, "total_value": 1000.0},
        {"year": 1, "contributed_total": 1500.0, "dividend_income": 10.0, "growth_gain": 40.0, "total_value": 1550.0},
        {"year": 2, "contributed_total": 2000.0, "dividend_income": 15.0, "growth_gain": 60.0, "total_value": 2125.0},
    ]

    contributed, dividend_cum, growth_cum = cumulative_stack_series(rows)

    assert contributed == pytest.approx([1000.0, 1500.0, 2000.0])
    assert dividend_cum == pytest.approx([0.0, 10.0, 25.0])
    assert growth_cum == pytest.approx([0.0, 40.0, 100.0])
    totals = [c + d + g for c, d, g in zip(contributed, dividend_cum, growth_cum)]
    assert totals == pytest.approx([row["total_value"] for row in rows])


def test_plot_stacked_breakdown_shows_currency_in_ylabel():
    rows = [
        {"year": 0, "contributed_total": 1000.0, "dividend_income": 0.0, "growth_gain": 0.0, "total_value": 1000.0},
        {"year": 1, "contributed_total": 1100.0, "dividend_income": 5.0, "growth_gain": 20.0, "total_value": 1125.0},
    ]
    fig, ax = plt.subplots()

    plot_stacked_breakdown(ax, rows, currency="SGD", title="AAPL")

    assert ax.get_ylabel() == "Value (SGD)"
    assert ax.get_title() == "AAPL"
    plt.close(fig)


def test_plot_stacked_breakdown_defaults_to_dollar_sign_without_currency():
    rows = [
        {"year": 0, "contributed_total": 1000.0, "dividend_income": 0.0, "growth_gain": 0.0, "total_value": 1000.0},
    ]
    fig, ax = plt.subplots()

    plot_stacked_breakdown(ax, rows)

    assert ax.get_ylabel() == "Value ($)"
    plt.close(fig)


def test_plot_portfolio_report_saves_file_with_one_panel_per_ticker_plus_total(tmp_path):
    total_rows = [
        {"year": 0, "contributed_total": 1000.0, "dividend_income": 0.0, "growth_gain": 0.0, "total_value": 1000.0},
        {"year": 1, "contributed_total": 1600.0, "dividend_income": 10.0, "growth_gain": 40.0, "total_value": 1650.0},
    ]
    ticker_rows = {
        "AAPL": [
            {"year": 0, "contributed_total": 500.0, "dividend_income": 0.0, "growth_gain": 0.0, "total_value": 500.0},
            {"year": 1, "contributed_total": 800.0, "dividend_income": 6.0, "growth_gain": 20.0, "total_value": 826.0},
        ],
        "MSFT": [
            {"year": 0, "contributed_total": 500.0, "dividend_income": 0.0, "growth_gain": 0.0, "total_value": 500.0},
            {"year": 1, "contributed_total": 800.0, "dividend_income": 4.0, "growth_gain": 20.0, "total_value": 824.0},
        ],
    }
    output_path = tmp_path / "report.png"

    fig = plot_portfolio_report(total_rows, ticker_rows, currency="USD", output_path=str(output_path))

    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0
    # 1 total panel + 1 panel per ticker
    assert len(fig.axes) == 1 + len(ticker_rows)
