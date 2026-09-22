"""CPF accumulation model — pure arithmetic, no I/O.

Mirrors the shape of simulation.py: small functions for one month's mechanics,
wrapped by a loop that records a monthly series.

Modelled: employer + employee contributions by age band and wage band, the
Ordinary Wage and Annual Total Wage ceilings, age-banded allocation across
OA/SA/MA, base and extra interest, and MediSave overflow above the Basic
Healthcare Sum.

Not modelled: the age-55 transition (Retirement Account creation, SA closure,
FRS top-ups) or CPF LIFE payouts. The projection deliberately stops at 55.
"""

import math
from dataclasses import dataclass
from datetime import date

from portfolio_checker.cpf_rates import (
    ANNUAL_TOTAL_WAGE_CEILING,
    EXTRA_INTEREST_BALANCE_CAP,
    EXTRA_INTEREST_ORDINARY_ACCOUNT_CAP,
    EXTRA_INTEREST_RATE,
    FULL_RATE_WAGE_FLOOR,
    GRADUATED_WAGE_FLOOR,
    MEDISAVE_ACCOUNT_INTEREST_RATE,
    NO_CONTRIBUTION_WAGE_CEILING,
    ORDINARY_ACCOUNT_INTEREST_RATE,
    SPECIAL_ACCOUNT_CLOSURE_AGE,
    SPECIAL_ACCOUNT_INTEREST_RATE,
    allocation_for,
    basic_healthcare_sum,
    contribution_rates_for,
    ordinary_wage_ceiling,
)

MONTHS_PER_YEAR = 12


@dataclass
class CpfMember:
    age: float
    monthly_salary: float
    annual_bonus_months: float = 0.0
    oa_balance: float = 0.0
    sa_balance: float = 0.0
    ma_balance: float = 0.0
    salary_growth_rate: float = 0.0
    bonus_month: int = 12


@dataclass
class AccountBalances:
    oa: float
    sa: float
    ma: float

    @property
    def total(self) -> float:
        return self.oa + self.sa + self.ma


@dataclass
class MonthlyContribution:
    total: float
    employee: float
    employer: float


@dataclass
class CpfResult:
    oa: list
    sa: list
    ma: list
    total: list
    contributions: list
    interest: list
    months_simulated: int
    stopped_at_55: bool


def round_to_nearest_dollar(amount: float) -> float:
    """CPF rounds a total contribution down below 50 cents and up from 50 cents."""
    return float(math.floor(amount + 0.5))


def round_down_to_dollar(amount: float) -> float:
    return float(math.floor(amount))


def contribution_for_month(
    ordinary_wage: float, additional_wage: float, age: float, year: int
) -> MonthlyContribution:
    """One month's CPF contribution, following CPF's published computation steps.

    The wage bands are assessed on total wages for the calendar month; above
    $750 the full rates apply to Ordinary Wages (capped at the OW ceiling) plus
    Additional Wages.
    """
    rates = contribution_rates_for(age)
    total_wages = ordinary_wage + additional_wage

    if total_wages <= NO_CONTRIBUTION_WAGE_CEILING:
        return MonthlyContribution(0.0, 0.0, 0.0)

    if total_wages <= GRADUATED_WAGE_FLOOR:
        total = rates.low_wage_total_rate * total_wages
        employee = 0.0
    elif total_wages <= FULL_RATE_WAGE_FLOOR:
        employee = rates.graduated_employee_coefficient * (total_wages - GRADUATED_WAGE_FLOOR)
        total = rates.low_wage_total_rate * total_wages + employee
    else:
        capped_ordinary_wage = min(ordinary_wage, ordinary_wage_ceiling(year))
        contributable_wage = capped_ordinary_wage + additional_wage
        total = rates.total_rate * contributable_wage
        employee = rates.employee_rate * contributable_wage

    rounded_total = round_to_nearest_dollar(total)
    rounded_employee = round_down_to_dollar(employee)
    return MonthlyContribution(
        total=rounded_total,
        employee=rounded_employee,
        employer=rounded_total - rounded_employee,
    )


