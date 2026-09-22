"""Reading and writing cpf.csv, kept separate so cpf.py stays free of I/O."""

import csv
import os

from portfolio_checker.cli_parsing import CPF_CSV_COLUMNS, parse_cpf_csv_row
from portfolio_checker.cpf import CpfMember

DEFAULT_CPF_FILE = "cpf.csv"


def load_cpf_from_csv(path=DEFAULT_CPF_FILE):
    """Load a member from cpf.csv, or None when there is nothing to load.

    Returning None rather than raising keeps CPF entirely opt-in — the
    dashboard works exactly as before for anyone without the file.
    """
    if not path or not os.path.exists(path):
        return None

    with open(path, newline="") as f:
        rows = [row for row in csv.DictReader(f) if any((value or "").strip() for value in row.values())]

    if not rows:
        return None

    return CpfMember(**parse_cpf_csv_row(rows[0]))


def write_cpf_csv(member: CpfMember, path=DEFAULT_CPF_FILE):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CPF_CSV_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "age": member.age,
                "monthly_salary": member.monthly_salary,
                "annual_bonus_months": member.annual_bonus_months,
                "bonus_month": member.bonus_month,
                "oa_balance": member.oa_balance,
                "sa_balance": member.sa_balance,
                "ma_balance": member.ma_balance,
                "salary_growth_percent": member.salary_growth_rate * 100,
            }
        )
