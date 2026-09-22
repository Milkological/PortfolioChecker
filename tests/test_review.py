from datetime import date

from portfolio_checker.report_builder import TickerInput
from portfolio_checker.review import (
    CRITICAL,
    GOOD,
    MAX_CORRELATION_FINDINGS,
    NOTE,
    WARNING,
    check_correlation_clusters,
    check_currency_mismatch,
    check_dca_allocation,
    check_dividend_concentration,
    check_drawdowns,
    check_growth_assumptions,
    check_home_bias,
    check_index_constituent_overlap,
    check_position_concentration,
    check_sector_concentration,
    check_speculative_positions,
    findings_to_dicts,
    portfolio_summary,
    review_portfolio,
)


def holding(ticker, shares=1.0, price=100.0, growth=0.05, dividend=0.0, dca=0.0, **metadata):
    return TickerInput(
        ticker=ticker,
        initial_shares=shares,
        current_price=price,
        annual_growth_rate=growth,
        annual_dividend_per_share=dividend,
        monthly_dca_amount=dca,
        **metadata,
    )


def series(prices, start_year=2020):
    out = []
    year, month = start_year, 1
    for price in prices:
        out.append((date(year, month, 28), float(price)))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return out


# --- position concentration ---


def test_single_dominant_position_is_critical():
    findings = check_position_concentration(
        [holding("BIG", price=800.0), holding("A"), holding("B"), holding("C")]
    )

    assert findings[0].severity == CRITICAL
    assert "BIG" in findings[0].title


def test_moderate_largest_position_is_a_warning():
    findings = check_position_concentration(
        [holding("A", price=220.0), holding("B", price=300.0), holding("C", price=300.0), holding("D", price=200.0)]
    )

    severities = [f.severity for f in findings]
    assert CRITICAL not in severities
    assert WARNING in severities


def test_even_portfolio_raises_no_concentration_findings():
    holdings = [holding(name) for name in "ABCDEFGHIJ"]

    assert check_position_concentration(holdings) == []


def test_concentration_on_a_worthless_portfolio_is_empty():
    assert check_position_concentration([holding("A", shares=0.0, price=0.0)]) == []


def test_effective_holdings_note_appears_for_lopsided_portfolios():
    holdings = [holding("BIG", price=500.0)] + [holding(name, price=10.0) for name in "ABCDE"]

    titles = [f.title for f in check_position_concentration(holdings)]

    assert any("behave like" in title for title in titles)


# --- index / constituent overlap ---


def test_overlap_detected_between_etf_and_same_exchange_equities():
    holdings = [
        holding("ES3.SI", price=400.0, quote_type="ETF"),
        holding("D05.SI", price=300.0, quote_type="EQUITY"),
        holding("U11.SI", price=300.0, quote_type="EQUITY"),
    ]

    findings = check_index_constituent_overlap(holdings)

    assert len(findings) == 1
    assert "D05.SI" in findings[0].title and "U11.SI" in findings[0].title
    assert findings[0].evidence["confirmed"] is False
    assert "inferred" in findings[0].detail


def test_overlap_uses_published_holdings_when_available():
    holdings = [
        holding("VWRA.L", price=400.0, quote_type="ETF"),
        holding("AAPL", price=300.0, quote_type="EQUITY"),
    ]

    findings = check_index_constituent_overlap(holdings, etf_holdings={"VWRA.L": ["AAPL", "MSFT"]})

    assert findings[0].evidence["confirmed"] is True
    assert "confirmed" in findings[0].detail


def test_no_overlap_when_etf_is_on_a_different_exchange():
    holdings = [
        holding("VWRA.L", price=400.0, quote_type="ETF"),
        holding("D05.SI", price=300.0, quote_type="EQUITY"),
    ]

    assert check_index_constituent_overlap(holdings) == []


def test_no_overlap_without_any_equities():
    holdings = [holding("ES3.SI", quote_type="ETF"), holding("VWRA.L", quote_type="ETF")]

    assert check_index_constituent_overlap(holdings) == []


def test_overlap_skipped_when_quote_type_is_unknown():
    holdings = [holding("ES3.SI", price=400.0), holding("D05.SI", price=300.0)]

    assert check_index_constituent_overlap(holdings) == []


