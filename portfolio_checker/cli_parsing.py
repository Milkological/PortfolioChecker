def parse_holding_line(line: str):
    if "," not in line:
        raise ValueError(f"Expected 'TICKER,SHARES', got {line!r}")

    ticker_part, shares_part = line.split(",", 1)
    ticker = ticker_part.strip().upper()
    if not ticker:
        raise ValueError("Ticker cannot be empty")

    try:
        shares = float(shares_part.strip())
    except ValueError:
        raise ValueError(f"Shares must be a number, got {shares_part!r}")

    if shares < 0:
        raise ValueError(f"Shares cannot be negative, got {shares}")

    return ticker, shares


def parse_nonnegative_float(text: str, field_name: str) -> float:
    try:
        value = float(text.strip())
    except ValueError:
        raise ValueError(f"{field_name} must be a number, got {text!r}")
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative, got {value}")
    return value


def parse_positive_float(text: str, field_name: str) -> float:
    value = parse_nonnegative_float(text, field_name)
    if value == 0:
        raise ValueError(f"{field_name} must be positive, got {value}")
    return value


def parse_positive_int(text: str, field_name: str) -> int:
    stripped = text.strip()
    try:
        value = int(stripped)
    except ValueError:
        raise ValueError(f"{field_name} must be a whole number, got {text!r}")
    if value <= 0:
        raise ValueError(f"{field_name} must be positive, got {value}")
    return value


def parse_projection_years(text: str, default: int = 10) -> int:
    if not text.strip():
        return default
    return parse_positive_int(text, "Projection years")


def parse_yes_no(text: str) -> bool:
    normalized = text.strip().lower()
    if normalized in ("y", "yes"):
        return True
    if normalized in ("n", "no"):
        return False
    raise ValueError(f"Expected yes/no, got {text!r}")


def parse_growth_rate_percent(text: str) -> float:
    stripped = text.strip().rstrip("%")
    try:
        percent = float(stripped)
    except ValueError:
        raise ValueError(f"Growth rate must be a number, got {text!r}")
    return percent / 100


REQUIRED_HOLDINGS_CSV_COLUMNS = ("ticker", "shares", "monthly_dca")


def parse_holdings_csv_rows(rows):
    holdings = []
    for row in rows:
        normalized = {
            (key.strip().lower() if key is not None else key): value for key, value in row.items()
        }

        for column in REQUIRED_HOLDINGS_CSV_COLUMNS:
            if not normalized.get(column, "").strip():
                raise ValueError(f"Missing required column {column!r} in holdings CSV row: {row}")

        ticker = normalized["ticker"].strip().upper()
        if not ticker:
            raise ValueError(f"Ticker cannot be empty in row: {row}")

        shares = parse_nonnegative_float(normalized["shares"], "shares")
        dca = parse_nonnegative_float(normalized["monthly_dca"], "monthly_dca")

        currency_text = normalized.get("currency", "").strip()
        currency = parse_currency_code(currency_text) if currency_text else None

        holdings.append({"ticker": ticker, "shares": shares, "dca": dca, "currency": currency})

    return holdings


REQUIRED_CPF_CSV_COLUMNS = ("age", "monthly_salary")

CPF_CSV_COLUMNS = (
    "age",
    "monthly_salary",
    "annual_bonus_months",
    "bonus_month",
    "oa_balance",
    "sa_balance",
    "ma_balance",
    "salary_growth_percent",
)


def parse_cpf_csv_row(row):
    """Parse the single row of a cpf.csv into plain values.

    Only age and monthly_salary are required; everything else defaults to zero
    so a member can start with just the basics filled in.
    """
    normalized = {
        (key.strip().lower() if key is not None else key): (value or "") for key, value in row.items()
    }

    for column in REQUIRED_CPF_CSV_COLUMNS:
        if not normalized.get(column, "").strip():
            raise ValueError(f"Missing required column {column!r} in CPF CSV row: {row}")

    age = parse_positive_float(normalized["age"], "age")
    if age >= 55:
        raise ValueError(f"CPF projection only models members below 55, got age {age}")

    def optional(column, field_name, default=0.0):
        text = normalized.get(column, "").strip()
        return parse_nonnegative_float(text, field_name) if text else default

    bonus_month_text = normalized.get("bonus_month", "").strip()
    bonus_month = parse_positive_int(bonus_month_text, "bonus_month") if bonus_month_text else 12
    if bonus_month > 12:
        raise ValueError(f"bonus_month must be between 1 and 12, got {bonus_month}")

    growth_text = normalized.get("salary_growth_percent", "").strip()
    salary_growth_rate = parse_growth_rate_percent(growth_text) if growth_text else 0.0

    return {
        "age": age,
        "monthly_salary": optional("monthly_salary", "monthly_salary"),
        "annual_bonus_months": optional("annual_bonus_months", "annual_bonus_months"),
        "bonus_month": bonus_month,
        "oa_balance": optional("oa_balance", "oa_balance"),
        "sa_balance": optional("sa_balance", "sa_balance"),
        "ma_balance": optional("ma_balance", "ma_balance"),
        "salary_growth_rate": salary_growth_rate,
    }


VALID_LOOKBACK_PERIODS = ("3y", "5y", "10y", "max")


def parse_lookback_period(text: str, default: str = "5y") -> str:
    normalized = text.strip().lower()
    if not normalized:
        return default
    if normalized not in VALID_LOOKBACK_PERIODS:
        raise ValueError(f"Lookback period must be one of {VALID_LOOKBACK_PERIODS}, got {text!r}")
    return normalized


def parse_currency_code(text: str) -> str:
    code = text.strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise ValueError(f"Currency code must be a 3-letter code, got {text!r}")
    return code
