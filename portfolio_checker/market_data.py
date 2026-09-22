from dataclasses import dataclass, field

import pandas as pd
import yfinance as yf

from portfolio_checker.finance_math import compute_cagr

MIN_HISTORY_YEARS = 0.5
HIGH_GROWTH_RATE_THRESHOLD = 0.20


def get_ticker(symbol: str):
    return yf.Ticker(symbol)


def fetch_cagr_inputs(ticker_obj, period: str = "5y"):
    history = ticker_obj.history(period=period, auto_adjust=False)
    if not history.empty:
        history = history.dropna(subset=["Close"])

    if history.empty or len(history) < 2:
        raise ValueError("Insufficient price history to compute a growth rate")

    start_close = float(history["Close"].iloc[0])
    end_close = float(history["Close"].iloc[-1])

    start_date = history.index[0]
    end_date = history.index[-1]
    years = (end_date - start_date).days / 365.25

    if years < MIN_HISTORY_YEARS:
        raise ValueError(
            f"Only {years:.2f} years of price history available; need at least {MIN_HISTORY_YEARS}"
        )

    return start_close, end_close, years


def fetch_annual_dividend_per_share(ticker_obj, lookback_years: float = 2.0) -> float:
    dividends = ticker_obj.dividends
    if dividends.empty:
        return 0.0

    index = dividends.index
    if getattr(index, "tz", None) is not None:
        dividends = dividends.copy()
        dividends.index = index.tz_localize(None)

    cutoff = pd.Timestamp.now() - pd.Timedelta(days=lookback_years * 365.25)
    recent = dividends[dividends.index >= cutoff]
    return float(recent.sum()) / lookback_years


def fetch_dividend_history(ticker_obj) -> list:
    dividends = ticker_obj.dividends
    if dividends.empty:
        return []

    index = dividends.index
    if getattr(index, "tz", None) is not None:
        dividends = dividends.copy()
        dividends.index = index.tz_localize(None)

    payments = [(payment_date.date(), float(amount)) for payment_date, amount in dividends.items()]
    payments.sort(key=lambda payment: payment[0], reverse=True)
    return payments


def fetch_growth_rate_for_period(symbol: str, period: str) -> float:
    ticker_obj = get_ticker(symbol)
    start_close, end_close, years = fetch_cagr_inputs(ticker_obj, period=period)
    return compute_cagr(start_close, end_close, years)


def _strip_timezone(series):
    index = series.index
    if getattr(index, "tz", None) is not None:
        series = series.copy()
        series.index = index.tz_localize(None)
    return series


def fetch_price_series(ticker_obj, period: str = "5y") -> list:
    """Closing prices as (date, close) pairs, for correlation and drawdown work.

    The CAGR path already downloads this history and throws all but the first
    and last close away; keeping the series costs no extra network calls.
    """
    history = ticker_obj.history(period=period, auto_adjust=False)
    if history.empty:
        return []
    history = history.dropna(subset=["Close"])
    if history.empty:
        return []
    closes = _strip_timezone(history["Close"])
    return [(timestamp.date(), float(close)) for timestamp, close in closes.items()]


def fetch_etf_holdings(ticker_obj) -> list:
    """Constituent symbols of a fund, when yfinance can supply them.

    This data is patchy and the accessor has changed shape across yfinance
    versions, so every failure returns an empty list — the review falls back to
    same-exchange inference and labels the finding as inferred.
    """
    try:
        top_holdings = ticker_obj.funds_data.top_holdings
    except Exception:
        return []

    if top_holdings is None or getattr(top_holdings, "empty", True):
        return []

    try:
        return [str(symbol).upper() for symbol in top_holdings.index]
    except Exception:
        return []


def fetch_company_metadata(ticker_obj, info=None) -> dict:
    """Classification fields used by the portfolio review. Never raises."""
    if info is None:
        info = getattr(ticker_obj, "info", None) or {}
    return {
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "country": info.get("country"),
        "quote_type": info.get("quoteType"),
        "market_cap": info.get("marketCap"),
    }


def fetch_company_summary(ticker_obj, info=None) -> str:
    if info is None:
        info = ticker_obj.info
    summary = info.get("longBusinessSummary")
    if summary:
        return summary

    name = info.get("longName") or info.get("shortName")
    category = info.get("category")
    if name and category:
        return f"{name} — {category}"
    if name:
        return name
    return "No company summary available."


def has_dividends(ticker_obj) -> bool:
    return not ticker_obj.dividends.empty


def is_high_growth_rate(annual_growth_rate: float, threshold: float = HIGH_GROWTH_RATE_THRESHOLD) -> bool:
    return annual_growth_rate > threshold


def describe_high_growth_warning(
    annual_growth_rate: float, threshold: float = HIGH_GROWTH_RATE_THRESHOLD
) -> str | None:
    if not is_high_growth_rate(annual_growth_rate, threshold):
        return None
    return (
        f"fetched growth rate ({annual_growth_rate * 100:.1f}%) is unusually high and may reflect "
        f"a short-term rally rather than a sustainable long-term trend. Consider double-checking "
        f"it, or trying a different lookback period."
    )


def get_ticker_currency(ticker_obj) -> str:
    return ticker_obj.fast_info["currency"]


def fetch_latest_price(ticker_obj, period: str = "5d") -> float:
    history = ticker_obj.history(period=period, auto_adjust=False)
    if not history.empty:
        history = history.dropna(subset=["Close"])
    if history.empty:
        raise ValueError("No price data available to determine the latest price")
    return float(history["Close"].iloc[-1])


def get_fx_rate(from_currency: str, to_currency: str) -> float:
    if from_currency == to_currency:
        return 1.0
    pair_ticker = get_ticker(f"{from_currency}{to_currency}=X")
    return fetch_latest_price(pair_ticker)


@dataclass
class TickerMarketData:
    current_price: float
    annual_growth_rate: float
    annual_dividend_per_share: float
    has_dividends: bool
    dividend_history: list
    company_summary: str
    sector: str = None
    industry: str = None
    country: str = None
    quote_type: str = None
    market_cap: float = None
    native_currency: str = None
    price_series: list = field(default_factory=list)


def build_ticker_market_data(
    symbol: str,
    base_currency: str,
    native_currency_override: str = None,
    price_period: str = "5y",
    dividend_lookback_years: float = 2.0,
) -> TickerMarketData:
    ticker_obj = get_ticker(symbol)
    start_close, end_close, years = fetch_cagr_inputs(ticker_obj, period=price_period)
    annual_growth_rate = compute_cagr(start_close, end_close, years)
    annual_dividend = fetch_annual_dividend_per_share(ticker_obj, dividend_lookback_years)
    dividend_history = fetch_dividend_history(ticker_obj)

    info = getattr(ticker_obj, "info", None) or {}
    company_summary = fetch_company_summary(ticker_obj, info)
    metadata = fetch_company_metadata(ticker_obj, info)

    native_currency = native_currency_override or get_ticker_currency(ticker_obj)
    fx_rate = get_fx_rate(native_currency, base_currency)

    return TickerMarketData(
        current_price=end_close * fx_rate,
        annual_growth_rate=annual_growth_rate,
        annual_dividend_per_share=annual_dividend * fx_rate,
        company_summary=company_summary,
        has_dividends=has_dividends(ticker_obj),
        dividend_history=[(payment_date, amount * fx_rate) for payment_date, amount in dividend_history],
        native_currency=native_currency,
        price_series=fetch_price_series(ticker_obj, period=price_period),
        **metadata,
    )
