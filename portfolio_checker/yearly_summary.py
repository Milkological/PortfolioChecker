def build_yearly_summary(year_labels, contributed_yearly, dividend_income_monthly, total_value_yearly):
    rows = []
    for i, year in enumerate(year_labels):
        contributed_total = contributed_yearly[i]
        total_value = total_value_yearly[i]
        if i == 0:
            dividend_income = 0.0
            growth_gain = 0.0
        else:
            months_this_year = dividend_income_monthly[(i - 1) * 12 + 1 : i * 12 + 1]
            dividend_income = sum(months_this_year)
            contributed_this_year = contributed_total - contributed_yearly[i - 1]
            growth_gain = total_value - total_value_yearly[i - 1] - contributed_this_year - dividend_income

        rows.append(
            {
                "year": year,
                "contributed_total": contributed_total,
                "dividend_income": dividend_income,
                "growth_gain": growth_gain,
                "total_value": total_value,
            }
        )
    return rows
