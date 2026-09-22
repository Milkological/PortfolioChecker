import dash
from dash import ALL, MATCH, Input, Output, State, dcc, html

from portfolio_checker.cli import collect_holdings, fetch_market_data_for_ticker, load_holdings_from_csv
from portfolio_checker.cli_parsing import VALID_LOOKBACK_PERIODS, parse_currency_code, parse_lookback_period
from portfolio_checker.cpf import CpfMember, build_cpf_yearly_summary, simulate_cpf
from portfolio_checker.cpf_io import DEFAULT_CPF_FILE, load_cpf_from_csv, write_cpf_csv
from portfolio_checker.dividend_history import (
    dividends_paid_this_calendar_year,
    estimate_next_dividend_date,
    recent_dividend_payments,
)
from portfolio_checker.plotly_view import build_stacked_figure
from portfolio_checker.portfolio_stats import breakdown_by_attribute
from portfolio_checker.market_data import (
    describe_high_growth_warning,
    fetch_etf_holdings,
    fetch_growth_rate_for_period,
    get_fx_rate,
    get_ticker,
)
from portfolio_checker.review import (
    CRITICAL,
    DISCLAIMER,
    GOOD,
    NOTE,
    WARNING,
    findings_to_dicts,
    portfolio_summary,
    review_portfolio,
)
from portfolio_checker.review_narrative import narrate_all
from portfolio_checker.report_builder import (
    TickerInput,
    build_report_data,
    combine_summary_rows,
    portfolio_share_percentage,
    review_metadata,
    scale_summary_rows,
    total_annual_dividend_income,
    total_portfolio_value,
    weighted_average_growth_rate,
)

CPF_CURRENCY = "SGD"


def toggle_display_style(current_style: dict) -> dict:
    return {"display": "none"} if current_style.get("display") == "block" else {"display": "block"}


ROW_STYLE = {"display": "flex", "flexDirection": "row", "border": "1px solid #ccc", "padding": "10px", "margin": "5px 0", "alignItems": "flex-start"}
ROW_STYLE_SELECTED = {**ROW_STYLE, "backgroundColor": "#fff8db", "border": "2px solid #f0c419"}


def row_style_for_selection(is_selected: bool) -> dict:
    return dict(ROW_STYLE_SELECTED) if is_selected else dict(ROW_STYLE)


def select_chart_tickers(all_tickers: list, open_tickers: set) -> list:
    if not open_tickers:
        return list(all_tickers)
    return [ticker for ticker in all_tickers if ticker in open_tickers]


def chart_title_for_tickers(selected_tickers: list, all_tickers: list) -> str:
    if selected_tickers == list(all_tickers):
        return "Total Portfolio"
    return " + ".join(selected_tickers)


def build_chart_for_selection(ticker_inputs, years, currency, title, extra_rows=None):
    total_rows, _ = build_report_data(ticker_inputs, years)
    if extra_rows:
        total_rows = combine_summary_rows(total_rows, extra_rows)
    return build_stacked_figure(total_rows, currency=currency, title=title)


def fetch_cpf_fx_rate(base_currency, print_func=print):
    """SGD to base-currency rate, fetched once so callbacks never hit the network."""
    try:
        return get_fx_rate(CPF_CURRENCY, base_currency)
    except Exception as exc:
        print_func(f"Could not fetch {CPF_CURRENCY}/{base_currency} rate ({exc}); showing CPF in {CPF_CURRENCY}.")
        return 1.0


def gather_starting_data(input_func=input, print_func=print, holdings_file=None, cpf_file=DEFAULT_CPF_FILE):
    if holdings_file:
        holdings = load_holdings_from_csv(holdings_file)
    else:
        holdings = collect_holdings(input_func)
    if not holdings:
        raise SystemExit("No holdings entered — nothing to project.")

    base_currency = parse_currency_code(
        input_func("What currency should totals be shown in? (e.g. USD, SGD): ")
    )
    lookback_period = parse_lookback_period(
        input_func("Price history window for growth rate calculation (3y/5y/10y/max) [default 5y]: "), default="5y"
    )

    ticker_inputs = []
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
        ticker_inputs.append(
            TickerInput(
                ticker=holding["ticker"],
                initial_shares=holding["shares"],
                current_price=data.current_price,
                annual_growth_rate=data.annual_growth_rate,
                annual_dividend_per_share=data.annual_dividend_per_share,
                monthly_dca_amount=holding["dca"],
                dividend_history=data.dividend_history,
                company_summary=data.company_summary,
                **review_metadata(data),
            )
        )

    if not ticker_inputs:
        raise SystemExit("No holdings left after data lookup — nothing to project.")

    cpf_member = load_cpf_from_csv(cpf_file)
    cpf_fx_rate = fetch_cpf_fx_rate(base_currency, print_func)
    etf_holdings = fetch_etf_look_through(ticker_inputs)

    return ticker_inputs, base_currency, cpf_member, cpf_fx_rate, etf_holdings


