import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


def extract_yearly_points(monthly_values: list) -> list:
    return monthly_values[::12]


def build_year_labels(num_years: int) -> list:
    return list(range(num_years + 1))


def cumulative_stack_series(rows: list) -> tuple:
    contributed = [row["contributed_total"] for row in rows]
    dividend_cum = []
    growth_cum = []
    dividend_running = 0.0
    growth_running = 0.0
    for row in rows:
        dividend_running += row["dividend_income"]
        growth_running += row["growth_gain"]
        dividend_cum.append(dividend_running)
        growth_cum.append(growth_running)
    return contributed, dividend_cum, growth_cum


def plot_stacked_breakdown(ax, rows, currency=None, title=None) -> None:
    years = [row["year"] for row in rows]
    contributed, dividend_cum, growth_cum = cumulative_stack_series(rows)
    total = [c + d + g for c, d, g in zip(contributed, dividend_cum, growth_cum)]

    ax.stackplot(
        years,
        contributed,
        dividend_cum,
        growth_cum,
        labels=["Contributed", "Dividends Reinvested", "Market Growth"],
        alpha=0.8,
    )
    ax.plot(years, total, color="black", linewidth=1, marker="o", markersize=3, label="Total Value")

    ax.set_xlabel("Year")
    ax.set_ylabel(f"Value ({currency})" if currency else "Value ($)")
    if title:
        ax.set_title(title)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", fontsize="small")

    unit = currency if currency else "$"
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"{x:,.0f} {unit}"))

    ax.annotate(
        f"{total[-1]:,.0f}",
        xy=(years[-1], total[-1]),
        xytext=(6, 0),
        textcoords="offset points",
        va="center",
        fontsize="small",
        fontweight="bold",
    )


def plot_portfolio_report(total_rows, ticker_rows, currency=None, output_path=None):
    tickers = list(ticker_rows.keys())
    cols = min(len(tickers), 3) if tickers else 1
    ticker_grid_rows = -(-len(tickers) // cols) if tickers else 0  # ceil division

    fig = plt.figure(figsize=(6 * cols, 4 * (1 + ticker_grid_rows)))
    gs = fig.add_gridspec(1 + ticker_grid_rows, cols)

    ax_total = fig.add_subplot(gs[0, :])
    plot_stacked_breakdown(ax_total, total_rows, currency=currency, title="Total Portfolio")

    for i, ticker in enumerate(tickers):
        r, c = divmod(i, cols)
        ax = fig.add_subplot(gs[1 + r, c])
        plot_stacked_breakdown(ax, ticker_rows[ticker], currency=currency, title=ticker)

    fig.tight_layout()

    if output_path:
        fig.savefig(output_path)
        plt.close(fig)
    else:
        plt.show()

    return fig
