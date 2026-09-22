from portfolio_checker.dashboard_app import (
    build_chart_for_selection,
    build_review_output,
    chart_title_for_tickers,
    cpf_member_from_inputs,
    fetch_cpf_fx_rate,
    row_style_for_selection,
    select_chart_tickers,
    toggle_display_style,
)
from portfolio_checker.report_builder import TickerInput
from portfolio_checker.review_narrative import NarrativeResult


def _render(children):
    """Flatten a Dash component tree into its text, for assertions."""
    if isinstance(children, str):
        return children
    if isinstance(children, (list, tuple)):
        return " ".join(_render(child) for child in children)
    inner = getattr(children, "children", None)
    return _render(inner) if inner is not None else ""


CONCENTRATED = [
    TickerInput("BIG", 900.0, 1.0, 0.05, 0.0, 0.0),
    TickerInput("SMALL", 100.0, 1.0, 0.05, 0.0, 0.0),
]


# --- charts -----------------------------------------------------------------


def test_build_chart_for_selection_uses_given_title():
    inputs = [
        TickerInput("A", 10.0, 100.0, 0.0, 0.0, 50.0),
        TickerInput("B", 5.0, 200.0, 0.0, 0.0, 0.0),
    ]

    fig = build_chart_for_selection(inputs, years=1, currency="USD", title="Total Portfolio")

    assert fig.layout.title.text == "Total Portfolio"


def test_build_chart_for_selection_single_ticker_subset():
    inputs = [TickerInput("A", 10.0, 100.0, 0.0, 0.0, 50.0)]

    fig = build_chart_for_selection(inputs, years=1, currency="USD", title="A")

    assert fig.layout.title.text == "A"
    # A's total value line should reflect only A's own contributions (1000 initial + 600 DCA)
    total_trace = fig.data[-1]
    assert list(total_trace.y) == [1000.0, 1600.0]


def test_build_chart_for_selection_folds_in_extra_rows():
    inputs = [TickerInput("A", 10.0, 100.0, 0.0, 0.0, 0.0)]
    cpf_rows = [
        {"year": 0, "contributed_total": 500.0, "dividend_income": 0.0, "growth_gain": 0.0, "total_value": 500.0},
        {"year": 1, "contributed_total": 500.0, "dividend_income": 0.0, "growth_gain": 20.0, "total_value": 520.0},
    ]

    fig = build_chart_for_selection(inputs, years=1, currency="SGD", title="Total", extra_rows=cpf_rows)

    total_trace = fig.data[-1]
    assert list(total_trace.y) == [1500.0, 1520.0]


# --- layout helpers ---------------------------------------------------------


def test_toggle_display_style_opens_when_closed():
    assert toggle_display_style({"display": "none"}) == {"display": "block"}


def test_toggle_display_style_closes_when_open():
    assert toggle_display_style({"display": "block"}) == {"display": "none"}


def test_select_chart_tickers_returns_all_when_none_open():
    assert select_chart_tickers(["A", "B", "C"], set()) == ["A", "B", "C"]


def test_select_chart_tickers_returns_open_subset_in_original_order():
    assert select_chart_tickers(["A", "B", "C"], {"C", "A"}) == ["A", "C"]


def test_chart_title_for_tickers_is_total_portfolio_when_none_open():
    assert chart_title_for_tickers(["A", "B", "C"], ["A", "B", "C"]) == "Total Portfolio"


def test_chart_title_for_tickers_joins_selected_tickers():
    assert chart_title_for_tickers(["A", "C"], ["A", "B", "C"]) == "A + C"


def test_row_style_for_selection_highlights_when_selected():
    assert row_style_for_selection(True).get("backgroundColor") == "#fff8db"


def test_row_style_for_selection_default_when_not_selected():
    assert "backgroundColor" not in row_style_for_selection(False)


# --- CPF --------------------------------------------------------------------


def test_cpf_member_from_inputs_converts_growth_percent_to_a_rate():
    member = cpf_member_from_inputs(32, 7000, 2, 12, 3, 45000, 30000, 25000)

    assert member.salary_growth_rate == 0.03
    assert member.age == 32.0
    assert member.bonus_month == 12


def test_cpf_member_from_inputs_tolerates_cleared_fields():
    member = cpf_member_from_inputs(None, None, None, None, None, None, None, None)

    assert member.age == 30.0
    assert member.monthly_salary == 0.0
    assert member.bonus_month == 12


def test_fetch_cpf_fx_rate_is_one_for_sgd():
    assert fetch_cpf_fx_rate("SGD") == 1.0


def test_fetch_cpf_fx_rate_falls_back_when_lookup_fails(monkeypatch):
    def boom(from_currency, to_currency):
        raise ValueError("no network")

    monkeypatch.setattr("portfolio_checker.dashboard_app.get_fx_rate", boom)
    messages = []

    assert fetch_cpf_fx_rate("USD", print_func=messages.append) == 1.0
    assert "Could not fetch" in messages[0]


# --- review panel -----------------------------------------------------------


def no_provider(findings, summary):
    return [NarrativeResult(error="no key")]


def test_build_review_output_reports_no_holdings():
    assert "Nothing to review" in _render(build_review_output([], "SGD"))


def test_build_review_output_includes_rule_findings_and_the_disclaimer():
    rendered = _render(build_review_output(CONCENTRATED, "SGD", narrator=no_provider))

    assert "BIG" in rendered
    assert "not financial advice" in rendered


def test_build_review_output_explains_why_the_narrative_is_missing():
    rendered = _render(build_review_output(CONCENTRATED, "SGD", narrator=no_provider))

    assert "no key" in rendered
    assert "Showing the rule-based findings" in rendered


def test_build_review_output_shows_the_narrative_when_available():
    def narrator(findings, summary):
        return [
            NarrativeResult(
                text="This portfolio is one bet.", provider="Gemini", model="gemini-3.8-flash"
            )
        ]

    rendered = _render(build_review_output(CONCENTRATED, "SGD", narrator=narrator))

    assert "This portfolio is one bet." in rendered
    assert "Written by Gemini (gemini-3.8-flash)" in rendered
    # A successful narrative means no rule-based fallback notice.
    assert "Showing the rule-based findings" not in rendered


def test_build_review_output_stacks_one_block_per_provider():
    def narrator(findings, summary):
        return [
            NarrativeResult(text="claude says", provider="Claude", model="claude-opus-5"),
            NarrativeResult(text="gemini says", provider="Gemini", model="gemini-3.8-flash"),
        ]

    rendered = _render(build_review_output(CONCENTRATED, "SGD", narrator=narrator))

    assert "claude says" in rendered
    assert "gemini says" in rendered


def test_build_review_output_shows_a_failure_alongside_a_success():
    def narrator(findings, summary):
        return [
            NarrativeResult(error="Claude: the API key was rejected", provider="Claude"),
            NarrativeResult(text="gemini says", provider="Gemini", model="gemini-3.8-flash"),
        ]

    rendered = _render(build_review_output(CONCENTRATED, "SGD", narrator=narrator))

    assert "the API key was rejected" in rendered
    assert "gemini says" in rendered
    assert "Showing the rule-based findings" not in rendered


def test_build_review_output_passes_json_safe_arguments_to_the_narrator():
    captured = {}

    def narrator(findings, summary):
        captured["findings"] = findings
        captured["summary"] = summary
        return [NarrativeResult(error="stub")]

    build_review_output(CONCENTRATED, "SGD", narrator=narrator)

    import json

    json.dumps(captured["findings"])
    json.dumps(captured["summary"])
    assert captured["summary"]["base_currency"] == "SGD"