def fetch_etf_look_through(ticker_inputs):
    """Constituents of any ETFs held, fetched once so the review stays offline."""
    holdings = {}
    for t in ticker_inputs:
        if (t.quote_type or "").upper() != "ETF":
            continue
        constituents = fetch_etf_holdings(get_ticker(t.ticker))
        if constituents:
            holdings[t.ticker] = constituents
    return holdings


def _growth_warning_text(annual_growth_rate):
    warning = describe_high_growth_warning(annual_growth_rate)
    return f"⚠ {warning}" if warning else ""


def _ticker_detail_content(t, shares, current_price, total_value):
    position_value = shares * current_price
    percent = portfolio_share_percentage(position_value, total_value)
    ytd_dividends = dividends_paid_this_calendar_year(t.dividend_history, shares)
    next_payment = estimate_next_dividend_date(t.dividend_history)
    recent_payments = recent_dividend_payments(t.dividend_history, count=4)

    lines = [
        html.P(f"Current price: {current_price:,.4f}"),
        html.P(f"Position value: {position_value:,.2f} ({percent:.1f}% of portfolio)"),
        html.P(f"Dividends paid this calendar year: {ytd_dividends:,.2f}"),
        html.P(f"Next expected payment: {next_payment.isoformat() if next_payment else 'unknown'}"),
        html.P("Recent payments:"),
    ]
    if recent_payments:
        lines.append(
            html.Ul([html.Li(f"{payment_date.isoformat()}: {amount:,.4f}/share") for payment_date, amount in recent_payments])
        )
    else:
        lines.append(html.P("No dividend history available."))
    return lines


TABLE_CELL_STYLE = {"padding": "3px 10px 3px 0", "textAlign": "left"}


def _holding_breakdown_table(current_inputs, total_value, currency):
    header = html.Tr(
        [
            html.Th(label, style=TABLE_CELL_STYLE)
            for label in (
                "Holding",
                "Shares",
                "Sector",
                "Industry",
                "Annual Growth Rate",
                "Annual Dividend Income",
                "% of Portfolio",
            )
        ]
    )
    rows = []
    for t in current_inputs:
        position_value = t.initial_shares * t.current_price
        percent = portfolio_share_percentage(position_value, total_value)
        dividend_income = t.initial_shares * t.annual_dividend_per_share
        rows.append(
            html.Tr(
                [
                    html.Td(t.ticker, style=TABLE_CELL_STYLE),
                    html.Td(f"{t.initial_shares:,.3f}", style=TABLE_CELL_STYLE),
                    html.Td(t.sector or "—", style=TABLE_CELL_STYLE),
                    html.Td(t.industry or "—", style=TABLE_CELL_STYLE),
                    html.Td(f"{t.annual_growth_rate * 100:.2f}%", style=TABLE_CELL_STYLE),
                    html.Td(f"{dividend_income:,.2f} {currency}", style=TABLE_CELL_STYLE),
                    html.Td(f"{percent:.1f}%", style=TABLE_CELL_STYLE),
                ]
            )
        )
    return html.Table([html.Thead(header), html.Tbody(rows)])


