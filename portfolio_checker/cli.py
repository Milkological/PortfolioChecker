import csv
import os

from portfolio_checker import contributions, csv_export, graph, market_data, yearly_summary
from portfolio_checker.cli_parsing import (
    parse_currency_code,
    parse_growth_rate_percent,
    parse_holding_line,
    parse_holdings_csv_rows,
    parse_lookback_period,
    parse_nonnegative_float,
    parse_positive_float,
    parse_projection_years,
)
from portfolio_checker.market_data import TickerMarketData
from portfolio_checker.simulation import TickerConfig, simulate_portfolio


def collect_holdings(input_func=input):
    holdings = []
    while True:
        line = input_func(
            "Holding as TICKER,SHARES (Yahoo Finance format, e.g. AAPL,10 or "
            "D05.SI,50 for international exchanges) — blank to finish: "
        )
        if not line.strip():
            break
        ticker, shares = parse_holding_line(line)
        dca_text = input_func(f"Monthly DCA amount for {ticker} (0 if none): ")
        dca = parse_nonnegative_float(dca_text, "Monthly DCA amount")
        holdings.append({"ticker": ticker, "shares": shares, "dca": dca, "currency": None})
    return holdings


def load_holdings_from_csv(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    return parse_holdings_csv_rows(rows)


def fetch_market_data_for_ticker(
    ticker, base_currency, native_currency_override=None, price_period="5y", input_func=input, print_func=print
):
    while True:
        try:
            data = market_data.build_ticker_market_data(
                ticker,
                base_currency=base_currency,
                native_currency_override=native_currency_override,
                price_period=price_period,
            )
            warning = market_data.describe_high_growth_warning(data.annual_growth_rate)
            if warning:
                print_func(f"Note: {ticker}'s {warning}")
            return data
        except Exception as exc:
            print_func(f"Could not fetch data for {ticker}: {exc}")
            choice = input_func(
                f"Type 'retry' to re-enter the ticker, 'drop' to remove {ticker} from "
                "the portfolio, or 'manual' to enter your own growth rate: "
            ).strip().lower()
            if choice == "retry":
                ticker = input_func("Re-enter ticker symbol: ").strip().upper()
            elif choice == "drop":
                return None
            elif choice == "manual":
                rate = parse_growth_rate_percent(
                    input_func(f"Assumed annual growth rate for {ticker} (e.g. 7 or 7%): ")
                )
                price = parse_positive_float(
                    input_func(
                        f"Current price per share for {ticker}, in {base_currency} "
                        "(no dividend data will be used): "
                    ),
                    "Current price",
                )
                return TickerMarketData(
                    current_price=price,
                    annual_growth_rate=rate,
                    annual_dividend_per_share=0.0,
                    has_dividends=False,
                    dividend_history=[],
                    company_summary="No company summary available (manually entered ticker).",
                )
            else:
                print_func("Please type 'retry', 'drop', or 'manual'.")


def run(input_func=input, print_func=print, output_path=None, holdings_file=None, logs_dir="logs"):
    if holdings_file:
        holdings = load_holdings_from_csv(holdings_file)
    else:
        holdings = collect_holdings(input_func)
    if not holdings:
        print_func("No holdings entered — nothing to project.")
        return

    base_currency = parse_currency_code(
        input_func("What currency should totals be shown in? (e.g. USD, SGD): ")
    )
    years = parse_projection_years(input_func("Projection horizon in years [default 10]: "), default=10)
    lookback_period = parse_lookback_period(
        input_func("Price history window for growth rate calculation (3y/5y/10y/max) [default 5y]: "), default="5y"
    )

    tickers = [h["ticker"] for h in holdings]
    market_by_ticker = {}
    active_holdings = []
    for holding in holdings:
        data = fetch_market_data_for_ticker(
            holding["ticker"],
            base_currency,
            native_currency_override=holding.get("currency"),
            price_period=lookback_period,
            input_func=input_func,
            print_func=print_func,
        )
        if data is None:
            print_func(f"Dropping {holding['ticker']} from the portfolio.")
            continue
        market_by_ticker[holding["ticker"]] = data
        active_holdings.append(holding)

    if not active_holdings:
        print_func("No holdings left after data lookup — nothing to project.")
        return

    tickers = [h["ticker"] for h in active_holdings]
    configs = []
    initial_prices = {}
    for holding in active_holdings:
        ticker = holding["ticker"]
        data = market_by_ticker[ticker]
        initial_prices[ticker] = data.current_price

        configs.append(
            TickerConfig(
                ticker=ticker,
                initial_shares=holding["shares"],
                annual_growth_rate=data.annual_growth_rate,
                monthly_dca_amount=holding["dca"],
                annual_dividend_per_share=data.annual_dividend_per_share,
                dividend_reinvest_target="CASH",
            )
        )

    months = years * 12
    result = simulate_portfolio(configs, initial_prices, months)

    shares_now = {h["ticker"]: h["shares"] for h in active_holdings}
    initial_investment = contributions.initial_portfolio_value(shares_now, initial_prices)
    total_monthly_dca = sum(h["dca"] for h in active_holdings)
    contributed = contributions.cumulative_contributions(initial_investment, total_monthly_dca, months)

    year_labels = graph.build_year_labels(years)
    contributed_yearly = graph.extract_yearly_points(contributed)
    projected_yearly = graph.extract_yearly_points(result.total_value)

    os.makedirs(logs_dir, exist_ok=True)
    ticker_rows = {}
    for ticker in tickers:
        ticker_initial_investment = shares_now[ticker] * initial_prices[ticker]
        ticker_dca = next(h["dca"] for h in active_holdings if h["ticker"] == ticker)
        ticker_contributed = contributions.cumulative_contributions(ticker_initial_investment, ticker_dca, months)
        rows = yearly_summary.build_yearly_summary(
            year_labels,
            graph.extract_yearly_points(ticker_contributed),
            result.dividend_income[ticker],
            graph.extract_yearly_points(result.ticker_values[ticker]),
        )
        ticker_rows[ticker] = rows
        csv_export.write_yearly_summary_csv(rows, os.path.join(logs_dir, f"{ticker}.csv"))

    total_dividend_income = contributions.total_dividend_income_monthly(result.dividend_income, tickers, months)
    total_rows = yearly_summary.build_yearly_summary(
        year_labels, contributed_yearly, total_dividend_income, projected_yearly
    )
    csv_export.write_yearly_summary_csv(total_rows, os.path.join(logs_dir, "TOTAL.csv"))

    graph.plot_portfolio_report(total_rows, ticker_rows, currency=base_currency, output_path=output_path)
