# PortfolioChecker

Pulls live price, growth (CAGR), and dividend data from Yahoo Finance for your holdings, then projects how your portfolio could grow over time (contributions + market growth + reinvested/cash dividends).

There are two ways to run it: an interactive **CLI** (prints a chart + CSV logs) or a browser-based **Dashboard** (live, editable projections).

## Setup

```
pip install -r requirements.txt
```

## Holdings file

Create a `holdings.csv` (see `holdings_example.csv`) with these columns:

```
ticker,shares,monthly_dca,currency
AAPL,10,100,USD
D05.SI,50,0,SGD
```

- `ticker` — Yahoo Finance symbol (append the exchange suffix for non-US listings, e.g. `.SI` for SGX, `.L` for LSE).
- `shares` — shares currently held.
- `monthly_dca` — amount you plan to invest monthly into that ticker going forward (0 if none).
- `currency` — the ticker's native trading currency. Optional; if left blank it's auto-detected.

`holdings.csv` is gitignored since it's personal financial data — don't commit your real one.

## Running the CLI

```
python main.py [holdings.csv]
```

If no file is given, it prompts you to enter holdings one at a time instead. It then asks for:
- the currency to display totals in,
- the projection horizon in years (default 10),
- the price-history lookback window used for the growth-rate calculation (`3y`/`5y`/`10y`/`max`, default `5y`).

For each ticker it fetches price, growth rate, and dividend data live from Yahoo Finance. If a fetch fails (bad ticker, no data, etc.) you'll be prompted to `retry` the symbol, `drop` the holding, or `manual` (type in your own assumed growth rate and current price — dividends aren't available for manually-entered holdings). If a ticker's fetched growth rate looks unusually high (>20%), you'll see a warning that it may reflect a short-term rally rather than a sustainable trend.

Output:
- a stacked-area chart (Total Portfolio + one panel per ticker) showing contributed capital, dividends, and market growth over time,
- a `logs/` folder with one CSV per ticker plus `TOTAL.csv`, each with yearly `contributed_total`, `dividend_income`, `growth_gain`, and `total_value` columns.

`logs/` is also gitignored — it's regenerated every run.

## Running the Dashboard

```
python dashboard.py [holdings.csv]
```

This starts a local Dash server and prompts for the same currency/lookback questions as the CLI, then opens an interactive web page (check your terminal for the local URL, typically `http://127.0.0.1:8050`).

Each holding is shown as a row with four parts:
- **checkbox** — "Show in chart." Check one or more tickers to combine just those into the chart below; with nothing checked, the chart shows your Total Portfolio. Checked rows are highlighted.
- **variables** — live-editable inputs: initial shares, monthly DCA, annual growth rate (%, pre-filled from the fetched CAGR), a CAGR lookback-period dropdown (3y/5y/10y/max — changing it re-fetches the growth rate for that window), and annual dividend per share. A warning badge appears next to the growth rate if it's unusually high (>20%).
- **details** — read-only, auto-updating: current price, position value and % of portfolio, actual dividends paid this calendar year, the estimated next payment date, and the last few real payment dates/amounts.
- **company summary** — a short business description pulled from Yahoo Finance.

There's also a **Total Portfolio** card (with its own expandable Details) showing total portfolio value, the value-weighted average annual growth rate, total annual dividend income, and a breakdown table across all holdings.

All chart and detail figures update live as you edit the inputs above — nothing needs to be re-fetched except when you change a lookback-period dropdown.

Below the main chart there's a **CPF** card for Singapore users — see [CPF (Singapore)](#cpf-singapore).

## CPF (Singapore)

The dashboard can project your CPF alongside your market portfolio. Fill in the **CPF** card at the bottom of the page — age, monthly salary, bonus, and your current OA/SA/MA balances — and the projection updates live, the same way the ticker rows do. Your entries are saved to `cpf.csv` (gitignored, see `cpf_example.csv` for the shape) so you don't have to retype them next run.

The card shows your projected balances split by account, total contributions, and total interest earned. Tick **Include CPF in Total Portfolio** to fold the CPF balance into the Total Portfolio figure and chart. CPF is held in SGD; if you're displaying totals in another currency it's converted at the live rate, fetched once at startup.

