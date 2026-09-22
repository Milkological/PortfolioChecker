"""Rule-based portfolio review — pure, deterministic, testable.

Each check is a small function returning a Finding or None, so every threshold
is visible and can be argued with. The bluntness lives in the `detail` strings:
these are meant to name the problem, not soften it.

Nothing here is financial advice. The checks measure concentration, overlap and
correlation — structural properties of a portfolio — not whether any particular
holding is a good idea.
"""

from dataclasses import dataclass, field

from portfolio_checker.portfolio_stats import (
    correlation_pairs,
    effective_holdings,
    herfindahl_index,
    max_drawdown,
    position_values,
    weights_by_attribute,
)
from portfolio_checker.report_builder import (
    total_annual_dividend_income,
    weighted_average_growth_rate,
)

CRITICAL = "critical"
WARNING = "warning"
NOTE = "note"
GOOD = "good"

SEVERITY_ORDER = {CRITICAL: 0, WARNING: 1, NOTE: 2, GOOD: 3}

# --- Thresholds. Tune here, nowhere else. ---
SINGLE_POSITION_CRITICAL = 0.30
SINGLE_POSITION_WARNING = 0.20
TOP_THREE_WARNING = 0.60
EFFECTIVE_HOLDINGS_WARNING = 5.0
SECTOR_CRITICAL = 0.40
SECTOR_WARNING = 0.25
COUNTRY_CRITICAL = 0.70
COUNTRY_WARNING = 0.50
CURRENCY_WARNING = 0.30
CORRELATION_CRITICAL = 0.85
CORRELATION_WARNING = 0.70
# Pairs grow with the square of holdings; only the worst few get their own card.
MAX_CORRELATION_FINDINGS = 3
SPECULATIVE_GROWTH_RATE = 0.30
SMALL_MARKET_CAP = 2_000_000_000
LONG_RUN_EQUITY_RETURN = 0.08
DIVIDEND_CONCENTRATION_WARNING = 0.50
DCA_OVERWEIGHT_SHARE = 0.40
DRAWDOWN_WARNING = 0.50

DISCLAIMER = (
    "This is a mechanical review of concentration, overlap and correlation in "
    "what you hold. It is not financial advice, it knows nothing about your "
    "goals, tax position or time horizon, and it cannot tell you what to buy "
    "or sell."
)


@dataclass
class Finding:
    severity: str
    title: str
    detail: str
    evidence: dict = field(default_factory=dict)


def _percent(fraction: float) -> str:
    return f"{fraction * 100:.1f}%"


def _exchange_suffix(ticker: str) -> str:
    """'D05.SI' -> '.SI'; a bare US ticker has no suffix."""
    return f".{ticker.rsplit('.', 1)[1]}" if "." in ticker else ""


def check_position_concentration(ticker_inputs: list) -> list:
    values = position_values(ticker_inputs)
    total = sum(values.values())
    if total <= 0:
        return []

    findings = []
    ranked = sorted(values.items(), key=lambda item: item[1], reverse=True)
    top_ticker, top_value = ranked[0]
    top_share = top_value / total

    if top_share >= SINGLE_POSITION_CRITICAL:
        findings.append(
            Finding(
                CRITICAL,
                f"{top_ticker} is {_percent(top_share)} of your portfolio",
                f"One position carries {_percent(top_share)} of your money. Whatever happens to "
                f"{top_ticker} happens to your portfolio — the other {len(ranked) - 1} holdings are "
                "rounding errors against it. You are not diversified; you own "
                f"{top_ticker} with a hedge.",
                {"ticker": top_ticker, "share": top_share},
            )
        )
    elif top_share >= SINGLE_POSITION_WARNING:
        findings.append(
            Finding(
                WARNING,
                f"{top_ticker} is your largest position at {_percent(top_share)}",
                f"{top_ticker} is a fifth or more of the portfolio. That is a deliberate bet, so "
                "make sure it is a deliberate bet and not just the position that ran up.",
                {"ticker": top_ticker, "share": top_share},
            )
        )

    top_three_share = sum(value for _, value in ranked[:3]) / total
    if len(ranked) > 3 and top_three_share >= TOP_THREE_WARNING:
        findings.append(
            Finding(
                WARNING,
                f"Your top 3 holdings are {_percent(top_three_share)} of the portfolio",
                f"{', '.join(ticker for ticker, _ in ranked[:3])} account for "
                f"{_percent(top_three_share)}. The remaining {len(ranked) - 3} positions are doing "
                "very little work — they add admin, not diversification.",
                {"share": top_three_share, "tickers": [ticker for ticker, _ in ranked[:3]]},
            )
        )

    weights = list(values.values())
    effective = effective_holdings(weights)
    if len(ranked) > 3 and effective < EFFECTIVE_HOLDINGS_WARNING:
        findings.append(
            Finding(
                NOTE,
                f"{len(ranked)} holdings that behave like {effective:.1f}",
                f"By concentration, your {len(ranked)} positions carry about as much "
                f"diversification as {effective:.1f} equally-sized ones. Counting holdings "
                "flatters the portfolio; weighting them does not.",
                {"holdings": len(ranked), "effective_holdings": effective},
            )
        )

    return findings


