from portfolio_checker.cpf import (
    AccountBalances,
    CpfMember,
    apply_medisave_overflow,
    build_cpf_yearly_summary,
    contribution_for_month,
    cumulative_contributions,
    monthly_interest,
    months_until_55,
    round_down_to_dollar,
    round_to_nearest_dollar,
    simulate_cpf,
    split_contribution,
)


def test_round_to_nearest_dollar_rounds_half_up():
    assert round_to_nearest_dollar(0.5) == 1.0
    assert round_to_nearest_dollar(0.49) == 0.0
    assert round_to_nearest_dollar(1849.5) == 1850.0


def test_round_down_to_dollar_truncates():
    assert round_down_to_dollar(59.99) == 59.0


def test_split_contribution_matches_cpf_worked_example():
    # CPF's published Example 1: a 30-year-old with a $100 contribution gets
    # $62.17 / $16.21 / $21.62 across OA / SA / MA.
    allocated = split_contribution(100.0, age=30)

    assert allocated.ma == 21.62
    assert allocated.sa == 16.21
    assert allocated.oa == 62.17


def test_split_contribution_assigns_ordinary_account_the_remainder():
    allocated = split_contribution(2220.0, age=30)

    assert allocated.ma == 479.96
    assert allocated.sa == 359.86
    # The residual, not 2220 * 0.6217 — this is CPF's documented order.
    assert allocated.oa == 1380.18
    assert round(allocated.total, 2) == 2220.0


def test_split_contribution_uses_older_age_band():
    allocated = split_contribution(1000.0, age=48)

    assert allocated.ma == 270.20
    assert allocated.sa == 216.20


def test_contribution_below_fifty_dollars_is_nil():
    contribution = contribution_for_month(50.0, 0.0, age=30, year=2026)

    assert contribution.total == 0.0
    assert contribution.employee == 0.0


def test_contribution_in_low_wage_band_has_no_employee_share():
    contribution = contribution_for_month(400.0, 0.0, age=30, year=2026)

    assert contribution.total == 68.0  # 17% of $400
    assert contribution.employee == 0.0
    assert contribution.employer == 68.0


def test_contribution_in_graduated_band_phases_in_employee_share():
    contribution = contribution_for_month(600.0, 0.0, age=30, year=2026)

    # 17%(600) + 0.6(600 - 500) = 102 + 60
    assert contribution.total == 162.0
    assert contribution.employee == 60.0


def test_contribution_at_full_rates():
    contribution = contribution_for_month(6000.0, 0.0, age=30, year=2026)

    assert contribution.total == 2220.0  # 37%
    assert contribution.employee == 1200.0  # 20%
    assert contribution.employer == 1020.0


def test_ordinary_wage_ceiling_caps_contribution_at_published_maximum():
    contribution = contribution_for_month(10000.0, 0.0, age=30, year=2026)

    # CPF publishes these as the maximum contribution on Ordinary Wages.
    assert contribution.total == 2960.0
    assert contribution.employee == 1600.0


def test_ordinary_wage_ceiling_is_lower_in_earlier_years():
    contribution = contribution_for_month(10000.0, 0.0, age=30, year=2025)

    assert contribution.total == round(0.37 * 7400)


def test_contribution_uses_senior_rates_above_55():
    contribution = contribution_for_month(6000.0, 0.0, age=58, year=2026)

    assert contribution.total == round(0.34 * 6000)
    assert contribution.employee == round(0.18 * 6000)


def test_additional_wage_attracts_contribution():
    contribution = contribution_for_month(6000.0, 12000.0, age=30, year=2026)

    assert contribution.total == round(0.37 * (6000 + 12000))


def test_monthly_interest_applies_base_rates():
    accrued = monthly_interest(AccountBalances(oa=120000.0, sa=0.0, ma=0.0))

    # Base 2.5% on the whole balance, plus extra 1% on the first $20,000 of OA,
    # which is paid into the Special Account rather than back into OA.
    assert round(accrued.oa, 4) == round(120000 * 0.025 / 12, 4)
    assert round(accrued.sa, 4) == round(20000 * 0.01 / 12, 4)


def test_extra_interest_caps_ordinary_account_contribution_at_twenty_thousand():
    accrued = monthly_interest(AccountBalances(oa=30000.0, sa=40000.0, ma=0.0))

    expected_sa = (
        40000 * 0.04 / 12  # base
        + 40000 * 0.01 / 12  # extra on the remaining $40k of the $60k allowance
        + 20000 * 0.01 / 12  # extra earned on OA, credited to SA
    )
    assert round(accrued.sa, 4) == round(expected_sa, 4)


def test_extra_interest_stops_at_sixty_thousand_combined():
    accrued = monthly_interest(AccountBalances(oa=20000.0, sa=40000.0, ma=50000.0))

    # The $60,000 allowance is exhausted by OA + SA, so MediSave earns base only.
    assert round(accrued.ma, 4) == round(50000 * 0.04 / 12, 4)


