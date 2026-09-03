import statistics
from datetime import date, timedelta


def recent_dividend_payments(history: list, count: int = 4) -> list:
    return history[:count]


def dividends_paid_this_calendar_year(history: list, shares: float, year: int = None) -> float:
    target_year = year if year is not None else date.today().year
    matching_total = sum(amount for payment_date, amount in history if payment_date.year == target_year)
    return matching_total * shares


def estimate_next_dividend_date(history: list):
    if len(history) < 2:
        return None

    recent = history[:4]
    intervals = [(recent[i][0] - recent[i + 1][0]).days for i in range(len(recent) - 1)]
    median_interval = statistics.median(intervals)
    return recent[0][0] + timedelta(days=median_interval)
