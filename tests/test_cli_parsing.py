import pytest

from portfolio_checker.cli_parsing import (
    parse_currency_code,
    parse_growth_rate_percent,
    parse_holding_line,
    parse_holdings_csv_rows,
    parse_lookback_period,
    parse_nonnegative_float,
    parse_positive_float,
    parse_positive_int,
    parse_projection_years,
    parse_yes_no,
)


def test_parse_holding_line_basic():
    ticker, shares = parse_holding_line("AAPL,10")
    assert ticker == "AAPL"
    assert shares == pytest.approx(10.0)


def test_parse_holding_line_lowercase_and_whitespace():
    ticker, shares = parse_holding_line(" aapl , 10.5 ")
    assert ticker == "AAPL"
    assert shares == pytest.approx(10.5)


def test_parse_holding_line_missing_comma_raises():
    with pytest.raises(ValueError):
        parse_holding_line("AAPL 10")


def test_parse_holding_line_empty_ticker_raises():
    with pytest.raises(ValueError):
        parse_holding_line(",10")


def test_parse_holding_line_non_numeric_shares_raises():
    with pytest.raises(ValueError):
        parse_holding_line("AAPL,abc")


def test_parse_holding_line_negative_shares_raises():
    with pytest.raises(ValueError):
        parse_holding_line("AAPL,-5")


def test_parse_holding_line_zero_shares_allowed():
    ticker, shares = parse_holding_line("AAPL,0")
    assert ticker == "AAPL"
    assert shares == pytest.approx(0.0)


def test_parse_nonnegative_float_accepts_zero():
    assert parse_nonnegative_float("0", "DCA") == pytest.approx(0.0)


def test_parse_nonnegative_float_accepts_positive():
    assert parse_nonnegative_float("100.5", "DCA") == pytest.approx(100.5)


def test_parse_nonnegative_float_rejects_negative():
    with pytest.raises(ValueError):
        parse_nonnegative_float("-1", "DCA")


def test_parse_nonnegative_float_rejects_non_numeric():
    with pytest.raises(ValueError):
        parse_nonnegative_float("abc", "DCA")


def test_parse_positive_float_rejects_zero():
    with pytest.raises(ValueError):
        parse_positive_float("0", "shares")


def test_parse_positive_float_accepts_positive():
    assert parse_positive_float("2.5", "shares") == pytest.approx(2.5)


def test_parse_positive_int_rejects_zero():
    with pytest.raises(ValueError):
        parse_positive_int("0", "years")


def test_parse_positive_int_accepts_positive():
    assert parse_positive_int("10", "years") == 10


def test_parse_positive_int_rejects_non_integer():
    with pytest.raises(ValueError):
        parse_positive_int("10.5", "years")


def test_parse_projection_years_blank_uses_default():
    assert parse_projection_years("", default=10) == 10
    assert parse_projection_years("   ", default=10) == 10


def test_parse_projection_years_explicit_value():
    assert parse_projection_years("20", default=10) == 20


def test_parse_projection_years_rejects_zero():
    with pytest.raises(ValueError):
        parse_projection_years("0", default=10)


def test_parse_yes_no_variants():
    assert parse_yes_no("y") is True
    assert parse_yes_no("Yes") is True
    assert parse_yes_no("n") is False
    assert parse_yes_no("No") is False


def test_parse_yes_no_rejects_garbage():
    with pytest.raises(ValueError):
        parse_yes_no("maybe")


def test_parse_growth_rate_percent_plain_number():
    assert parse_growth_rate_percent("7") == pytest.approx(0.07)


def test_parse_growth_rate_percent_with_percent_sign():
    assert parse_growth_rate_percent("7%") == pytest.approx(0.07)


def test_parse_growth_rate_percent_rejects_non_numeric():
    with pytest.raises(ValueError):
        parse_growth_rate_percent("abc")


def test_parse_holdings_csv_rows_basic():
    rows = [
        {"ticker": "AAPL", "shares": "10", "monthly_dca": "50"},
        {"ticker": "KO", "shares": "5", "monthly_dca": "20"},
    ]
    result = parse_holdings_csv_rows(rows)
    assert result == [
        {"ticker": "AAPL", "shares": 10.0, "dca": 50.0, "currency": None},
        {"ticker": "KO", "shares": 5.0, "dca": 20.0, "currency": None},
    ]


def test_parse_holdings_csv_rows_normalizes_header_case_and_whitespace():
    rows = [{" Ticker ": " aapl ", "SHARES": "10", "Monthly_DCA": "50"}]
    result = parse_holdings_csv_rows(rows)
    assert result == [{"ticker": "AAPL", "shares": 10.0, "dca": 50.0, "currency": None}]


def test_parse_holdings_csv_rows_missing_column_raises():
    rows = [{"ticker": "AAPL", "shares": "10"}]
    with pytest.raises(ValueError):
        parse_holdings_csv_rows(rows)


def test_parse_holdings_csv_rows_empty_ticker_raises():
    rows = [{"ticker": "", "shares": "10", "monthly_dca": "50"}]
    with pytest.raises(ValueError):
        parse_holdings_csv_rows(rows)


def test_parse_holdings_csv_rows_negative_shares_raises():
    rows = [{"ticker": "AAPL", "shares": "-10", "monthly_dca": "50"}]
    with pytest.raises(ValueError):
        parse_holdings_csv_rows(rows)


def test_parse_holdings_csv_rows_empty_list_returns_empty():
    assert parse_holdings_csv_rows([]) == []


def test_parse_holdings_csv_rows_with_currency_column():
    rows = [{"ticker": "D05.SI", "shares": "50", "monthly_dca": "0", "currency": "sgd"}]
    result = parse_holdings_csv_rows(rows)
    assert result == [{"ticker": "D05.SI", "shares": 50.0, "dca": 0.0, "currency": "SGD"}]


def test_parse_holdings_csv_rows_currency_column_optional():
    rows = [{"ticker": "AAPL", "shares": "10", "monthly_dca": "50"}]
    result = parse_holdings_csv_rows(rows)
    assert result == [{"ticker": "AAPL", "shares": 10.0, "dca": 50.0, "currency": None}]


def test_parse_holdings_csv_rows_blank_currency_treated_as_none():
    rows = [{"ticker": "AAPL", "shares": "10", "monthly_dca": "50", "currency": ""}]
    result = parse_holdings_csv_rows(rows)
    assert result == [{"ticker": "AAPL", "shares": 10.0, "dca": 50.0, "currency": None}]


def test_parse_lookback_period_valid_options():
    assert parse_lookback_period("3y") == "3y"
    assert parse_lookback_period("5y") == "5y"
    assert parse_lookback_period("10y") == "10y"
    assert parse_lookback_period("max") == "max"


def test_parse_lookback_period_blank_uses_default():
    assert parse_lookback_period("", default="5y") == "5y"
    assert parse_lookback_period("   ", default="5y") == "5y"


def test_parse_lookback_period_normalizes_case_and_whitespace():
    assert parse_lookback_period(" 3Y ") == "3y"


def test_parse_lookback_period_rejects_invalid():
    with pytest.raises(ValueError):
        parse_lookback_period("7y")


def test_parse_currency_code_normalizes_case_and_whitespace():
    assert parse_currency_code(" usd ") == "USD"


def test_parse_currency_code_rejects_wrong_length():
    with pytest.raises(ValueError):
        parse_currency_code("US")


def test_parse_currency_code_rejects_non_alpha():
    with pytest.raises(ValueError):
        parse_currency_code("US1")
