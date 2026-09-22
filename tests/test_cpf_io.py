import pytest

from portfolio_checker.cli_parsing import parse_cpf_csv_row
from portfolio_checker.cpf import CpfMember
from portfolio_checker.cpf_io import load_cpf_from_csv, write_cpf_csv


def test_parse_cpf_csv_row_reads_all_fields():
    parsed = parse_cpf_csv_row(
        {
            "age": "32",
            "monthly_salary": "7000",
            "annual_bonus_months": "2",
            "bonus_month": "12",
            "oa_balance": "45000",
            "sa_balance": "30000",
            "ma_balance": "25000",
            "salary_growth_percent": "3",
        }
    )

    assert parsed["age"] == 32.0
    assert parsed["monthly_salary"] == 7000.0
    assert parsed["salary_growth_rate"] == 0.03


def test_parse_cpf_csv_row_defaults_optional_fields():
    parsed = parse_cpf_csv_row({"age": "30", "monthly_salary": "5000"})

    assert parsed["oa_balance"] == 0.0
    assert parsed["annual_bonus_months"] == 0.0
    assert parsed["bonus_month"] == 12
    assert parsed["salary_growth_rate"] == 0.0


def test_parse_cpf_csv_row_requires_age():
    with pytest.raises(ValueError, match="age"):
        parse_cpf_csv_row({"age": "", "monthly_salary": "5000"})


def test_parse_cpf_csv_row_rejects_members_at_or_above_55():
    with pytest.raises(ValueError, match="below 55"):
        parse_cpf_csv_row({"age": "57", "monthly_salary": "5000"})


def test_parse_cpf_csv_row_rejects_invalid_bonus_month():
    with pytest.raises(ValueError, match="bonus_month"):
        parse_cpf_csv_row({"age": "30", "monthly_salary": "5000", "bonus_month": "13"})


def test_load_returns_none_when_file_missing(tmp_path):
    assert load_cpf_from_csv(str(tmp_path / "nope.csv")) is None


def test_load_returns_none_when_path_is_empty():
    assert load_cpf_from_csv(None) is None


def test_load_returns_none_for_a_header_only_file(tmp_path):
    path = tmp_path / "cpf.csv"
    path.write_text("age,monthly_salary\n")

    assert load_cpf_from_csv(str(path)) is None


def test_write_then_load_round_trips(tmp_path):
    path = str(tmp_path / "cpf.csv")
    member = CpfMember(
        age=32.0,
        monthly_salary=7000.0,
        annual_bonus_months=2.0,
        oa_balance=45000.0,
        sa_balance=30000.0,
        ma_balance=25000.0,
        salary_growth_rate=0.03,
        bonus_month=6,
    )

    write_cpf_csv(member, path)

    assert load_cpf_from_csv(path) == member
