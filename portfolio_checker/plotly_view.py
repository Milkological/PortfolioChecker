import plotly.graph_objects as go

from portfolio_checker.graph import cumulative_stack_series


def build_stacked_figure(rows, currency=None, title=None) -> go.Figure:
    years = [row["year"] for row in rows]
    contributed, dividend_cum, growth_cum = cumulative_stack_series(rows)
    total = [c + d + g for c, d, g in zip(contributed, dividend_cum, growth_cum)]
    unit = currency if currency else "$"

    # Every trace reports its own value for the hovered year; `hovermode` below
    # gathers them into one box so thin bands stay readable.
    hover_template = f"%{{y:,.0f}} {unit}<extra></extra>"

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=years, y=contributed, name="Contributed", stackgroup="one", mode="lines",
            hovertemplate=hover_template,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=years, y=dividend_cum, name="Dividends Reinvested", stackgroup="one", mode="lines",
            hovertemplate=hover_template,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=years, y=growth_cum, name="Market Growth", stackgroup="one", mode="lines",
            hovertemplate=hover_template,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=years, y=total, name="Total Value", mode="lines+markers",
            line=dict(color="black"), hovertemplate=hover_template,
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Year",
        yaxis_title=f"Value ({currency})" if currency else "Value ($)",
        yaxis_tickformat=",.0f",
        yaxis_ticksuffix=f" {unit}",
        # Show all four values for the hovered year in a single box, rather than
        # only whichever line the cursor happens to be nearest.
        hovermode="x unified",
        xaxis=dict(hoverformat="Year %{x}"),
    )

    return fig
