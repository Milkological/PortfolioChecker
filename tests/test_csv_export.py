import csv

from portfolio_checker.csv_export import write_yearly_summary_csv


def test_write_yearly_summary_csv_writes_rows(tmp_path):
    rows = [
        {"year": 0, "contributed_total": 1000.0, "dividend_income": 0.0, "growth_gain": 0.0, "total_value": 1000.0},
        {"year": 1, "contributed_total": 1600.0, "dividend_income": 20.0, "growth_gain": 80.0, "total_value": 1700.0},
    ]
    output_path = tmp_path / "AAPL.csv"

    write_yearly_summary_csv(rows, output_path)

    with open(output_path, newline="") as f:
        written_rows = list(csv.DictReader(f))

    assert written_rows == [
        {"year": "0", "contributed_total": "1000.0", "dividend_income": "0.0", "growth_gain": "0.0", "total_value": "1000.0"},
        {"year": "1", "contributed_total": "1600.0", "dividend_income": "20.0", "growth_gain": "80.0", "total_value": "1700.0"},
    ]
