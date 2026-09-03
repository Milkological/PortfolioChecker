import os

import pandas as pd

import portfolio_checker.market_data as market_data
from portfolio_checker import cli
from tests.conftest import FakeTicker, make_price_history


def test_fetch_market_data_for_ticker_warns_on_high_growth_rate(monkeypatch):
    end_date = pd.Timestamp.now().normalize()
    start_date = end_date - pd.Timedelta(days=5 * 365)
    high_growth_ticker = FakeTicker(
        history_df=make_price_history(100.0, 300.0, start_date, end_date),  # ~24.6% CAGR
        dividends=pd.Series(dtype=float),
    )
    monkeypatch.setattr(market_data, "get_ticker", lambda symbol: high_growth_ticker)
    messages = []

    data = cli.fetch_market_data_for_ticker("HYPE", "USD", print_func=messages.append)

    assert data is not None
    assert any("unusually high" in m for m in messages)


def test_fetch_market_data_for_ticker_no_warning_for_normal_growth_rate(
    monkeypatch, ticker_with_growth_and_dividends
):
    monkeypatch.setattr(market_data, "get_ticker", lambda symbol: ticker_with_growth_and_dividends)
    messages = []

    data = cli.fetch_market_data_for_ticker("AAPL", "USD", print_func=messages.append)

    assert data is not None
    assert not messages


def test_fetch_market_data_for_ticker_passes_through_price_period(monkeypatch, ticker_with_growth_and_dividends):
    recorded_periods = []
    original_history = ticker_with_growth_and_dividends.history

    def recording_history(period="5y", auto_adjust=False):
        recorded_periods.append(period)
        return original_history(period=period, auto_adjust=auto_adjust)

    ticker_with_growth_and_dividends.history = recording_history
    monkeypatch.setattr(market_data, "get_ticker", lambda symbol: ticker_with_growth_and_dividends)

    cli.fetch_market_data_for_ticker("AAPL", "USD", price_period="10y", print_func=lambda m: None)

    assert "10y" in recorded_periods


def test_fetch_market_data_for_ticker_manual_entry_builds_valid_market_data(monkeypatch):
    def failing_get_ticker(symbol):
        raise RuntimeError("network down")

    monkeypatch.setattr(market_data, "get_ticker", failing_get_ticker)
    responses = iter(["manual", "7", "100"])

    data = cli.fetch_market_data_for_ticker(
        "BADTICKER", "USD", input_func=lambda prompt: next(responses), print_func=lambda m: None
    )

    assert data.current_price == 100.0
    assert data.annual_growth_rate == 0.07
    assert data.annual_dividend_per_share == 0.0
    assert data.has_dividends is False
    assert data.dividend_history == []
    assert data.company_summary  # must be a populated string, not missing/empty


def test_run_asks_for_lookback_period_and_uses_it(monkeypatch, tmp_path, ticker_with_growth_and_dividends):
    recorded_periods = []
    original_history = ticker_with_growth_and_dividends.history

    def recording_history(period="5y", auto_adjust=False):
        recorded_periods.append(period)
        return original_history(period=period, auto_adjust=auto_adjust)

    ticker_with_growth_and_dividends.history = recording_history
    monkeypatch.setattr(market_data, "get_ticker", lambda symbol: ticker_with_growth_and_dividends)

    answers = iter(
        [
            "AAPL,10",  # holding
            "50",  # monthly DCA for AAPL
            "",  # blank -> finish holdings
            "USD",  # base currency
            "5",  # projection years
            "10y",  # price history lookback period
        ]
    )
    input_func = lambda prompt: next(answers)
    output_path = tmp_path / "chart.png"

    cli.run(
        input_func=input_func,
        print_func=lambda m: None,
        output_path=str(output_path),
        logs_dir=str(tmp_path / "logs"),
    )

    assert "10y" in recorded_periods