def _attribute_breakdown_table(current_inputs, attribute, currency, label):
    """Portfolio value grouped by sector / industry / country, largest first."""
    groups = breakdown_by_attribute(current_inputs, attribute, unknown_label="Unclassified")
    if not groups:
        return html.P(f"No {label.lower()} data available.")

    header = html.Tr(
        [
            html.Th(label, style=TABLE_CELL_STYLE),
            html.Th("Value", style=TABLE_CELL_STYLE),
            html.Th("% of Portfolio", style=TABLE_CELL_STYLE),
            html.Th("Holdings", style=TABLE_CELL_STYLE),
        ]
    )
    rows = [
        html.Tr(
            [
                html.Td(group["key"], style=TABLE_CELL_STYLE),
                html.Td(f"{group['value']:,.2f} {currency}", style=TABLE_CELL_STYLE),
                html.Td(f"{group['weight'] * 100:.1f}%", style=TABLE_CELL_STYLE),
                html.Td(", ".join(group["tickers"]), style=TABLE_CELL_STYLE),
            ]
        )
        for group in groups
    ]
    return html.Table([html.Thead(header), html.Tbody(rows)])


def _total_portfolio_detail_content(current_inputs, currency, cpf_value=0.0):
    total_value = total_portfolio_value(current_inputs)
    total_dividend = total_annual_dividend_income(current_inputs)
    average_growth = weighted_average_growth_rate(current_inputs)

    lines = [
        html.P(f"Total portfolio value: {total_value:,.2f} {currency}"),
        html.P(f"Average annual growth rate (value-weighted): {average_growth * 100:.2f}%"),
        html.P(f"Total annual dividend income: {total_dividend:,.2f} {currency}"),
    ]
    if cpf_value:
        lines.append(html.P(f"CPF balance: {cpf_value:,.2f} {currency}"))
        lines.append(
            html.P(
                f"Total including CPF: {total_value + cpf_value:,.2f} {currency}",
                style={"fontWeight": "bold"},
            )
        )
    lines.append(html.H5("By sector", style={"marginBottom": "4px"}))
    lines.append(_attribute_breakdown_table(current_inputs, "sector", currency, "Sector"))

    lines.append(html.H5("By industry", style={"marginBottom": "4px"}))
    lines.append(_attribute_breakdown_table(current_inputs, "industry", currency, "Industry"))

    lines.append(html.H5("By country", style={"marginBottom": "4px"}))
    lines.append(_attribute_breakdown_table(current_inputs, "country", currency, "Country"))

    lines.append(html.H5("By holding", style={"marginBottom": "4px"}))
    lines.append(_holding_breakdown_table(current_inputs, total_value, currency))
    return lines


def _total_portfolio_card():
    return html.Div(
        [
            html.Div(
                [
                    html.H4("Total Portfolio", style={"display": "inline-block", "marginRight": "10px"}),
                    html.Button("Details", id="toggle-total", n_clicks=0),
                ]
            ),
            html.Div(
                id="detail-total",
                style={"display": "none"},
                children=[html.Div(id="total-detail-content")],
            ),
        ],
        style={"border": "1px solid #ccc", "padding": "10px", "margin": "10px", "display": "inline-block"},
    )


DEFAULT_CPF_MEMBER = CpfMember(age=30.0, monthly_salary=0.0)


def _number(value, default=0.0):
    """dcc.Input returns None when a field is cleared — treat that as the default."""
    return default if value is None else float(value)


def _cpf_field(label, input_id, value, **input_kwargs):
    return html.Div(
        [
            html.Label(label, style={"display": "block", "fontSize": "0.85em"}),
            dcc.Input(id=input_id, type="number", value=value, **input_kwargs),
        ],
        style={"marginBottom": "8px"},
    )