# --- sector / country / currency ---


def test_dominant_sector_is_critical():
    holdings = [
        holding("A", price=500.0, sector="Financial Services"),
        holding("B", price=300.0, sector="Technology"),
    ]

    findings = check_sector_concentration(holdings)

    assert findings[0].severity == CRITICAL
    assert "Financial Services" in findings[0].title


def test_sector_check_ignores_unknown_sectors():
    assert check_sector_concentration([holding("A"), holding("B")]) == []


def test_heavy_home_bias_is_critical():
    holdings = [
        holding("A", price=800.0, country="Singapore"),
        holding("B", price=200.0, country="United States"),
    ]

    findings = check_home_bias(holdings)

    assert findings[0].severity == CRITICAL
    assert "Singapore" in findings[0].title


def test_balanced_countries_raise_nothing():
    holdings = [
        holding("A", price=100.0, country="Singapore"),
        holding("B", price=100.0, country="United States"),
        holding("C", price=100.0, country="Japan"),
    ]

    assert check_home_bias(holdings) == []


def test_currency_mismatch_is_reported_against_the_base_currency():
    holdings = [
        holding("A", price=500.0, native_currency="SGD"),
        holding("B", price=500.0, native_currency="USD"),
    ]

    findings = check_currency_mismatch(holdings, base_currency="SGD")

    assert findings[0].severity == NOTE
    assert "USD" in findings[0].detail


def test_no_currency_finding_when_everything_matches():
    holdings = [holding("A", native_currency="SGD"), holding("B", native_currency="SGD")]

    assert check_currency_mismatch(holdings, base_currency="SGD") == []


# --- correlation ---


def test_identical_price_histories_are_flagged():
    prices = [100, 110, 105, 120, 118, 130, 125, 140, 138, 150, 147, 160, 155]
    holdings = [
        holding("A", price_series=series(prices)),
        holding("B", price_series=series(prices)),
    ]

    findings = check_correlation_clusters(holdings)

    assert findings[0].severity == WARNING
    assert "move together" in findings[0].title


def test_correlation_check_needs_two_series():
    assert check_correlation_clusters([holding("A", price_series=series([100, 110]))]) == []


def test_correlation_findings_are_capped_and_rolled_up():
    prices = [100, 110, 105, 120, 118, 130, 125, 140, 138, 150, 147, 160, 155]
    # Eight identical series produce 28 correlated pairs.
    holdings = [holding(name, price_series=series(prices)) for name in "ABCDEFGH"]

    findings = check_correlation_clusters(holdings)

    assert len(findings) == MAX_CORRELATION_FINDINGS + 1
    rollup = findings[-1]
    assert rollup.evidence["pair_count"] == 28 - MAX_CORRELATION_FINDINGS
    assert "further pairs" in rollup.title


def test_correlation_rollup_is_omitted_when_pairs_fit():
    prices = [100, 110, 105, 120, 118, 130, 125, 140, 138, 150, 147, 160, 155]
    holdings = [holding(name, price_series=series(prices)) for name in "AB"]

    findings = check_correlation_clusters(holdings)

    assert len(findings) == 1
    assert "further pairs" not in findings[0].title


def test_uncorrelated_holdings_raise_nothing():
    a = [100, 105, 98, 107, 96, 110, 99, 112, 97, 115, 101, 118, 102]
    b = [50, 49, 52, 48, 53, 47, 54, 46, 55, 45, 56, 44, 57]
    holdings = [holding("A", price_series=series(a)), holding("B", price_series=series(b))]

    findings = check_correlation_clusters(holdings)

    assert all(f.evidence.get("correlation", 0) >= 0.7 for f in findings)


# --- speculative positions ---


def test_high_growth_non_dividend_position_is_flagged():
    holdings = [holding("QBIT", growth=0.65, market_cap=800_000_000)]

    findings = check_speculative_positions(holdings)

    assert findings[0].severity == WARNING
    assert "QBIT" in findings[0].title
    assert "0.8B" in findings[0].detail


def test_dividend_payer_is_not_called_speculative():
    holdings = [holding("D05.SI", growth=0.65, dividend=2.0)]

    assert check_speculative_positions(holdings) == []


