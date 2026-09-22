"""Portfolio statistics over price series and weights — pure, no I/O.

Everything here takes plain Python data (lists of (date, close) pairs, dicts of
weights) so it can be tested without pandas fixtures or network access.
"""

import math

TRADING_DAYS_PER_YEAR = 252


def month_end_prices(price_series: list) -> dict:
    """Collapse a daily series to one close per calendar month.

    Monthly sampling is what the correlation figures should be built on: daily
    returns across exchanges in different timezones produce spuriously low
    correlations purely from non-overlapping trading hours.
    """
    by_month = {}
    for price_date, close in sorted(price_series):
        by_month[(price_date.year, price_date.month)] = close
    return by_month


def monthly_returns(price_series: list) -> dict:
    """Month-over-month returns, keyed by (year, month)."""
    prices = month_end_prices(price_series)
    keys = sorted(prices)
    returns = {}
    for previous, current in zip(keys, keys[1:]):
        previous_price = prices[previous]
        if previous_price > 0:
            returns[current] = prices[current] / previous_price - 1
    return returns


def correlation(returns_a: dict, returns_b: dict) -> float:
    """Pearson correlation over the months both series cover.

    Returns 0.0 when there is too little overlap to say anything, so callers
    never mistake "unknown" for "uncorrelated" by way of an exception.
    """
    shared = sorted(set(returns_a) & set(returns_b))
    if len(shared) < 12:
        return None

    a = [returns_a[key] for key in shared]
    b = [returns_b[key] for key in shared]
    mean_a = sum(a) / len(a)
    mean_b = sum(b) / len(b)

    covariance = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    variance_a = sum((x - mean_a) ** 2 for x in a)
    variance_b = sum((y - mean_b) ** 2 for y in b)
    if variance_a <= 0 or variance_b <= 0:
        return None

    return covariance / math.sqrt(variance_a * variance_b)


def correlation_pairs(series_by_ticker: dict) -> list:
    """Every pairwise correlation, strongest first."""
    returns = {
        ticker: monthly_returns(series) for ticker, series in series_by_ticker.items() if series
    }
    tickers = sorted(returns)
    pairs = []
    for i, first in enumerate(tickers):
        for second in tickers[i + 1 :]:
            value = correlation(returns[first], returns[second])
            if value is not None:
                pairs.append((first, second, value))
    pairs.sort(key=lambda pair: pair[2], reverse=True)
    return pairs


def annualised_volatility(price_series: list) -> float:
    """Annualised standard deviation of monthly returns."""
    returns = list(monthly_returns(price_series).values())
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(12)


def max_drawdown(price_series: list) -> float:
    """Largest peak-to-trough fall, as a positive fraction."""
    peak = None
    worst = 0.0
    for _, close in sorted(price_series):
        if peak is None or close > peak:
            peak = close
        if peak and peak > 0:
            worst = max(worst, (peak - close) / peak)
    return worst


def herfindahl_index(weights: list) -> float:
    """Concentration of a set of weights: 1/n when even, 1.0 for a single position."""
    total = sum(weights)
    if total <= 0:
        return 0.0
    return sum((weight / total) ** 2 for weight in weights)


def effective_holdings(weights: list) -> float:
    """How many equally-sized positions the portfolio really behaves like."""
    index = herfindahl_index(weights)
    return 1 / index if index > 0 else 0.0


def position_values(ticker_inputs: list) -> dict:
    return {t.ticker: t.initial_shares * t.current_price for t in ticker_inputs}


def breakdown_by_attribute(ticker_inputs: list, attribute: str, unknown_label="Unknown") -> list:
    """Group holdings by a metadata field, largest group first.

    Returns one entry per group with its value, share of the portfolio, and the
    tickers in it — enough to render a breakdown table directly.
    """
    groups = {}
    for t in ticker_inputs:
        key = getattr(t, attribute, None) or unknown_label
        group = groups.setdefault(key, {"key": key, "value": 0.0, "tickers": []})
        group["value"] += t.initial_shares * t.current_price
        group["tickers"].append(t.ticker)

    total_value = sum(group["value"] for group in groups.values())
    for group in groups.values():
        group["weight"] = group["value"] / total_value if total_value > 0 else 0.0

    return sorted(groups.values(), key=lambda group: group["value"], reverse=True)


def weights_by_attribute(ticker_inputs: list, attribute: str, unknown_label="Unknown") -> dict:
    """Share of portfolio value grouped by a metadata field, largest first."""
    totals = {}
    for t in ticker_inputs:
        key = getattr(t, attribute, None) or unknown_label
        totals[key] = totals.get(key, 0.0) + t.initial_shares * t.current_price

    total_value = sum(totals.values())
    if total_value <= 0:
        return {}
    shares = {key: value / total_value for key, value in totals.items()}
    return dict(sorted(shares.items(), key=lambda item: item[1], reverse=True))