def check_index_constituent_overlap(ticker_inputs: list, etf_holdings: dict = None) -> list:
    """Flag holding a fund and, separately, the things inside it.

    When real look-through data is available it is used for exact matching;
    otherwise this falls back to same-exchange overlap and says so, rather than
    asserting index membership it cannot verify.
    """
    etf_holdings = etf_holdings or {}
    values = position_values(ticker_inputs)
    total = sum(values.values())
    if total <= 0:
        return []

    funds = [t for t in ticker_inputs if (t.quote_type or "").upper() == "ETF"]
    equities = [t for t in ticker_inputs if (t.quote_type or "").upper() == "EQUITY"]
    if not funds or not equities:
        return []

    findings = []
    for fund in funds:
        known_holdings = {symbol.upper() for symbol in etf_holdings.get(fund.ticker, [])}
        if known_holdings:
            overlapping = [t for t in equities if t.ticker.upper() in known_holdings]
            basis = "confirmed against the fund's published holdings"
        else:
            suffix = _exchange_suffix(fund.ticker)
            if not suffix:
                continue
            overlapping = [t for t in equities if _exchange_suffix(t.ticker) == suffix]
            basis = (
                f"inferred from the shared {suffix} listing — the fund's holdings could not be "
                "read, so treat this as likely rather than confirmed"
            )

        if not overlapping:
            continue

        direct_share = sum(values[t.ticker] for t in overlapping) / total
        fund_share = values[fund.ticker] / total
        findings.append(
            Finding(
                WARNING,
                f"{fund.ticker} already holds {', '.join(t.ticker for t in overlapping)}",
                f"You own {fund.ticker} ({_percent(fund_share)}) and separately hold "
                f"{len(overlapping)} of its constituents ({_percent(direct_share)}). Your true "
                "exposure to those names is higher than the position weights suggest, and the "
                f"fund is not diversifying you away from them — it is adding to them. Basis: {basis}.",
                {
                    "fund": fund.ticker,
                    "overlapping": [t.ticker for t in overlapping],
                    "fund_share": fund_share,
                    "direct_share": direct_share,
                    "confirmed": bool(known_holdings),
                },
            )
        )

    return findings


def check_sector_concentration(ticker_inputs: list) -> list:
    weights = weights_by_attribute(ticker_inputs, "sector")
    known = {key: value for key, value in weights.items() if key != "Unknown"}
    if not known:
        return []

    sector, share = max(known.items(), key=lambda item: item[1])
    if share >= SECTOR_CRITICAL:
        return [
            Finding(
                CRITICAL,
                f"{_percent(share)} of the portfolio is {sector}",
                f"{sector} is {_percent(share)} of your money. Sector risk is the kind that hits "
                "every position at once — a rate move, a regulatory change or a credit cycle does "
                "not care that you spread it across several tickers.",
                {"sector": sector, "share": share},
            )
        ]
    if share >= SECTOR_WARNING:
        return [
            Finding(
                WARNING,
                f"{sector} is your largest sector at {_percent(share)}",
                f"{sector} carries {_percent(share)} of the portfolio. Worth knowing whether that "
                "is a view you hold or an accident of what you bought.",
                {"sector": sector, "share": share},
            )
        ]
    return []