def test_medisave_overflow_spills_into_special_account():
    balances = apply_medisave_overflow(AccountBalances(oa=100.0, sa=200.0, ma=80000.0), year=2026)

    assert balances.ma == 79000.0
    assert balances.sa == 1200.0
    assert balances.oa == 100.0


def test_medisave_below_the_cap_is_untouched():
    original = AccountBalances(oa=100.0, sa=200.0, ma=50000.0)

    assert apply_medisave_overflow(original, year=2026) == original


def test_months_until_55():
    assert months_until_55(54.0) == 12
    assert months_until_55(30.0) == 300
    assert months_until_55(60.0) == 0


def test_simulation_stops_at_55():
    member = CpfMember(age=54.0, monthly_salary=6000.0)

    result = simulate_cpf(member, months=120, start_year=2026, start_month=1)

    assert result.months_simulated == 12
    assert result.stopped_at_55 is True
    assert len(result.total) == 13


def test_simulation_does_not_stop_early_when_well_under_55():
    member = CpfMember(age=30.0, monthly_salary=6000.0)

    result = simulate_cpf(member, months=24, start_year=2026, start_month=1)

    assert result.months_simulated == 24
    assert result.stopped_at_55 is False


def test_first_month_lands_the_expected_allocation():
    member = CpfMember(age=30.0, monthly_salary=6000.0)

    result = simulate_cpf(member, months=1, start_year=2026, start_month=1)

    assert result.oa[1] == 1380.18
    assert result.sa[1] == 359.86
    assert result.ma[1] == 479.96


def test_interest_is_credited_only_in_december():
    member = CpfMember(age=30.0, monthly_salary=6000.0, oa_balance=50000.0)

    result = simulate_cpf(member, months=12, start_year=2026, start_month=1)

    assert result.interest[1] == 0.0
    assert result.interest[11] == 0.0
    assert result.interest[12] > 0.0


def test_opening_balance_earns_interest_but_not_in_the_first_month():
    member = CpfMember(age=30.0, monthly_salary=0.0, oa_balance=10000.0)

    result = simulate_cpf(member, months=12, start_year=2026, start_month=1)

    # No contributions, so the balance only moves when interest is credited.
    assert result.total[1] == 10000.0
    assert result.total[12] > 10000.0


def test_salary_growth_raises_later_contributions():
    member = CpfMember(age=30.0, monthly_salary=6000.0, salary_growth_rate=0.10)

    result = simulate_cpf(member, months=24, start_year=2026, start_month=1)

    assert result.contributions[1] == 2220.0
    assert result.contributions[13] == round(0.37 * 6600)


def test_bonus_month_adds_additional_wage():
    member = CpfMember(age=30.0, monthly_salary=6000.0, annual_bonus_months=2.0, bonus_month=12)

    result = simulate_cpf(member, months=12, start_year=2026, start_month=1)

    assert result.contributions[11] == 2220.0
    assert result.contributions[12] > 2220.0


def test_annual_wage_ceiling_limits_the_bonus():
    # $8,000/month is $96,000 of OW, leaving only $6,000 of headroom under the
    # $102,000 annual ceiling regardless of how large the bonus is.
    member = CpfMember(age=30.0, monthly_salary=8000.0, annual_bonus_months=6.0, bonus_month=12)

    result = simulate_cpf(member, months=12, start_year=2026, start_month=1)

    december_contribution = result.contributions[12]
    assert december_contribution == round(0.37 * (8000 + 6000))


def test_cumulative_contributions_start_from_opening_balance():
    member = CpfMember(age=30.0, monthly_salary=6000.0, oa_balance=1000.0)

    result = simulate_cpf(member, months=2, start_year=2026, start_month=1)
    contributed = cumulative_contributions(result)

    assert contributed[0] == 1000.0
    assert contributed[1] == 1000.0 + 2220.0
    assert contributed[2] == 1000.0 + 2 * 2220.0


def test_yearly_summary_rows_reconcile_to_total_value():
    member = CpfMember(age=30.0, monthly_salary=6000.0, oa_balance=20000.0)

    result = simulate_cpf(member, months=24, start_year=2026, start_month=1)
    rows = build_cpf_yearly_summary(result)

    assert [row["year"] for row in rows] == [0, 1, 2]
    assert all(row["dividend_income"] == 0.0 for row in rows)
    for row in rows:
        assert row["total_value"] >= row["contributed_total"]
    assert rows[-1]["total_value"] == result.total[24]


def test_yearly_summary_growth_is_a_per_year_delta():
    member = CpfMember(age=30.0, monthly_salary=6000.0, oa_balance=20000.0)

    result = simulate_cpf(member, months=24, start_year=2026, start_month=1)
    rows = build_cpf_yearly_summary(result)

    # Summing the per-year deltas must reproduce total growth over the period,
    # which is what cumulative_stack_series relies on when charting.
    total_growth = sum(row["growth_gain"] for row in rows)
    expected = rows[-1]["total_value"] - rows[-1]["contributed_total"]
    assert round(total_growth, 6) == round(expected, 6)