def _cpf_card(member):
    member = member or DEFAULT_CPF_MEMBER

    inputs_column = html.Div(
        [
            _cpf_field("Age", "cpf-age", member.age, min=0, max=54),
            _cpf_field("Monthly salary (SGD)", "cpf-salary", member.monthly_salary, min=0),
            _cpf_field("Bonus (months of salary)", "cpf-bonus-months", member.annual_bonus_months, min=0),
            _cpf_field("Bonus paid in month", "cpf-bonus-month", member.bonus_month, min=1, max=12, step=1),
            _cpf_field("Annual salary growth (%)", "cpf-growth", member.salary_growth_rate * 100),
        ],
        style={"flex": "1 1 220px", "minWidth": "200px"},
    )

    balances_column = html.Div(
        [
            _cpf_field("Ordinary Account (SGD)", "cpf-oa", member.oa_balance, min=0),
            _cpf_field("Special Account (SGD)", "cpf-sa", member.sa_balance, min=0),
            _cpf_field("MediSave Account (SGD)", "cpf-ma", member.ma_balance, min=0),
            dcc.Checklist(
                id="cpf-include",
                options=[{"label": " Include CPF in Total Portfolio", "value": "include"}],
                value=[],
                style={"marginTop": "12px"},
            ),
            html.Span(id="cpf-save-status", style={"fontSize": "0.8em", "color": "#666"}),
        ],
        style={"flex": "1 1 220px", "minWidth": "200px"},
    )

    detail_column = html.Div(
        id="cpf-detail-content",
        style={"flex": "2 1 320px", "padding": "0 20px"},
    )

    return html.Div(
        [
            html.H4("CPF"),
            html.Div(
                [inputs_column, balances_column, detail_column],
                style={"display": "flex", "flexDirection": "row", "alignItems": "flex-start"},
            ),
            dcc.Graph(id="cpf-chart"),
        ],
        style={"border": "1px solid #ccc", "padding": "10px", "margin": "10px 5px"},
    )


def cpf_member_from_inputs(age, salary, bonus_months, bonus_month, growth_percent, oa, sa, ma):
    return CpfMember(
        age=_number(age, DEFAULT_CPF_MEMBER.age),
        monthly_salary=_number(salary),
        annual_bonus_months=_number(bonus_months),
        bonus_month=int(_number(bonus_month, 12)),
        salary_growth_rate=_number(growth_percent) / 100,
        oa_balance=_number(oa),
        sa_balance=_number(sa),
        ma_balance=_number(ma),
    )


def _cpf_detail_content(result, member, currency, fx_rate):
    def money(amount_sgd):
        return f"{amount_sgd * fx_rate:,.2f} {currency}"

    starting_total = result.total[0]
    final_total = result.total[-1]
    total_contributed = sum(result.contributions)
    total_interest = final_total - starting_total - total_contributed
    years_projected = result.months_simulated / 12

    lines = [
        html.P(f"CPF today: {money(starting_total)}"),
        html.P(
            f"Projected in {years_projected:.0f} year(s) (age {member.age + years_projected:.0f}): "
            f"{money(final_total)}"
        ),
        html.Ul(
            [
                html.Li(f"Ordinary Account: {money(result.oa[-1])}"),
                html.Li(f"Special Account: {money(result.sa[-1])}"),
                html.Li(f"MediSave Account: {money(result.ma[-1])}"),
            ]
        ),
        html.P(f"Contributions over the period: {money(total_contributed)}"),
        html.P(f"Interest earned over the period: {money(total_interest)}"),
    ]

    if result.stopped_at_55:
        lines.append(
            html.P(
                "Projection stops at age 55 — the Retirement Account, Full Retirement Sum "
                "top-ups and CPF LIFE payouts are not modelled.",
                style={"color": "#b45309"},
            )
        )
    if fx_rate != 1.0:
        lines.append(
            html.P(
                f"Converted from SGD at {fx_rate:,.4f} {currency}/SGD.",
                style={"fontSize": "0.85em", "color": "#666"},
            )
        )

    return lines


SEVERITY_STYLES = {
    CRITICAL: {"label": "CRITICAL", "color": "#991b1b", "background": "#fef2f2", "border": "#dc2626"},
    WARNING: {"label": "WARNING", "color": "#b45309", "background": "#fffbeb", "border": "#f59e0b"},
    NOTE: {"label": "NOTE", "color": "#1e40af", "background": "#eff6ff", "border": "#3b82f6"},
    GOOD: {"label": "WORKING", "color": "#166534", "background": "#f0fdf4", "border": "#22c55e"},
}


def _finding_card(finding):
    style = SEVERITY_STYLES.get(finding.severity, SEVERITY_STYLES[NOTE])
    return html.Div(
        [
            html.Div(
                style["label"],
                style={
                    "color": style["color"],
                    "fontWeight": "bold",
                    "fontSize": "0.75em",
                    "letterSpacing": "0.05em",
                },
            ),
            html.Div(finding.title, style={"fontWeight": "bold", "margin": "4px 0"}),
            html.Div(finding.detail, style={"fontSize": "0.9em", "lineHeight": "1.5"}),
        ],
        style={
            "backgroundColor": style["background"],
            "borderLeft": f"4px solid {style['border']}",
            "padding": "10px 14px",
            "margin": "8px 0",
        },
    )


