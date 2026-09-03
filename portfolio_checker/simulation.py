from dataclasses import dataclass, field
from typing import Optional

from portfolio_checker.finance_math import annual_rate_to_periodic_rate


@dataclass
class TickerConfig:
    ticker: str
    initial_shares: float
    annual_growth_rate: float
    monthly_dca_amount: float
    annual_dividend_per_share: float
    dividend_reinvest_target: Optional[str]


@dataclass
class SimulationResult:
    ticker_values: dict
    cash_balance: list
    total_value: list
    dividend_income: dict


def compute_dividend_cash(shares, configs):
    return {
        ticker: shares[ticker] * (config.annual_dividend_per_share / 12)
        for ticker, config in configs.items()
    }


def simulate_month(shares, prices, cash, configs):
    for config in configs.values():
        target = config.dividend_reinvest_target
        if target is not None and target != "CASH" and target not in configs:
            raise ValueError(f"Unknown dividend_reinvest_target: {target!r}")

    dividend_cash = compute_dividend_cash(shares, configs)

    new_prices = dict(prices)
    for ticker, config in configs.items():
        monthly_rate = annual_rate_to_periodic_rate(config.annual_growth_rate, 12)
        new_prices[ticker] = prices[ticker] * (1 + monthly_rate)

    new_shares = dict(shares)
    for ticker, config in configs.items():
        new_shares[ticker] += config.monthly_dca_amount / new_prices[ticker]

    new_cash = cash
    for ticker, config in configs.items():
        target = config.dividend_reinvest_target
        if target is None or target == "CASH":
            new_cash += dividend_cash[ticker]
        else:
            new_shares[target] += dividend_cash[ticker] / new_prices[target]

    return new_shares, new_prices, new_cash


def simulate_portfolio(configs, initial_prices, months):
    config_by_ticker = {config.ticker: config for config in configs}

    shares = {config.ticker: config.initial_shares for config in configs}
    prices = dict(initial_prices)
    cash = 0.0

    ticker_values = {ticker: [shares[ticker] * prices[ticker]] for ticker in config_by_ticker}
    cash_balance = [cash]
    total_value = [sum(ticker_values[t][0] for t in config_by_ticker) + cash]
    dividend_income = {ticker: [0.0] for ticker in config_by_ticker}

    for _ in range(months):
        dividend_cash = compute_dividend_cash(shares, config_by_ticker)
        shares, prices, cash = simulate_month(shares, prices, cash, config_by_ticker)
        for ticker in config_by_ticker:
            ticker_values[ticker].append(shares[ticker] * prices[ticker])
            dividend_income[ticker].append(dividend_cash[ticker])
        cash_balance.append(cash)
        total_value.append(sum(ticker_values[t][-1] for t in config_by_ticker) + cash)

    return SimulationResult(
        ticker_values=ticker_values,
        cash_balance=cash_balance,
        total_value=total_value,
        dividend_income=dividend_income,
    )