def check_home_bias(ticker_inputs: list) -> list:
    weights = weights_by_attribute(ticker_inputs, "country")
    known = {key: value for key, value in weights.items() if key != "Unknown"}
    if not known:
        return []

    country, share = max(known.items(), key=lambda item: item[1])
    if share >= COUNTRY_CRITICAL:
        return [
            Finding(
                CRITICAL,
                f"{_percent(share)} of the portfolio sits in {country}",
                f"{_percent(share)} in one country is a concentrated bet on one economy, one "
                "currency and one regulatory regime. If you also earn your salary and own "
                f"property in {country}, your total exposure is higher still — your portfolio is "
                "compounding a risk you already carry rather than offsetting it.",
                {"country": country, "share": share},
            )
        ]
    if share >= COUNTRY_WARNING:
        return [
            Finding(
                WARNING,
                f"{country} is {_percent(share)} of the portfolio",
                f"Half or more of your money is in {country}. Reasonable if deliberate; worth "
                "checking it against where the rest of your financial life already sits.",
                {"country": country, "share": share},
            )
        ]
    return []


def check_currency_mismatch(ticker_inputs: list, base_currency: str) -> list:
    weights = weights_by_attribute(ticker_inputs, "native_currency")
    foreign = {
        currency: share
        for currency, share in weights.items()
        if currency not in (base_currency, "Unknown")
    }
    if not foreign:
        return []

    total_foreign = sum(foreign.values())
    if total_foreign < CURRENCY_WARNING:
        return []

    breakdown = ", ".join(f"{currency} {_percent(share)}" for currency, share in foreign.items())
    return [
        Finding(
            NOTE,
            f"{_percent(total_foreign)} of the portfolio is not in {base_currency}",
            f"You are reporting in {base_currency} but hold {breakdown}. Currency moves will show "
            "up in your returns whether or not you have a view on them, and over short horizons "
            "they can easily swamp the underlying performance.",
            {"base_currency": base_currency, "foreign_share": total_foreign, "breakdown": foreign},
        )
    ]


def check_correlation_clusters(ticker_inputs: list) -> list:
    """Report the most correlated pairs, then roll the rest into one line.

    A portfolio of n holdings has n(n-1)/2 pairs, so emitting a finding per pair
    buries every other result. Only the worst few earn their own card.
    """
    series_by_ticker = {t.ticker: t.price_series for t in ticker_inputs if t.price_series}
    if len(series_by_ticker) < 2:
        return []

    correlated = [
        (first, second, value)
        for first, second, value in correlation_pairs(series_by_ticker)
        if value >= CORRELATION_WARNING
    ]
    if not correlated:
        return []

    findings = []
    for first, second, value in correlated[:MAX_CORRELATION_FINDINGS]:
        severity = WARNING if value >= CORRELATION_CRITICAL else NOTE
        findings.append(
            Finding(
                severity,
                f"{first} and {second} move together ({value:.2f} correlation)",
                f"Monthly returns for {first} and {second} are {value:.2f} correlated. Holding both "
                "is close to holding more of one thing — they will not cushion each other when it "
                "matters, which is the moment diversification is supposed to pay.",
                {"pair": [first, second], "correlation": value},
            )
        )

    remaining = correlated[MAX_CORRELATION_FINDINGS:]
    if remaining:
        involved = sorted({ticker for first, second, _ in remaining for ticker in (first, second)})
        findings.append(
            Finding(
                WARNING if len(remaining) >= len(series_by_ticker) else NOTE,
                f"{len(remaining)} further pairs are correlated above {CORRELATION_WARNING:.2f}",
                f"Beyond the pairs listed above, {len(remaining)} more move together closely, "
                f"across {', '.join(involved)}. The portfolio has fewer independent bets in it "
                "than the number of tickers suggests.",
                {"pair_count": len(remaining), "tickers": involved},
            )
        )

    return findings


