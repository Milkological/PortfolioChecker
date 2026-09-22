from dataclasses import dataclass, field

from portfolio_checker import contributions, yearly_summary
from portfolio_checker.graph import build_year_labels, extract_yearly_points
from portfolio_checker.simulation import TickerConfig, simulate_portfolio


@dataclass
class TickerInput:
    ticker: str
    initial_shares: float
    current_price: float
    annual_growth_rate: float
    annual_dividend_per_share: float
    monthly_dca_amount: float
    dividend_history: list = field(default_factory=list)
    company_summary: str = ""
    sector: str = None
    industry: str = None
    country: str = None
    quote_type: str = None
    market_cap: float = None
    native_currency: str = None
    price_series: list = field(default_factory=list)


REVIEW_METADATA_FIELDS = (
    "sector",
    "industry",
    "country",
    "quote_type",
    "market_cap",
    "native_currency",
    "price_series",
)


def review_metadata(source) -> dict:
    """Pull the review-only fields off a TickerInput or TickerMarketData."""
    return {field_name: getattr(source, field_name, None) for field_name in REVIEW_METADATA_FIELDS}


def total_annual_dividend_income(ticker_inputs: list) -> float:
    return sum(t.initial_shares * t.annual_dividend_per_share for t in ticker_inputs)


def total_portfolio_value(ticker_inputs: list) -> float:
    return sum(t.initial_shares * t.current_price for t in ticker_inputs)


def portfolio_share_percentage(position_value: float, total_value: float) -> float:
    if total_value == 0:
        return 0.0
    return position_value / total_value * 100


def weighted_average_growth_rate(ticker_inputs: list) -> float:
    total_value = total_portfolio_value(ticker_inputs)
    if total_value == 0:
        return 0.0
    weighted_sum = sum(t.initial_shares * t.current_price * t.annual_growth_rate for t in ticker_inputs)
    return weighted_sum / total_value


SUMMARY_VALUE_FIELDS = ("contributed_total", "dividend_income", "growth_gain", "total_value")


def scale_summary_rows(rows: list, factor: float) -> list:
    """Multiply every money column by a factor — used for currency conversion."""
    return [
        {"year": row["year"], **{field: row[field] * factor for field in SUMMARY_VALUE_FIELDS}}
        for row in rows
    ]


def combine_summary_rows(primary: list, secondary: list) -> list:
    """Add two yearly-summary row lists element-wise.

    When the secondary series is shorter — as CPF is once it stops at age 55 —
    its final balance is held flat for the remaining years, with no further
    contributions or growth attributed to it.
    """
    if not secondary:
        return list(primary)

    combined = []
    for i, row in enumerate(primary):
        if i < len(secondary):
            other = secondary[i]
        else:
            other = {
                "contributed_total": secondary[-1]["contributed_total"],
                "dividend_income": 0.0,
                "growth_gain": 0.0,
                "total_value": secondary[-1]["total_value"],
            }
        combined.append(
            {"year": row["year"], **{field: row[field] + other[field] for field in SUMMARY_VALUE_FIELDS}}
        )
    return combined


def build_report_data(ticker_inputs: list, years: int) -> tuple:
    configs = [
        TickerConfig(
            ticker=t.ticker,
            initial_shares=t.initial_shares,
            annual_growth_rate=t.annual_growth_rate,
            monthly_dca_amount=t.monthly_dca_amount,
            annual_dividend_per_share=t.annual_dividend_per_share,
            dividend_reinvest_target="CASH",
        )
        for t in ticker_inputs
    ]
    initial_prices = {t.ticker: t.current_price for t in ticker_inputs}
    months = years * 12
    result = simulate_portfolio(configs, initial_prices, months)
    year_labels = build_year_labels(years)

    ticker_rows = {}
    for t in ticker_inputs:
        ticker_contributed = contributions.cumulative_contributions(
            t.initial_shares * t.current_price, t.monthly_dca_amount, months
        )
        ticker_rows[t.ticker] = yearly_summary.build_yearly_summary(
            year_labels,
            extract_yearly_points(ticker_contributed),
            result.dividend_income[t.ticker],
            extract_yearly_points(result.ticker_values[t.ticker]),
        )

    total_initial_investment = sum(t.initial_shares * t.current_price for t in ticker_inputs)
    total_monthly_dca = sum(t.monthly_dca_amount for t in ticker_inputs)
    total_contributed = contributions.cumulative_contributions(total_initial_investment, total_monthly_dca, months)
    tickers = [t.ticker for t in ticker_inputs]
    total_dividend_income = contributions.total_dividend_income_monthly(result.dividend_income, tickers, months)
    total_rows = yearly_summary.build_yearly_summary(
        year_labels,
        extract_yearly_points(total_contributed),
        total_dividend_income,
        extract_yearly_points(result.total_value),
    )

    return total_rows, ticker_rows
