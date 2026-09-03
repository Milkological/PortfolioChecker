from datetime import date

import pytest

from portfolio_checker.dividend_history import (
    dividends_paid_this_calendar_year,
    estimate_next_dividend_date,
    recent_dividend_payments,
)


def test_recent_dividend_payments_returns_first_four_of_descending_list():
    history = [
        (date(2026, 8, 1), 0.6),
        (date(2026, 2, 1), 0.5),
        (date(2025, 8, 1), 0.4),
        (date(2025, 2, 1), 0.3),
        (date(2024, 8, 1), 0.2),
        (date(2024, 2, 1), 0.1),
    ]

    assert recent_dividend_payments(history, count=4) == history[:4]


def test_recent_dividend_payments_returns_all_when_fewer_than_count():
    history = [(date(2026, 8, 1), 0.6), (date(2026, 2, 1), 0.5)]

    assert recent_dividend_payments(history, count=4) == history


def test_dividends_paid_this_calendar_year_sums_matching_year_times_shares():
    history = [
        (date(2026, 3, 1), 0.5),
        (date(2026, 6, 1), 0.5),
        (date(2025, 11, 1), 0.5),
    ]

    result = dividends_paid_this_calendar_year(history, shares=100.0, year=2026)

    assert result == pytest.approx(100.0 * 1.0)


def test_dividends_paid_this_calendar_year_defaults_to_current_year():
    today = date.today()
    history = [(today, 1.0), (date(today.year - 1, 1, 1), 1.0)]

    result = dividends_paid_this_calendar_year(history, shares=10.0)

    assert result == pytest.approx(10.0)


def test_dividends_paid_this_calendar_year_no_matching_payments_returns_zero():
    history = [(date(2020, 1, 1), 1.0)]

    assert dividends_paid_this_calendar_year(history, shares=10.0, year=2026) == pytest.approx(0.0)


def test_estimate_next_dividend_date_uses_median_of_last_three_intervals():
    # payments 90 days apart -> next expected 90 days after the most recent
    history = [
        (date(2026, 7, 1), 0.5),
        (date(2026, 4, 2), 0.5),
        (date(2026, 1, 2), 0.5),
        (date(2025, 10, 3), 0.5),
    ]

    result = estimate_next_dividend_date(history)

    assert result == date(2026, 9, 29)


def test_estimate_next_dividend_date_returns_none_with_fewer_than_two_payments():
    assert estimate_next_dividend_date([(date(2026, 1, 1), 0.5)]) is None
    assert estimate_next_dividend_date([]) is None