def check_speculative_positions(ticker_inputs: list) -> list:
    values = position_values(ticker_inputs)
    total = sum(values.values())
    if total <= 0:
        return []

    findings = []
    for t in ticker_inputs:
        pays_dividends = bool(t.dividend_history) or t.annual_dividend_per_share > 0
        small = t.market_cap is not None and t.market_cap < SMALL_MARKET_CAP
        extreme_growth = t.annual_growth_rate >= SPECULATIVE_GROWTH_RATE
        if pays_dividends or not extreme_growth:
            continue

        share = values[t.ticker] / total
        size_note = (
            f" Its market cap of about {t.market_cap / 1e9:.1f}B puts it well down the size scale."
            if small
            else ""
        )
        findings.append(
            Finding(
                WARNING,
                f"{t.ticker} is projected at {_percent(t.annual_growth_rate)} a year",
                f"{t.ticker} pays no dividend and its projection rests on a historical growth rate "
                f"of {_percent(t.annual_growth_rate)}. Nothing compounds at that rate for long. "
                f"Extrapolating it across the whole horizon is the single biggest source of "
                f"fiction in this projection — it is {_percent(share)} of the portfolio today but "
                f"the chart will show it becoming far more.{size_note} Set a growth rate you would "
                "actually defend, or treat this as a speculative sleeve and size it accordingly.",
                {
                    "ticker": t.ticker,
                    "growth_rate": t.annual_growth_rate,
                    "share": share,
                    "market_cap": t.market_cap,
                },
            )
        )
    return findings


def check_growth_assumptions(ticker_inputs: list) -> list:
    average = weighted_average_growth_rate(ticker_inputs)
    if average <= LONG_RUN_EQUITY_RETURN:
        return [
            Finding(
                GOOD,
                f"Your blended growth assumption is {_percent(average)}",
                f"The value-weighted growth rate across the portfolio is {_percent(average)}, at or "
                "below a defensible long-run equity return. The projection is not flattering itself.",
                {"weighted_growth_rate": average},
            )
        ]
    return [
        Finding(
            CRITICAL if average > LONG_RUN_EQUITY_RETURN * 1.5 else WARNING,
            f"The whole projection assumes {_percent(average)} a year",
            f"Your value-weighted growth rate is {_percent(average)}, against a long-run equity "
            f"return closer to {_percent(LONG_RUN_EQUITY_RETURN)}. These rates are backward-looking "
            "CAGRs from a specific window, not forecasts. Every number in the projection inherits "
            "this assumption, so if it is too high, the final figure is not slightly wrong — it is "
            "wrong by a compounding multiple.",
            {"weighted_growth_rate": average, "benchmark": LONG_RUN_EQUITY_RETURN},
        )
    ]


def check_dca_allocation(ticker_inputs: list) -> list:
    total_dca = sum(t.monthly_dca_amount for t in ticker_inputs)
    if total_dca <= 0:
        return []

    values = position_values(ticker_inputs)
    total_value = sum(values.values())
    if total_value <= 0:
        return []

    findings = []
    for t in ticker_inputs:
        if t.monthly_dca_amount <= 0:
            continue
        dca_share = t.monthly_dca_amount / total_dca
        weight = values[t.ticker] / total_value
        if dca_share >= DCA_OVERWEIGHT_SHARE and dca_share > weight:
            findings.append(
                Finding(
                    NOTE,
                    f"{_percent(dca_share)} of new money goes into {t.ticker}",
                    f"{t.ticker} is {_percent(weight)} of the portfolio today but takes "
                    f"{_percent(dca_share)} of your monthly contributions. Your concentration is "
                    "going to increase from here, not decrease — that is a choice worth making on "
                    "purpose.",
                    {"ticker": t.ticker, "dca_share": dca_share, "current_weight": weight},
                )
            )
    return findings