def test_run_end_to_end_with_mocked_market_data(monkeypatch, tmp_path, ticker_with_growth_and_dividends):
    monkeypatch.setattr(market_data, "get_ticker", lambda symbol: ticker_with_growth_and_dividends)

    answers = iter(
        [
            "AAPL,10",  # holding
            "50",  # monthly DCA for AAPL
            "",  # blank -> finish holdings
            "USD",  # base currency
            "5",  # projection years
            "",  # lookback period -> default 5y
        ]
    )
    input_func = lambda prompt: next(answers)
    messages = []
    output_path = tmp_path / "chart.png"

    cli.run(
        input_func=input_func,
        print_func=messages.append,
        output_path=str(output_path),
        logs_dir=str(tmp_path / "logs"),
    )

    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0
    assert not messages  # no warnings/errors expected on the happy path


def test_run_writes_per_ticker_and_total_csv_logs(monkeypatch, tmp_path, ticker_with_growth_and_dividends):
    monkeypatch.setattr(market_data, "get_ticker", lambda symbol: ticker_with_growth_and_dividends)

    answers = iter(
        [
            "AAPL,10",  # holding
            "50",  # monthly DCA for AAPL
            "",  # blank -> finish holdings
            "USD",  # base currency
            "5",  # projection years
            "",  # lookback period -> default 5y
        ]
    )
    input_func = lambda prompt: next(answers)
    messages = []
    output_path = tmp_path / "chart.png"
    logs_dir = tmp_path / "logs"

    cli.run(input_func=input_func, print_func=messages.append, output_path=str(output_path), logs_dir=str(logs_dir))

    aapl_csv = logs_dir / "AAPL.csv"
    total_csv = logs_dir / "TOTAL.csv"
    assert aapl_csv.exists()
    assert total_csv.exists()
    header = aapl_csv.read_text().splitlines()[0]
    assert header == "year,contributed_total,dividend_income,growth_gain,total_value"


def test_run_end_to_end_loading_holdings_from_csv(monkeypatch, tmp_path, ticker_with_growth_and_dividends):
    monkeypatch.setattr(market_data, "get_ticker", lambda symbol: ticker_with_growth_and_dividends)

    holdings_file = tmp_path / "holdings.csv"
    holdings_file.write_text("ticker,shares,monthly_dca\nAAPL,10,50\n")

    answers = iter(
        [
            "USD",  # base currency
            "5",  # projection years
            "",  # lookback period -> default 5y
        ]
    )
    input_func = lambda prompt: next(answers)
    messages = []
    output_path = tmp_path / "chart.png"

    cli.run(
        input_func=input_func,
        print_func=messages.append,
        output_path=str(output_path),
        holdings_file=str(holdings_file),
        logs_dir=str(tmp_path / "logs"),
    )

    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0
    assert not messages


def test_run_end_to_end_converts_mixed_currency_holdings(monkeypatch, tmp_path, ticker_with_growth_and_dividends):
    end_date = pd.Timestamp.now().normalize()
    start_date = end_date - pd.Timedelta(days=5 * 365)
    sgd_ticker = FakeTicker(
        history_df=make_price_history(10.0, 20.0, start_date, end_date),
        dividends=pd.Series(dtype=float),
        currency="SGD",
    )
    fx_ticker = FakeTicker(history_df=pd.DataFrame({"Close": [1.35]}, index=pd.date_range("2026-01-01", periods=1)))

    def fake_get_ticker(symbol):
        if symbol == "D05.SI":
            return sgd_ticker
        if symbol == "SGDUSD=X":
            return fx_ticker
        return ticker_with_growth_and_dividends  # AAPL, native USD

    monkeypatch.setattr(market_data, "get_ticker", fake_get_ticker)

    holdings_file = tmp_path / "holdings.csv"
    holdings_file.write_text(
        "ticker,shares,monthly_dca,currency\nAAPL,10,50,USD\nD05.SI,50,0,SGD\n"
    )

    answers = iter(
        [
            "USD",  # base currency
            "5",  # projection years
            "",  # lookback period -> default 5y
        ]
    )
    input_func = lambda prompt: next(answers)
    messages = []
    output_path = tmp_path / "chart.png"

    cli.run(
        input_func=input_func,
        print_func=messages.append,
        output_path=str(output_path),
        holdings_file=str(holdings_file),
        logs_dir=str(tmp_path / "logs"),
    )

    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0
    assert not messages
