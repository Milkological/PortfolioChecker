import pytest

from portfolio_checker.yearly_summary import build_yearly_summary


def test_build_yearly_summary_no_dividends():
    year_labels = [0, 1, 2]
    contributed_yearly = [1000.0, 1600.0, 2200.0]
    total_value_yearly = [1000.0, 1700.0, 2500.0]
    dividend_income_monthly = [0.0] * 25  # 2 years -> 24 months + initial snapshot

    rows = build_yearly_summary(year_labels, contributed_yearly, dividend_income_monthly, total_value_yearly)

    assert rows == [
        {"year": 0, "contributed_total": pytest.approx(1000.0), "dividend_income": pytest.approx(0.0),
         "growth_gain": pytest.approx(0.0), "total_value": pytest.approx(1000.0)},
        {"year": 1, "contributed_total": pytest.approx(1600.0), "dividend_income": pytest.approx(0.0),
         "growth_gain": pytest.approx(100.0), "total_value": pytest.approx(1700.0)},
        {"year": 2, "contributed_total": pytest.approx(2200.0), "dividend_income": pytest.approx(0.0),
         "growth_gain": pytest.approx(200.0), "total_value": pytest.approx(2500.0)},
    ]


def test_build_yearly_summary_sums_dividends_within_each_year():
    year_labels = [0, 1, 2]
    contributed_yearly = [1000.0, 1000.0, 1000.0]
    total_value_yearly = [1000.0, 1050.0, 1130.0]
    # index 0 = initial snapshot, indices 1-12 = year 1's months, 13-24 = year 2's months
    dividend_income_monthly = [0.0] + [5.0] * 12 + [10.0] * 12

    rows = build_yearly_summary(year_labels, contributed_yearly, dividend_income_monthly, total_value_yearly)

    assert rows[1]["dividend_income"] == pytest.approx(60.0)
    # growth_gain = 1050 - 1000 - (contributed unchanged) - 60 dividends
    assert rows[1]["growth_gain"] == pytest.approx(-10.0)
    assert rows[2]["dividend_income"] == pytest.approx(120.0)
    assert rows[2]["growth_gain"] == pytest.approx(-40.0)
