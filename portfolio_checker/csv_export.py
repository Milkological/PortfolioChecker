import csv


def write_yearly_summary_csv(rows, path):
    fieldnames = ["year", "contributed_total", "dividend_income", "growth_gain", "total_value"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
