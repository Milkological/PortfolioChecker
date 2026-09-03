# Portfolio Checker

A tool that takes your current stock/ETF holdings and monthly DCA
(dollar-cost averaging) contributions, pulls real historical growth rates and
dividend data from Yahoo Finance, and projects your portfolio's value
forward — broken down by how much came from your own contributions, dividend
income, and market growth. It ships two ways to view the projection:

- **`main.py`** — a command-line tool that produces a static chart plus a
  detailed year-by-year CSV per ticker (and one for your total portfolio).
- **`dashboard.py`** — an interactive browser dashboard with sliders for
  years, DCA, growth rate, and dividends per ticker, so you can adjust
  assumptions and compare scenarios live.

## Requirements

- Python 3.11+ (developed and tested on 3.14)
- The included virtual environment: `portfolio_venv`

## Setup

Install dependencies into the venv (only needed once, or after
`requirements.txt` changes):

```powershell
& "portfolio_venv\Scripts\pip.exe" install -r requirements.txt
```

## Running it

Both scripts ask the same starting questions — holdings, base currency,
projection horizon, and per-ticker market data lookup — then diverge in what
they produce. You can type holdings in interactively, or pass a CSV file as
an argument to either script to skip that step (see
[From a CSV file](#from-a-csv-file) below).

### Static chart + CSV export (`main.py`)

```powershell
& "portfolio_venv\Scripts\python.exe" main.py
```

(or activate the venv first with `portfolio_venv\Scripts\Activate.ps1` and
just run `python main.py`)

You'll be prompted interactively:

1. **Holdings** — enter each as `TICKER,SHARES` (Yahoo Finance format, e.g.
   `AAPL,10` or `D05.SI,50` for international exchanges), followed by the
   monthly DCA amount for that ticker. Press Enter on a blank line when done.
2. **Base currency** — what currency totals should be shown in (e.g. `USD`,
   `SGD`). Your DCA amounts are understood to be in this currency. If a
   ticker trades in a different currency, its price and dividends are
   converted automatically using a live exchange rate.
3. **Projection horizon** — how many years to project forward (default: 10).
4. **Price history lookback window** — `3y`, `5y` (default), or `10y`. This
   controls how much trailing price history each ticker's CAGR is computed
   over. Useful to compare: a rate that's similar across all three windows
   is more trustworthy than one that swings wildly, which usually means the
   default window happened to catch a short-term rally or crash rather than
   a sustained trend.
5. **Market data lookup** — for each ticker, the tool fetches its CAGR and
   dividend history from Yahoo Finance over that window. If a ticker can't
   be found or has too little price history to trust, you'll be asked to
   retry the ticker, drop it from the portfolio, or manually enter an
   assumed growth rate and price yourself (entered directly in your base
   currency). If the fetched growth rate comes back unusually high (above
   20%/year), you'll see a note flagging it as possibly a short-term rally
   rather than sustainable long-term growth — worth a second look, or try a
   different lookback window to sanity-check it.
6. A chart window opens showing a stacked breakdown of your **total
   portfolio** value (contributed money, dividend income, and market growth),
   plus one smaller panel per ticker showing the same breakdown for just that
   holding.
7. A `logs/` folder is written next to the script, containing one CSV per
   ticker (`logs/AAPL.csv`, etc.) plus `logs/TOTAL.csv` for the combined
   portfolio — each with a row per year: `contributed_total`,
   `dividend_income`, `growth_gain`, and `total_value`.

### Interactive dashboard (`dashboard.py`)

```powershell
& "portfolio_venv\Scripts\python.exe" dashboard.py
```

Same holdings/currency/market-data prompts as `main.py`, but instead of
writing a static chart, it starts a local web server and prints a URL (e.g.
`http://127.0.0.1:8050/`) — open that in your browser. You'll see:

- Sliders/inputs for **projection years**, and per-ticker **initial shares**,
  **monthly DCA**, **annual growth rate**, and **monthly dividend per
  share** — all seeded from the real values fetched from Yahoo Finance, but
  freely adjustable so you can test "what if" scenarios.
- A **Total Portfolio / per-ticker** selector to switch which breakdown the
  chart shows.
- The chart updates live as you move any control — no need to re-run the
  script.

Leave the terminal running while you use the dashboard; closing it (or
Ctrl+C) stops the local server.

### From a CSV file

Instead of typing holdings in one at a time, pass a CSV file as an argument
to either script:

```powershell
& "portfolio_venv\Scripts\python.exe" main.py holdings.csv
& "portfolio_venv\Scripts\python.exe" dashboard.py holdings.csv
```

The file needs a header row and one holding per line:

```csv
ticker,shares,monthly_dca,currency
AAPL,10,100,USD
KO,5,20,USD
D05.SI,50,0,SGD
```

- `ticker` — Yahoo Finance format (e.g. `AAPL`, or `D05.SI` for international
  exchanges)
- `shares` — number of shares you currently own (can be `0` if you're only
  planning to DCA into a ticker you don't own yet)
- `monthly_dca` — monthly dollar-cost-average amount for that ticker (`0` if
  none)
- `currency` — *optional*. The ticker's native trading currency (e.g. `USD`,
  `SGD`, `JPY`, `CNY`, `MYR`). If omitted, the tool auto-detects it from
  Yahoo Finance. Setting it explicitly skips that lookup and is useful if you
  want to be certain, or auto-detection is ever wrong.

Column headers are case-insensitive and extra whitespace is trimmed, so
`Ticker`, `TICKER`, or ` ticker ` all work. See `holdings_example.csv` in this
repo for a working example. When a file is provided, the base currency and
projection horizon are still asked interactively as normal — only the
holdings themselves are loaded from the file.

### Mixing currencies

You can freely mix tickers from different exchanges/currencies in one
portfolio (e.g. US stocks in USD alongside Singapore stocks in SGD). Pick
one base currency when prompted (or via the CSV `currency` column plus the
interactive base-currency prompt), and every ticker's price and dividends
are converted to it using a live FX rate before being combined — so the
total and the chart are always in one consistent currency.

Note: the growth rate for each ticker is calculated in its own native
currency (that's how the stock actually grows) and only the resulting dollar
amounts are converted — exchange-rate movement itself isn't projected
forward, since forecasting FX rates is a separate problem outside this
tool's scope.

## Running the tests

```powershell
& "portfolio_venv\Scripts\python.exe" -m pytest -v
```

All tests run offline — no network calls are made. `yfinance` is isolated
behind `portfolio_checker/market_data.py` and swapped out for fake data in
tests.

## Project structure

```
main.py                        # entry point: static chart + CSV export
dashboard.py                    # entry point: interactive web dashboard
holdings_example.csv           # sample holdings file
portfolio_checker/
  finance_math.py               # CAGR + rate conversion math
  simulation.py                 # month-by-month DCA/growth/dividend simulation
  contributions.py              # "amount contributed" line calculation
  yearly_summary.py             # turns monthly simulation output into yearly rows
  report_builder.py             # non-interactive version of the simulation pipeline, used by the dashboard
  market_data.py                # yfinance data fetching, isolated for testing
  cli_parsing.py                # input parsing/validation, incl. holdings CSV rows
  cli.py                        # interactive prompts, wires everything together for main.py
  dashboard_app.py              # Dash app: layout, sliders, live-update callback
  graph.py                      # chart data prep + matplotlib plotting (main.py)
  plotly_view.py                # chart data prep as a Plotly figure (dashboard.py)
  csv_export.py                 # writes yearly summary rows to CSV
tests/                          # pytest suite, one file per module above
```

## Notes and assumptions

- Growth rate is computed as CAGR (compound annual growth rate) over your
  chosen lookback window (3y/5y/10y, default 5y) — or however much history
  is actually available for younger tickers, down to a minimum of ~6 months.
  Note that CAGR only looks at the start and end price, so it can't tell the
  difference between steady long-term compounding and years of flat/dead
  money followed by one sharp recent rally — both can produce the same
  headline number. A fetched rate above 20%/year triggers a warning for
  exactly this reason; comparing the rate across different lookback windows
  is a good way to sanity-check whether it reflects a real trend.
- Dividend yield is based on the trailing 12 months of payouts, averaged
  evenly per month rather than modeling actual (usually quarterly) payment
  dates.
- Manually-entered growth rates (used as a fallback when Yahoo Finance data
  isn't available) don't include dividend data.
- Currency conversion uses a live, current FX rate — it does not model how
  exchange rates might drift over the projection horizon.
- Dividends are assumed **not reinvested** — they're tracked as income and
  count toward your total portfolio value, but sit as cash rather than
  buying more shares. There's no way to know a ticker's real-world DRIP
  status from Yahoo Finance data alone, so this is the deliberately
  conservative default in both `main.py` and `dashboard.py`.
