import dash
from dash import ALL, MATCH, Input, Output, State, dcc, html

from portfolio_checker.cli import collect_holdings, fetch_market_data_for_ticker, load_holdings_from_csv
from portfolio_checker.cli_parsing import VALID_LOOKBACK_PERIODS, parse_currency_code, parse_lookback_period
from portfolio_checker.dividend_history import (
    dividends_paid_this_calendar_year,
    estimate_next_dividend_date,
    recent_dividend_payments,
)
from portfolio_checker.plotly_view import build_stacked_figure
from portfolio_checker.market_data import describe_high_growth_warning, fetch_growth_rate_for_period
from portfolio_checker.report_builder import (
    TickerInput,
    build_report_data,
    portfolio_share_percentage,
    total_annual_dividend_income,
    total_portfolio_value,
    weighted_average_growth_rate,
)


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


def build_chart_for_selection(ticker_inputs, years, currency, title):
    total_rows, _ = build_report_data(ticker_inputs, years)
    return build_stacked_figure(total_rows, currency=currency, title=title)


def gather_starting_data(input_func=input, print_func=print, holdings_file=None):
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
            )
        )

    if not ticker_inputs:
        raise SystemExit("No holdings left after data lookup — nothing to project.")

    return ticker_inputs, base_currency


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


def _holding_breakdown_table(current_inputs, total_value, currency):
    header = html.Tr(
        [
            html.Th("Holding"),
            html.Th("Shares"),
            html.Th("Annual Growth Rate"),
            html.Th("Annual Dividend Income"),
            html.Th("% of Portfolio"),
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
                    html.Td(t.ticker),
                    html.Td(f"{t.initial_shares:,.3f}"),
                    html.Td(f"{t.annual_growth_rate * 100:.2f}%"),
                    html.Td(f"{dividend_income:,.2f} {currency}"),
                    html.Td(f"{percent:.1f}%"),
                ]
            )
        )
    return html.Table([html.Thead(header), html.Tbody(rows)])


def _total_portfolio_detail_content(current_inputs, currency):
    total_value = total_portfolio_value(current_inputs)
    total_dividend = total_annual_dividend_income(current_inputs)
    average_growth = weighted_average_growth_rate(current_inputs)

    return [
        html.P(f"Total portfolio value: {total_value:,.2f} {currency}"),
        html.P(f"Average annual growth rate (value-weighted): {average_growth * 100:.2f}%"),
        html.P(f"Total annual dividend income: {total_dividend:,.2f} {currency}"),
        html.P("Breakdown by holding:"),
        _holding_breakdown_table(current_inputs, total_value, currency),
    ]


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


def build_app(ticker_inputs, currency, default_years=10):
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
        ]
    )

    @app.callback(
        Output("chart", "figure"),
        Output("total-detail-content", "children"),
        Output({"type": "growth-warning", "ticker": ALL}, "children"),
        Output({"type": "detail-content", "ticker": ALL}, "children"),
        Input("years", "value"),
        Input({"type": "chart-select", "ticker": ALL}, "value"),
        Input({"type": "shares", "ticker": ALL}, "value"),
        Input({"type": "dca", "ticker": ALL}, "value"),
        Input({"type": "growth", "ticker": ALL}, "value"),
        Input({"type": "dividend", "ticker": ALL}, "value"),
    )
    def update_chart(years, chart_selected, shares_values, dca_values, growth_values, dividend_values):
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
            )
            for i, t in enumerate(ticker_inputs)
        ]
        total_detail_content = _total_portfolio_detail_content(current_inputs, currency)
        growth_warnings = [_growth_warning_text(rate / 100) for rate in growth_values]
        portfolio_value = total_portfolio_value(current_inputs)
        detail_contents = [
            _ticker_detail_content(t, shares_values[i], t.current_price, portfolio_value)
            for i, t in enumerate(ticker_inputs)
        ]

        checked_tickers = {t.ticker for t, checked in zip(ticker_inputs, chart_selected) if "selected" in checked}
        selected_tickers = select_chart_tickers(tickers, checked_tickers)
        title = chart_title_for_tickers(selected_tickers, tickers)
        selected_inputs = [t for t in current_inputs if t.ticker in set(selected_tickers)]
        chart = build_chart_for_selection(selected_inputs, years, currency, title)

        return chart, total_detail_content, growth_warnings, detail_contents

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


def run(input_func=input, print_func=print, holdings_file=None):
    ticker_inputs, currency = gather_starting_data(input_func, print_func, holdings_file)
    app = build_app(ticker_inputs, currency)
    app.run(debug=False)
