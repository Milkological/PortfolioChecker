from datetime import date

import pandas as pd
import pytest

import portfolio_checker.market_data as market_data
from portfolio_checker.finance_math import compute_cagr
from portfolio_checker.market_data import (
    build_ticker_market_data,
    describe_high_growth_warning,
    fetch_annual_dividend_per_share,
    fetch_cagr_inputs,
    fetch_company_summary,
    fetch_dividend_history,
    fetch_growth_rate_for_period,
    fetch_latest_price,
    get_fx_rate,
    get_ticker_currency,
    has_dividends,
    is_high_growth_rate,
)
from tests.conftest import FakeTicker, make_price_history


def test_fetch_cagr_inputs_normal_case(ticker_with_growth_and_dividends):
    start_close, end_close, years = fetch_cagr_inputs(ticker_with_growth_and_dividends)

    assert start_close == pytest.approx(100.0)
    assert end_close == pytest.approx(200.0)
    assert years == pytest.approx(5.0, abs=0.05)


def test_fetch_cagr_inputs_empty_history_raises():
    empty_ticker = FakeTicker(history_df=pd.DataFrame())
    with pytest.raises(ValueError):
        fetch_cagr_inputs(empty_ticker)


def test_fetch_cagr_inputs_too_short_span_raises(ticker_with_insufficient_history):
    with pytest.raises(ValueError):
        fetch_cagr_inputs(ticker_with_insufficient_history)


def test_fetch_cagr_inputs_ignores_trailing_nan_close():
    end_date = pd.Timestamp.now().normalize()
    start_date = end_date - pd.Timedelta(days=5 * 365)
    history_df = make_price_history(100.0, 200.0, start_date, end_date)
    # Simulate Yahoo Finance returning NaN for an in-progress/unsettled latest session.
    history_df.loc[history_df.index[-1], "Close"] = float("nan")
    ticker = FakeTicker(history_df=history_df)

    start_close, end_close, years = fetch_cagr_inputs(ticker)

    assert start_close == pytest.approx(100.0)
    assert end_close == pytest.approx(history_df["Close"].iloc[-2])
    assert years > 0


def test_fetch_annual_dividend_per_share_sums_trailing_year():
    now = pd.Timestamp.now().normalize()
    dividends = pd.Series(
        [1.0, 1.0, 1.0, 1.0],
        index=[now - pd.DateOffset(months=m) for m in (1, 4, 7, 10)],
    )
    ticker = FakeTicker(dividends=dividends)

    result = fetch_annual_dividend_per_share(ticker, lookback_years=1.0)

    # $4 total dividends over the trailing year -> $4/year
    assert result == pytest.approx(4.0)


def test_fetch_annual_dividend_per_share_excludes_old_dividends():
    now = pd.Timestamp.now().normalize()
    dividends = pd.Series(
        [1.0, 1.0, 5.0],
        index=[now - pd.DateOffset(months=m) for m in (1, 4, 24)],
    )
    ticker = FakeTicker(dividends=dividends)

    result = fetch_annual_dividend_per_share(ticker, lookback_years=1.0)

    # only the two recent $1 dividends count; the 24-month-old $5 is excluded
    assert result == pytest.approx(2.0)


def test_fetch_annual_dividend_per_share_empty_series_returns_zero():
    ticker = FakeTicker(dividends=pd.Series(dtype=float))

    result = fetch_annual_dividend_per_share(ticker, lookback_years=1.0)

    assert result == pytest.approx(0.0)


def test_fetch_dividend_history_returns_plain_python_most_recent_first(ticker_with_growth_and_dividends):
    history = fetch_dividend_history(ticker_with_growth_and_dividends)

    assert len(history) == 4
    dates = [payment_date for payment_date, _ in history]
    assert dates == sorted(dates, reverse=True)
    payment_date, amount = history[0]
    assert isinstance(payment_date, date)
    assert not isinstance(payment_date, pd.Timestamp)
    assert isinstance(amount, float)
    assert amount == pytest.approx(0.5)


def test_fetch_dividend_history_empty_series_returns_empty_list():
    ticker = FakeTicker(dividends=pd.Series(dtype=float))

    assert fetch_dividend_history(ticker) == []


def test_describe_high_growth_warning_below_threshold_is_none():
    assert describe_high_growth_warning(0.10) is None


def test_describe_high_growth_warning_above_threshold_mentions_percentage():
    message = describe_high_growth_warning(0.25)

    assert message is not None
    assert "25.0%" in message


def test_fetch_company_summary_returns_long_business_summary_when_present():
    ticker = FakeTicker(info={"longBusinessSummary": "Makes and sells widgets worldwide."})

    assert fetch_company_summary(ticker) == "Makes and sells widgets worldwide."


def test_fetch_company_summary_falls_back_to_name_and_category():
    ticker = FakeTicker(info={"longName": "Nikko AM STI ETF", "category": "Equity"})

    assert fetch_company_summary(ticker) == "Nikko AM STI ETF — Equity"


def test_fetch_company_summary_falls_back_to_name_only():
    ticker = FakeTicker(info={"shortName": "Some Fund"})

    assert fetch_company_summary(ticker) == "Some Fund"


def test_fetch_company_summary_returns_placeholder_when_nothing_available():
    ticker = FakeTicker(info={})

    assert fetch_company_summary(ticker) == "No company summary available."