def split_contribution(total_contribution: float, age: float) -> AccountBalances:
    """Split a contribution across accounts in CPF's documented order.

    MediSave is computed first, then Special, and the remainder goes to
    Ordinary — computing OA as a residual rather than by its own ratio is what
    makes the cents tie out against CPF's worked examples.
    """
    ratios = allocation_for(age)
    medisave = round(total_contribution * ratios.medisave, 2)
    special = round(total_contribution * ratios.special, 2)
    ordinary = round(total_contribution - medisave - special, 2)
    return AccountBalances(oa=ordinary, sa=special, ma=medisave)


def apply_medisave_overflow(balances: AccountBalances, year: int) -> AccountBalances:
    """MediSave above the Basic Healthcare Sum spills into the Special Account.

    (Before 55 and below the Full Retirement Sum the overflow goes to SA; the
    onward spill to OA only applies once the FRS is met, which is outside this
    model's scope.)
    """
    cap = basic_healthcare_sum(year)
    if balances.ma <= cap:
        return balances
    overflow = balances.ma - cap
    return AccountBalances(oa=balances.oa, sa=balances.sa + overflow, ma=cap)


def monthly_interest(balances: AccountBalances) -> AccountBalances:
    """One month's interest accrual, for a member below 55.

    CPF computes interest monthly on the lowest balance of the month and credits
    it once a year, so callers should accrue this against opening balances and
    only add it to the accounts at year end.

    Extra interest applies to the first $60,000 of combined balances, of which
    at most $20,000 may come from OA. Extra interest earned on OA balances is
    paid into the Special Account, not back into OA.
    """
    base_oa = balances.oa * ORDINARY_ACCOUNT_INTEREST_RATE / MONTHS_PER_YEAR
    base_sa = balances.sa * SPECIAL_ACCOUNT_INTEREST_RATE / MONTHS_PER_YEAR
    base_ma = balances.ma * MEDISAVE_ACCOUNT_INTEREST_RATE / MONTHS_PER_YEAR

    ordinary_eligible = min(balances.oa, EXTRA_INTEREST_ORDINARY_ACCOUNT_CAP)
    remaining_allowance = EXTRA_INTEREST_BALANCE_CAP - ordinary_eligible
    special_eligible = min(balances.sa, remaining_allowance)
    remaining_allowance -= special_eligible
    medisave_eligible = min(balances.ma, remaining_allowance)

    monthly_extra_rate = EXTRA_INTEREST_RATE / MONTHS_PER_YEAR
    extra_from_ordinary = ordinary_eligible * monthly_extra_rate
    extra_special = special_eligible * monthly_extra_rate
    extra_medisave = medisave_eligible * monthly_extra_rate

    return AccountBalances(
        oa=base_oa,
        sa=base_sa + extra_special + extra_from_ordinary,
        ma=base_ma + extra_medisave,
    )


def months_until_55(age: float) -> int:
    return max(0, int(round((SPECIAL_ACCOUNT_CLOSURE_AGE - age) * MONTHS_PER_YEAR)))