def _review_card():
    return html.Div(
        [
            html.Div(
                [
                    html.H4("Portfolio Review", style={"display": "inline-block", "marginRight": "10px"}),
                    html.Button("Run review", id="run-review", n_clicks=0),
                ]
            ),
            html.P(
                "Checks concentration, fund/holding overlap, correlation, currency and the growth "
                "assumptions behind the projection. Uses the values currently in the inputs above.",
                style={"fontSize": "0.85em", "color": "#666"},
            ),
            dcc.Loading(html.Div(id="review-output")),
        ],
        style={"border": "1px solid #ccc", "padding": "10px", "margin": "10px 5px"},
    )


def _narrative_block(result):
    if result.succeeded:
        byline = f"Written by {result.provider} ({result.model}) from the findings below"
        return html.Div(
            [
                html.Div(
                    byline,
                    style={"fontSize": "0.75em", "color": "#666", "marginBottom": "6px"},
                ),
                dcc.Markdown(result.text),
            ],
            style={"backgroundColor": "#fafafa", "padding": "12px 16px", "margin": "8px 0"},
        )
    return html.P(
        result.error,
        style={"fontSize": "0.85em", "color": "#666", "fontStyle": "italic", "margin": "4px 0"},
    )


def build_review_output(ticker_inputs, base_currency, etf_holdings=None, narrator=narrate_all):
    """Run the rule engine, then have every configured provider write it up."""
    findings = review_portfolio(ticker_inputs, base_currency, etf_holdings)
    if not findings:
        return [html.P("Nothing to review — no holdings.")]

    results = narrator(findings_to_dicts(findings), portfolio_summary(ticker_inputs, base_currency))
    children = [_narrative_block(result) for result in results]

    if not any(result.succeeded for result in results):
        children.append(
            html.P(
                "Showing the rule-based findings.",
                style={"fontSize": "0.85em", "color": "#666", "fontStyle": "italic"},
            )
        )

    children.extend(_finding_card(finding) for finding in findings)
    children.append(
        html.P(DISCLAIMER, style={"fontSize": "0.8em", "color": "#666", "marginTop": "14px"})
    )
    return children


def _ticker_controls(t):
    checkbox_column = html.Div(
        [
            dcc.Checklist(
                id={"type": "chart-select", "ticker": t.ticker},
                options=[{"label": " Show in chart", "value": "selected"}],
                value=[],
            ),
        ],
        style={"flex": "0 0 110px"},
    )

    variables_column = html.Div(
        [
            html.H4(t.ticker),
            html.Label("Initial shares"),
            dcc.Input(id={"type": "shares", "ticker": t.ticker}, type="number", value=t.initial_shares, min=0),
            html.Label("Monthly DCA"),
            dcc.Input(id={"type": "dca", "ticker": t.ticker}, type="number", value=t.monthly_dca_amount, min=0),
            html.Label("Annual growth rate (%)"),
            dcc.Input(
                id={"type": "growth", "ticker": t.ticker},
                type="number",
                value=round(t.annual_growth_rate * 100, 2),
            ),
            html.Label("CAGR lookback period"),
            dcc.Loading(
                dcc.Dropdown(
                    id={"type": "lookback", "ticker": t.ticker},
                    options=list(VALID_LOOKBACK_PERIODS),
                    value="5y",
                    clearable=False,
                ),
            ),
            html.Span(
                id={"type": "growth-warning", "ticker": t.ticker},
                children=_growth_warning_text(t.annual_growth_rate),
                style={"color": "#b45309", "display": "block"},
            ),
            html.Label("Annual dividend per share"),
            dcc.Input(
                id={"type": "dividend", "ticker": t.ticker},
                type="number",
                value=t.annual_dividend_per_share,
                min=0,
            ),
        ],
        style={"flex": "1 1 280px", "minWidth": "250px"},
    )

    details_column = html.Div(
        id={"type": "detail-content", "ticker": t.ticker},
        style={"flex": "2 1 300px", "padding": "0 20px"},
    )

    summary_column = html.Div(
        [
            html.Strong("About"),
            html.P(t.company_summary, style={"marginTop": "5px"}),
        ],
        style={"flex": "2 1 300px", "padding": "0 20px", "fontSize": "0.9em", "color": "#444"},
    )

    return html.Div(
        [checkbox_column, variables_column, details_column, summary_column],
        id={"type": "row", "ticker": t.ticker},
        style=row_style_for_selection(False),
    )


