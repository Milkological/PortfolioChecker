def initial_portfolio_value(shares: dict, prices: dict) -> float:
    return sum(shares[ticker] * prices[ticker] for ticker in shares)


def cumulative_contributions(initial_investment: float, total_monthly_dca: float, months: int) -> list:
    contributed = [initial_investment]
    for _ in range(months):
        contributed.append(contributed[-1] + total_monthly_dca)
    return contributed


def total_dividend_income_monthly(dividend_income: dict, tickers: list, months: int) -> list:
    return [sum(dividend_income[ticker][i] for ticker in tickers) for i in range(months + 1)]