def test_modest_growth_is_not_called_speculative():
    assert check_speculative_positions([holding("A", growth=0.07)]) == []


# --- growth assumptions ---


def test_high_blended_growth_rate_is_flagged():
    findings = check_growth_assumptions([holding("A", growth=0.25)])

    assert findings[0].severity == CRITICAL


def test_slightly_high_growth_rate_is_a_warning():
    findings = check_growth_assumptions([holding("A", growth=0.10)])

    assert findings[0].severity == WARNING


def test_defensible_growth_rate_is_reported_as_good():
    findings = check_growth_assumptions([holding("A", growth=0.06)])

    assert findings[0].severity == GOOD


# --- contributions and income ---


def test_dca_into_an_already_large_position_is_noted():
    holdings = [
        holding("A", price=100.0, dca=900.0),
        holding("B", price=900.0, dca=100.0),
    ]

    findings = check_dca_allocation(holdings)

    assert findings[0].evidence["ticker"] == "A"


def test_no_dca_finding_when_nothing_is_contributed():
    assert check_dca_allocation([holding("A"), holding("B")]) == []


def test_dividend_concentration_is_noted():
    holdings = [holding("A", dividend=9.0), holding("B", dividend=1.0)]

    findings = check_dividend_concentration(holdings)

    assert findings[0].evidence["ticker"] == "A"


def test_dividend_concentration_needs_more_than_one_payer():
    assert check_dividend_concentration([holding("A", dividend=5.0)]) == []


def test_deep_drawdown_is_noted():
    holdings = [holding("A", price_series=series([100, 120, 40, 60]))]

    findings = check_drawdowns(holdings)

    assert findings[0].evidence["drawdowns"]["A"] > 0.5


def test_drawdowns_are_aggregated_into_one_finding():
    holdings = [
        holding("A", price_series=series([100, 120, 40, 60])),
        holding("B", price_series=series([100, 200, 20, 30])),
        holding("STEADY", price_series=series([100, 101, 102, 103])),
    ]

    findings = check_drawdowns(holdings)

    assert len(findings) == 1
    assert set(findings[0].evidence["drawdowns"]) == {"A", "B"}


def test_no_drawdown_finding_without_price_history():
    assert check_drawdowns([holding("A")]) == []


# --- orchestration ---


def test_review_portfolio_is_empty_for_no_holdings():
    assert review_portfolio([]) == []


def test_review_portfolio_sorts_critical_findings_first():
    holdings = [
        holding("BIG", price=900.0, growth=0.40, sector="Technology", country="United States"),
        holding("A", price=50.0, sector="Technology", country="United States"),
        holding("B", price=50.0, sector="Technology", country="United States"),
    ]

    findings = review_portfolio(holdings, base_currency="USD")

    assert findings[0].severity == CRITICAL
    severities = [f.severity for f in findings]
    assert severities == sorted(severities, key=lambda s: {"critical": 0, "warning": 1, "note": 2, "good": 3}[s])


def test_review_portfolio_survives_a_single_holding():
    findings = review_portfolio([holding("A")], base_currency="USD")

    assert isinstance(findings, list)


def test_review_portfolio_survives_missing_metadata():
    holdings = [holding("A", price=500.0), holding("B", price=500.0)]

    assert isinstance(review_portfolio(holdings), list)


def test_findings_to_dicts_is_json_safe():
    findings = review_portfolio([holding("A", price=900.0), holding("B", price=100.0)])

    import json

    json.dumps(findings_to_dicts(findings))


def test_portfolio_summary_is_json_safe_and_ranked():
    holdings = [
        holding("SMALL", price=100.0, sector="Energy"),
        holding("BIG", price=900.0, sector="Financial Services"),
    ]

    summary = portfolio_summary(holdings, base_currency="SGD")

    import json

    json.dumps(summary)
    assert summary["positions"][0]["ticker"] == "BIG"
    assert summary["total_value"] == 1000.0
    assert summary["base_currency"] == "SGD"


def test_portfolio_summary_handles_a_worthless_portfolio():
    summary = portfolio_summary([holding("A", shares=0.0, price=0.0)])

    assert summary["total_value"] == 0.0
    assert summary["positions"][0]["weight"] == 0.0