def simulate_cpf(member: CpfMember, months: int, start_year: int = None, start_month: int = None):
    """Project CPF balances forward month by month, stopping at age 55.

    Returns a CpfResult whose series are indexed by month, with index 0 holding
    the starting balances — the same convention as simulate_portfolio, so
    graph.extract_yearly_points works on them unchanged.
    """
    today = date.today()
    year = start_year if start_year is not None else today.year
    month = start_month if start_month is not None else today.month

    capped_months = min(months, months_until_55(member.age))
    stopped_at_55 = capped_months < months

    balances = AccountBalances(oa=member.oa_balance, sa=member.sa_balance, ma=member.ma_balance)
    age = member.age
    salary = member.monthly_salary

    oa_series = [balances.oa]
    sa_series = [balances.sa]
    ma_series = [balances.ma]
    total_series = [balances.total]
    contributions = [0.0]
    interest_series = [0.0]

    pending_interest = AccountBalances(0.0, 0.0, 0.0)
    ordinary_wage_paid_this_year = 0.0

    for _ in range(capped_months):
        # Interest accrues on the opening balance, which is the month's lowest.
        accrued = monthly_interest(balances)
        pending_interest = AccountBalances(
            oa=pending_interest.oa + accrued.oa,
            sa=pending_interest.sa + accrued.sa,
            ma=pending_interest.ma + accrued.ma,
        )

        contributable_ordinary_wage = min(salary, ordinary_wage_ceiling(year))
        ordinary_wage_paid_this_year += contributable_ordinary_wage

        additional_wage = salary * member.annual_bonus_months if month == member.bonus_month else 0.0
        if additional_wage:
            # CPF's Additional Wage ceiling is $102,000 less the whole calendar
            # year's Ordinary Wages, so project the rest of the year rather than
            # using only the months elapsed so far.
            months_left_in_year = MONTHS_PER_YEAR - month
            projected_annual_ordinary_wage = (
                ordinary_wage_paid_this_year + contributable_ordinary_wage * months_left_in_year
            )
            allowance = max(0.0, ANNUAL_TOTAL_WAGE_CEILING - projected_annual_ordinary_wage)
            additional_wage = min(additional_wage, allowance)

        contribution = contribution_for_month(salary, additional_wage, age, year)
        allocated = split_contribution(contribution.total, age)
        balances = AccountBalances(
            oa=balances.oa + allocated.oa,
            sa=balances.sa + allocated.sa,
            ma=balances.ma + allocated.ma,
        )
        balances = apply_medisave_overflow(balances, year)

        credited_interest = 0.0

        if month == MONTHS_PER_YEAR:
            balances = AccountBalances(
                oa=balances.oa + pending_interest.oa,
                sa=balances.sa + pending_interest.sa,
                ma=balances.ma + pending_interest.ma,
            )
            balances = apply_medisave_overflow(balances, year)
            credited_interest = pending_interest.total
            pending_interest = AccountBalances(0.0, 0.0, 0.0)

            month = 1
            year += 1
            ordinary_wage_paid_this_year = 0.0
            salary *= 1 + member.salary_growth_rate
        else:
            month += 1

        age += 1 / MONTHS_PER_YEAR

        oa_series.append(balances.oa)
        sa_series.append(balances.sa)
        ma_series.append(balances.ma)
        total_series.append(balances.total)
        contributions.append(contribution.total)
        interest_series.append(credited_interest)

    return CpfResult(
        oa=oa_series,
        sa=sa_series,
        ma=ma_series,
        total=total_series,
        contributions=contributions,
        interest=interest_series,
        months_simulated=capped_months,
        stopped_at_55=stopped_at_55,
    )


def cumulative_contributions(result: CpfResult) -> list:
    """Running total of money paid in, starting from the opening balance."""
    running = result.total[0]
    series = [running]
    for contribution in result.contributions[1:]:
        running += contribution
        series.append(running)
    return series


def build_cpf_yearly_summary(result: CpfResult) -> list:
    """Reshape a CpfResult into the row dicts the existing charts already consume.

    Contributions map to `contributed_total`, interest falls out as
    `growth_gain`, and `dividend_income` is always zero — so
    plotly_view.build_stacked_figure and graph.cumulative_stack_series work on
    CPF rows with no changes. Delegates the per-year deltas to
    yearly_summary.build_yearly_summary so the arithmetic matches the market
    portfolio's exactly.
    """
    from portfolio_checker import yearly_summary
    from portfolio_checker.graph import build_year_labels, extract_yearly_points

    full_years = result.months_simulated // MONTHS_PER_YEAR
    year_labels = build_year_labels(full_years)
    return yearly_summary.build_yearly_summary(
        year_labels,
        extract_yearly_points(cumulative_contributions(result)),
        [0.0] * (result.months_simulated + 1),
        extract_yearly_points(result.total),
    )