def test_fetch_growth_rate_for_period_composes_cagr_inputs(monkeypatch, ticker_with_growth_and_dividends):
    monkeypatch.setattr(market_data, "get_ticker", lambda symbol: ticker_with_growth_and_dividends)

    rate = fetch_growth_rate_for_period("FAKE", period="5y")

    start_close, end_close, years = fetch_cagr_inputs(ticker_with_growth_and_dividends, period="5y")
    assert rate == pytest.approx(compute_cagr(start_close, end_close, years))


def test_has_dividends_true_when_present(ticker_with_growth_and_dividends):
    assert has_dividends(ticker_with_growth_and_dividends) is True


def test_has_dividends_false_when_absent(ticker_with_zero_dividends):
    assert has_dividends(ticker_with_zero_dividends) is False


def test_get_ticker_currency_reads_fast_info():
    ticker = FakeTicker(currency="SGD")
    assert get_ticker_currency(ticker) == "SGD"


def test_is_high_growth_rate_above_default_threshold():
    assert is_high_growth_rate(0.25) is True


def test_is_high_growth_rate_at_or_below_default_threshold():
    assert is_high_growth_rate(0.20) is False
    assert is_high_growth_rate(0.10) is False


def test_is_high_growth_rate_custom_threshold():
    assert is_high_growth_rate(0.12, threshold=0.10) is True
    assert is_high_growth_rate(0.08, threshold=0.10) is False


def test_fetch_latest_price_returns_last_close():
    history_df = pd.DataFrame({"Close": [10.0, 11.0, 12.5]}, index=pd.date_range("2026-01-01", periods=3))
    ticker = FakeTicker(history_df=history_df)
    assert fetch_latest_price(ticker) == pytest.approx(12.5)


def test_fetch_latest_price_raises_on_empty_history():
    ticker = FakeTicker(history_df=pd.DataFrame())
    with pytest.raises(ValueError):
        fetch_latest_price(ticker)


def test_fetch_latest_price_ignores_trailing_nan_close():
    history_df = pd.DataFrame(
        {"Close": [10.0, 11.0, float("nan")]}, index=pd.date_range("2026-01-01", periods=3)
    )
    ticker = FakeTicker(history_df=history_df)
    assert fetch_latest_price(ticker) == pytest.approx(11.0)


def test_get_fx_rate_same_currency_is_one(monkeypatch):
    # No ticker lookup should happen at all when currencies match.
    monkeypatch.setattr(market_data, "get_ticker", lambda symbol: (_ for _ in ()).throw(AssertionError("should not fetch")))
    assert get_fx_rate("USD", "USD") == pytest.approx(1.0)


def test_get_fx_rate_different_currencies_fetches_pair(monkeypatch):
    fx_history = pd.DataFrame({"Close": [1.35]}, index=pd.date_range("2026-01-01", periods=1))
    fx_ticker = FakeTicker(history_df=fx_history)

    seen_symbols = []

    def fake_get_ticker(symbol):
        seen_symbols.append(symbol)
        return fx_ticker

    monkeypatch.setattr(market_data, "get_ticker", fake_get_ticker)

    rate = get_fx_rate("USD", "SGD")

    assert rate == pytest.approx(1.35)
    assert seen_symbols == ["USDSGD=X"]


def test_build_ticker_market_data_wiring(monkeypatch, ticker_with_growth_and_dividends):
    monkeypatch.setattr(market_data, "get_ticker", lambda symbol: ticker_with_growth_and_dividends)

    result = build_ticker_market_data("FAKE", base_currency="USD")

    start_close, end_close, years = fetch_cagr_inputs(ticker_with_growth_and_dividends)
    assert result.current_price == pytest.approx(end_close)
    assert result.has_dividends is True
    assert result.annual_dividend_per_share > 0
    assert result.annual_growth_rate > 0
    assert len(result.dividend_history) == 4
    assert result.company_summary == "No company summary available."


def test_build_ticker_market_data_converts_to_base_currency(monkeypatch):
    end_date = pd.Timestamp.now().normalize()
    start_date = end_date - pd.Timedelta(days=5 * 365)
    from tests.conftest import make_price_history

    sgd_ticker = FakeTicker(
        history_df=make_price_history(10.0, 20.0, start_date, end_date),
        dividends=pd.Series([1.0], index=[end_date]),
        currency="SGD",
    )
    fx_ticker = FakeTicker(
        history_df=pd.DataFrame({"Close": [1.35]}, index=pd.date_range("2026-01-01", periods=1))
    )

    def fake_get_ticker(symbol):
        return fx_ticker if symbol == "SGDUSD=X" else sgd_ticker

    monkeypatch.setattr(market_data, "get_ticker", fake_get_ticker)

    result = build_ticker_market_data("D05.SI", base_currency="USD")

    # native price is $20 SGD, converted at 1.35 USD per SGD
    assert result.current_price == pytest.approx(20.0 * 1.35)
    # the single native $1 SGD dividend payment is also converted at 1.35 USD per SGD
    assert result.dividend_history == [(end_date.date(), pytest.approx(1.35))]


def test_build_ticker_market_data_native_currency_override_skips_detection(monkeypatch, ticker_with_growth_and_dividends):
    def fail_if_currency_looked_up(symbol):
        raise AssertionError(f"should not fetch a ticker for {symbol}")

    # get_ticker is only called for the stock itself (needed for price/dividends);
    # the override means fast_info-based currency detection is never consulted.
    monkeypatch.setattr(market_data, "get_ticker", lambda symbol: ticker_with_growth_and_dividends)
    monkeypatch.setattr(market_data, "get_ticker_currency", lambda ticker_obj: (_ for _ in ()).throw(AssertionError("should not auto-detect")))

    result = build_ticker_market_data("FAKE", base_currency="USD", native_currency_override="USD")

    assert result.current_price > 0