def build_app(
    ticker_inputs,
    currency,
    default_years=10,
    cpf_member=None,
    cpf_fx_rate=1.0,
    cpf_file=DEFAULT_CPF_FILE,
    etf_holdings=None,
):
    app = dash.Dash(__name__)
    tickers = [t.ticker for t in ticker_inputs]

    app.layout = html.Div(
        [
            html.H2("Portfolio Checker — Interactive Projection"),
            html.Label("Projection years"),
            dcc.Slider(
                id="years",
                min=1,
                max=30,
                step=1,
                value=default_years,
                marks={i: str(i) for i in range(0, 31, 5)},
            ),
            html.Div([_ticker_controls(t) for t in ticker_inputs]),
            _total_portfolio_card(),
            dcc.Graph(id="chart"),
            _cpf_card(cpf_member),
            _review_card(),
        ]
    )

    @app.callback(
        Output("chart", "figure"),
        Output("total-detail-content", "children"),
        Output({"type": "growth-warning", "ticker": ALL}, "children"),
        Output({"type": "detail-content", "ticker": ALL}, "children"),
        Output("cpf-chart", "figure"),
        Output("cpf-detail-content", "children"),
        Input("years", "value"),
        Input({"type": "chart-select", "ticker": ALL}, "value"),
        Input({"type": "shares", "ticker": ALL}, "value"),
        Input({"type": "dca", "ticker": ALL}, "value"),
        Input({"type": "growth", "ticker": ALL}, "value"),
        Input({"type": "dividend", "ticker": ALL}, "value"),
        Input("cpf-age", "value"),
        Input("cpf-salary", "value"),
        Input("cpf-bonus-months", "value"),
        Input("cpf-bonus-month", "value"),
        Input("cpf-growth", "value"),
        Input("cpf-oa", "value"),
        Input("cpf-sa", "value"),
        Input("cpf-ma", "value"),
        Input("cpf-include", "value"),
    )
    def update_chart(
        years,
        chart_selected,
        shares_values,
        dca_values,
        growth_values,
        dividend_values,
        cpf_age,
        cpf_salary,
        cpf_bonus_months,
        cpf_bonus_month,
        cpf_growth,
        cpf_oa,
        cpf_sa,
        cpf_ma,
        cpf_include,
    ):
        current_inputs = [
            TickerInput(
                ticker=t.ticker,
                initial_shares=shares_values[i],
                current_price=t.current_price,
                annual_growth_rate=growth_values[i] / 100,
                annual_dividend_per_share=dividend_values[i],
                monthly_dca_amount=dca_values[i],
                dividend_history=t.dividend_history,
                company_summary=t.company_summary,
                **review_metadata(t),
            )
            for i, t in enumerate(ticker_inputs)
        ]
        growth_warnings = [_growth_warning_text(rate / 100) for rate in growth_values]
        portfolio_value = total_portfolio_value(current_inputs)
        detail_contents = [
            _ticker_detail_content(t, shares_values[i], t.current_price, portfolio_value)
            for i, t in enumerate(ticker_inputs)
        ]

        member = cpf_member_from_inputs(
            cpf_age, cpf_salary, cpf_bonus_months, cpf_bonus_month, cpf_growth, cpf_oa, cpf_sa, cpf_ma
        )
        cpf_result = simulate_cpf(member, months=years * 12)
        cpf_rows = scale_summary_rows(build_cpf_yearly_summary(cpf_result), cpf_fx_rate)
        cpf_chart = build_stacked_figure(cpf_rows, currency=currency, title="CPF")
        cpf_detail_content = _cpf_detail_content(cpf_result, member, currency, cpf_fx_rate)

        include_cpf = "include" in (cpf_include or [])
        cpf_value = cpf_result.total[0] * cpf_fx_rate if include_cpf else 0.0
        total_detail_content = _total_portfolio_detail_content(current_inputs, currency, cpf_value)

        checked_tickers = {t.ticker for t, checked in zip(ticker_inputs, chart_selected) if "selected" in checked}
        selected_tickers = select_chart_tickers(tickers, checked_tickers)
        title = chart_title_for_tickers(selected_tickers, tickers)
        selected_inputs = [t for t in current_inputs if t.ticker in set(selected_tickers)]

        # CPF only folds into the chart when the chart is actually showing the
        # whole portfolio, not a hand-picked subset of tickers.
        showing_whole_portfolio = selected_tickers == list(tickers)
        extra_rows = cpf_rows if include_cpf and showing_whole_portfolio else None
        if extra_rows:
            title = f"{title} + CPF"
        chart = build_chart_for_selection(selected_inputs, years, currency, title, extra_rows=extra_rows)

        return (
            chart,
            total_detail_content,
            growth_warnings,
            detail_contents,
            cpf_chart,
            cpf_detail_content,
        )

    @app.callback(
        Output("review-output", "children"),
        Input("run-review", "n_clicks"),
        State({"type": "shares", "ticker": ALL}, "value"),
        State({"type": "dca", "ticker": ALL}, "value"),
        State({"type": "growth", "ticker": ALL}, "value"),
        State({"type": "dividend", "ticker": ALL}, "value"),
        prevent_initial_call=True,
    )
    def run_review(n_clicks, shares_values, dca_values, growth_values, dividend_values):
        current_inputs = [
            TickerInput(
                ticker=t.ticker,
                initial_shares=_number(shares_values[i]),
                current_price=t.current_price,
                annual_growth_rate=_number(growth_values[i]) / 100,
                annual_dividend_per_share=_number(dividend_values[i]),
                monthly_dca_amount=_number(dca_values[i]),
                dividend_history=t.dividend_history,
                company_summary=t.company_summary,
                **review_metadata(t),
            )
            for i, t in enumerate(ticker_inputs)
        ]
        return build_review_output(current_inputs, currency, etf_holdings)

    @app.callback(
        Output("cpf-save-status", "children"),
        Input("cpf-age", "value"),
        Input("cpf-salary", "value"),
        Input("cpf-bonus-months", "value"),
        Input("cpf-bonus-month", "value"),
        Input("cpf-growth", "value"),
        Input("cpf-oa", "value"),
        Input("cpf-sa", "value"),
        Input("cpf-ma", "value"),
        prevent_initial_call=True,
    )
    def save_cpf(age, salary, bonus_months, bonus_month, growth, oa, sa, ma):
        if age is None:
            return "Age is required to save."
        member = cpf_member_from_inputs(age, salary, bonus_months, bonus_month, growth, oa, sa, ma)
        try:
            write_cpf_csv(member, cpf_file)
        except OSError as exc:
            return f"Could not save: {exc}"
        return f"Saved to {cpf_file}"

    @app.callback(
        Output("detail-total", "style"),
        Input("toggle-total", "n_clicks"),
        State("detail-total", "style"),
        prevent_initial_call=True,
    )
    def toggle_total_detail(n_clicks, current_style):
        return toggle_display_style(current_style)

    @app.callback(
        Output({"type": "row", "ticker": MATCH}, "style"),
        Input({"type": "chart-select", "ticker": MATCH}, "value"),
    )
    def update_row_highlight(checked_values):
        return row_style_for_selection("selected" in checked_values)

    @app.callback(
        Output({"type": "growth", "ticker": MATCH}, "value"),
        Input({"type": "lookback", "ticker": MATCH}, "value"),
        prevent_initial_call=True,
    )
    def update_growth_rate_for_lookback(period):
        ticker = dash.ctx.triggered_id["ticker"]
        rate = fetch_growth_rate_for_period(ticker, period)
        return round(rate * 100, 2)

    return app


def run(input_func=input, print_func=print, holdings_file=None, cpf_file=DEFAULT_CPF_FILE):
    ticker_inputs, currency, cpf_member, cpf_fx_rate, etf_holdings = gather_starting_data(
        input_func, print_func, holdings_file, cpf_file
    )
    app = build_app(
        ticker_inputs,
        currency,
        cpf_member=cpf_member,
        cpf_fx_rate=cpf_fx_rate,
        cpf_file=cpf_file,
        etf_holdings=etf_holdings,
    )
    app.run(debug=False)
