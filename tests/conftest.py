import matplotlib

matplotlib.use("Agg")

import pandas as pd
import pytest


class FakeTicker:
    """Test double standing in for yfinance.Ticker — no network access."""

    def __init__(self, history_df=None, dividends=None, currency="USD", info=None):
        self._history_df = history_df if history_df is not None else pd.DataFrame()
        self._dividends = dividends if dividends is not None else pd.Series(dtype=float)
        self.fast_info = {"currency": currency}
        self.info = info if info is not None else {}

    def history(self, period="5y", auto_adjust=False):
        return self._history_df

    @property
    def dividends(self):
        return self._dividends


def make_price_history(start_price, end_price, start_date, end_date, freq="7D"):
    dates = pd.date_range(start=start_date, end=end_date, freq=freq)
    prices = [start_price + (end_price - start_price) * i / (len(dates) - 1) for i in range(len(dates))]
    return pd.DataFrame({"Close": prices}, index=dates)


@pytest.fixture
def ticker_with_growth_and_dividends():
    end_date = pd.Timestamp.now().normalize()
    start_date = end_date - pd.Timedelta(days=5 * 365)
    history_df = make_price_history(100.0, 200.0, start_date, end_date)
    dividends = pd.Series(
        [0.5, 0.5, 0.5, 0.5],
        index=pd.date_range(end=end_date, periods=4, freq="90D"),
    )
    return FakeTicker(history_df=history_df, dividends=dividends)


@pytest.fixture
def ticker_with_zero_dividends():
    end_date = pd.Timestamp.now().normalize()
    start_date = end_date - pd.Timedelta(days=5 * 365)
    history_df = make_price_history(100.0, 150.0, start_date, end_date)
    return FakeTicker(history_df=history_df, dividends=pd.Series(dtype=float))


@pytest.fixture
def ticker_with_insufficient_history():
    end_date = pd.Timestamp.now().normalize()
    start_date = end_date - pd.Timedelta(days=5)
    history_df = make_price_history(100.0, 101.0, start_date, end_date, freq="1D")
    return FakeTicker(history_df=history_df, dividends=pd.Series(dtype=float))