def check_dividend_concentration(ticker_inputs: list) -> list:
    total_income = total_annual_dividend_income(ticker_inputs)
    if total_income <= 0:
        return []

    by_ticker = {
        t.ticker: t.initial_shares * t.annual_dividend_per_share
        for t in ticker_inputs
        if t.annual_dividend_per_share > 0
    }
    if len(by_ticker) < 2:
        return []

    top_ticker, top_income = max(by_ticker.items(), key=lambda item: item[1])
    share = top_income / total_income
    if share < DIVIDEND_CONCENTRATION_WARNING:
        return []

    return [
        Finding(
            NOTE,
            f"{_percent(share)} of your dividend income comes from {top_ticker}",
            f"{top_ticker} pays {_percent(share)} of the portfolio's dividend income. If you are "
            "counting on that income, you are counting on one company's payout policy.",
            {"ticker": top_ticker, "share": share},
        )
    ]


def check_drawdowns(ticker_inputs: list) -> list:
    """One finding covering every deep drawdown, worst first."""
    drawdowns = []
    for t in ticker_inputs:
        if not t.price_series:
            continue
        drawdown = max_drawdown(t.price_series)
        if drawdown >= DRAWDOWN_WARNING:
            drawdowns.append((t.ticker, drawdown))

    if not drawdowns:
        return []

    drawdowns.sort(key=lambda item: item[1], reverse=True)
    listed = ", ".join(f"{ticker} {_percent(value)}" for ticker, value in drawdowns)
    return [
        Finding(
            NOTE,
            f"{len(drawdowns)} holding(s) have fallen more than {_percent(DRAWDOWN_WARNING)} before",
            f"Within the price history used to compute their growth rates: {listed}. The projection "
            "draws a smooth line, but earning the average return meant holding through falls like "
            "these — the question is whether you would have.",
            {"drawdowns": dict(drawdowns)},
        )
    ]


def review_portfolio(ticker_inputs: list, base_currency: str = "USD", etf_holdings: dict = None) -> list:
    """Run every check and return findings, most severe first."""
    if not ticker_inputs:
        return []

    findings = []
    findings += check_position_concentration(ticker_inputs)
    findings += check_index_constituent_overlap(ticker_inputs, etf_holdings)
    findings += check_sector_concentration(ticker_inputs)
    findings += check_home_bias(ticker_inputs)
    findings += check_currency_mismatch(ticker_inputs, base_currency)
    findings += check_correlation_clusters(ticker_inputs)
    findings += check_speculative_positions(ticker_inputs)
    findings += check_growth_assumptions(ticker_inputs)
    findings += check_dca_allocation(ticker_inputs)
    findings += check_dividend_concentration(ticker_inputs)
    findings += check_drawdowns(ticker_inputs)

    findings.sort(key=lambda finding: SEVERITY_ORDER.get(finding.severity, 99))
    return findings


def portfolio_summary(ticker_inputs: list, base_currency: str = "USD") -> dict:
    """Compact, JSON-safe description of the portfolio for the narrative layer."""
    values = position_values(ticker_inputs)
    total = sum(values.values())
    return {
        "base_currency": base_currency,
        "total_value": round(total, 2),
        "holding_count": len(ticker_inputs),
        "effective_holdings": round(effective_holdings(list(values.values())), 2),
        "concentration_index": round(herfindahl_index(list(values.values())), 4),
        "weighted_growth_rate": round(weighted_average_growth_rate(ticker_inputs), 4),
        "annual_dividend_income": round(total_annual_dividend_income(ticker_inputs), 2),
        "positions": [
            {
                "ticker": t.ticker,
                "weight": round(values[t.ticker] / total, 4) if total else 0.0,
                "value": round(values[t.ticker], 2),
                "growth_rate": round(t.annual_growth_rate, 4),
                "monthly_dca": t.monthly_dca_amount,
                "sector": t.sector,
                "country": t.country,
                "currency": t.native_currency,
                "quote_type": t.quote_type,
            }
            for t in sorted(ticker_inputs, key=lambda t: values[t.ticker], reverse=True)
        ],
    }


def findings_to_dicts(findings: list) -> list:
    return [
        {
            "severity": finding.severity,
            "title": finding.title,
            "detail": finding.detail,
            "evidence": finding.evidence,
        }
        for finding in findings
    ]