**What's modelled:**
- employer and employee contribution rates by age band and wage band,
- the Ordinary Wage ceiling ($8,000/month from 1 Jan 2026) and the $102,000 Annual Total Wage ceiling on bonuses,
- age-banded allocation across OA / SA / MediSave, computed in CPF's documented order (MediSave first, then SA, with OA taking the remainder),
- base interest (2.5% OA, 4% SA/MA) plus the extra 1% on the first $60,000 of combined balances, capped at $20,000 from OA, with OA's extra interest paid into SA,
- MediSave overflow above the Basic Healthcare Sum spilling into SA,
- interest accrued monthly and credited each December, as CPF actually does it.

**What isn't:** the projection **stops at age 55**. Retirement Account creation, Special Account closure, Full Retirement Sum top-ups and CPF LIFE payouts are out of scope. Only Singapore Citizen / 3rd-year-onwards PR rates are modelled, not the graduated 1st- and 2nd-year PR tables.

All statutory figures live in `portfolio_checker/cpf_rates.py`, each with a link to the CPF Board page it came from. CPF revises most of them annually — when new tables are published, update that one file and bump `RATES_EFFECTIVE_YEAR`.

> These projections assume today's rates hold for the whole period. They won't — rates, ceilings and the BHS all change. Treat the output as a planning estimate, not a statement of your future balance.

## Portfolio Review

The **Portfolio Review** card at the bottom of the dashboard gives a blunt structural assessment of what you hold. Press **Run review** — it uses whatever values are currently in the inputs, so you can change a growth rate and re-run to see the verdict change.

It checks:
- **concentration** — largest position, top-3 share, and how many equally-sized holdings your portfolio actually behaves like,
- **fund/holding overlap** — whether you own an ETF *and* the things inside it, which hides your true exposure,
- **correlation** — pairs whose monthly returns move together, using the price history already fetched for the growth rates,
- **sector, country and currency concentration**,
- **speculative positions** — no dividend plus an extrapolated growth rate nothing sustains,
- **the growth assumptions the whole projection rests on**,
- **where new monthly money is going**, and whether it increases concentration,
- **dividend income concentration** and **historical drawdowns**.

Findings are ranked worst-first. Checks that would otherwise produce one card per pair or per ticker (correlation, drawdowns) are capped and rolled up, so the review stays readable rather than burying the important findings under dozens of near-identical ones.

**Optional LLM narrative.** If an API key is available, the computed findings are sent to a model which writes them up as prose above the finding cards. Two providers are supported:

| Section | Environment variable | Package | Default model |
|---|---|---|---|
| `[claude]` | `ANTHROPIC_API_KEY` | `anthropic` | `claude-opus-5` |
| `[gemini]` | `GEMINI_API_KEY` or `GOOGLE_API_KEY` | `google-genai` | `gemini-3.8-flash` |

Configure either, both, or neither. Copy `config_example.ini` to `config.ini` (gitignored) and fill in the sections you want, or set the environment variables — those take precedence over the file. A section left with the example's `...` placeholder counts as not configured.

**Every configured provider runs and produces its own narrative**, stacked and labelled, so you can compare how each reads the same findings. That means one API call per provider per review. Delete or leave unconfigured whichever you don't want.

Without any key — or if a key is wrong, the network is down, or the package isn't installed — the review runs anyway and shows the rule-based findings, with a one-line note per provider saying why its narrative is missing. A provider failing doesn't stop the others.

The rules are the source of truth; the model only rephrases what they found, and is explicitly instructed not to introduce numbers of its own. The prompt lives in `SYSTEM_PROMPT` in [review_narrative.py](portfolio_checker/review_narrative.py) and is shared by both providers.

> This is a mechanical review of structure — concentration, overlap and correlation. It is not financial advice, it knows nothing about your goals, tax position or time horizon, and it cannot tell you what to buy or sell.

## Notes

- Dividend figures throughout are **annual**, not monthly (e.g. "Annual dividend per share") — this matches how dividends are actually paid (often quarterly or semi-annually) instead of smoothing them into a misleading per-month number.
- Growth rates are historical CAGR (compound annual growth rate) computed from price history, not a guarantee of future performance — treat them as a starting assumption you can freely edit.
