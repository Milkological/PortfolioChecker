from portfolio_checker.report_builder import combine_summary_rows, scale_summary_rows


def row(year, contributed, dividend, growth, total):
    return {
        "year": year,
        "contributed_total": contributed,
        "dividend_income": dividend,
        "growth_gain": growth,
        "total_value": total,
    }


def test_scale_summary_rows_multiplies_every_money_column():
    scaled = scale_summary_rows([row(1, 100.0, 10.0, 5.0, 115.0)], 2.0)

    assert scaled == [row(1, 200.0, 20.0, 10.0, 230.0)]


def test_scale_summary_rows_leaves_the_year_alone():
    scaled = scale_summary_rows([row(3, 100.0, 0.0, 0.0, 100.0)], 0.75)

    assert scaled[0]["year"] == 3


def test_combine_summary_rows_adds_element_wise():
    primary = [row(0, 100.0, 0.0, 0.0, 100.0), row(1, 200.0, 5.0, 10.0, 215.0)]
    secondary = [row(0, 50.0, 0.0, 0.0, 50.0), row(1, 60.0, 0.0, 4.0, 64.0)]

    combined = combine_summary_rows(primary, secondary)

    assert combined[1] == row(1, 260.0, 5.0, 14.0, 279.0)


def test_combine_summary_rows_holds_a_shorter_series_flat():
    primary = [row(0, 100.0, 0.0, 0.0, 100.0), row(1, 200.0, 0.0, 0.0, 200.0), row(2, 300.0, 0.0, 0.0, 300.0)]
    secondary = [row(0, 50.0, 0.0, 0.0, 50.0), row(1, 60.0, 0.0, 4.0, 64.0)]

    combined = combine_summary_rows(primary, secondary)

    # Year 2 carries the CPF balance forward without adding further growth.
    assert combined[2]["total_value"] == 300.0 + 64.0
    assert combined[2]["contributed_total"] == 300.0 + 60.0
    assert combined[2]["growth_gain"] == 0.0


def test_combine_summary_rows_returns_primary_when_secondary_is_empty():
    primary = [row(0, 100.0, 0.0, 0.0, 100.0)]

    assert combine_summary_rows(primary, []) == primary


def test_combine_summary_rows_does_not_mutate_its_inputs():
    primary = [row(0, 100.0, 0.0, 0.0, 100.0)]
    secondary = [row(0, 50.0, 0.0, 0.0, 50.0)]

    combine_summary_rows(primary, secondary)

    assert primary[0]["total_value"] == 100.0
    assert secondary[0]["total_value"] == 50.0
