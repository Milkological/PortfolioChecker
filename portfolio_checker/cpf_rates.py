"""CPF statutory rates and ceilings, as data.

Every figure here is transcribed from CPF Board's published tables — nothing is
estimated. Sources are named next to each table. CPF revises most of these
annually, so when a new year's tables are published, update the numbers here and
bump RATES_EFFECTIVE_YEAR; no other module needs to change.

Scope note: these are the Singapore Citizen / 3rd-year-onwards SPR rates for
private sector and non-pensionable employees (CPF's "Table 1"). The graduated
1st/2nd-year SPR tables are not modelled.
"""

from dataclasses import dataclass

RATES_EFFECTIVE_YEAR = 2026

CONTRIBUTION_RATES_SOURCE = (
    "https://www.cpf.gov.sg/content/dam/web/employer/employer-obligations/"
    "documents/CPFcontributionratesfrom1Jan2026.pdf (Table 1)"
)
ALLOCATION_RATES_SOURCE = (
    "https://www.cpf.gov.sg/content/dam/web/employer/employer-obligations/"
    "documents/CPFAllocationRatesfromJanuary2026.pdf"
)
INTEREST_RATES_SOURCE = (
    "https://www.cpf.gov.sg/member/infohub/news/news-releases/"
    "cpf-interest-rates-from-1-january-to-31-march-2026-and-basic-healthcare-sum-for-2026"
)

# CPF contributions are payable only above this monthly total wage, and the
# employee's own share only kicks in above GRADUATED_WAGE_FLOOR.
NO_CONTRIBUTION_WAGE_CEILING = 50.0
GRADUATED_WAGE_FLOOR = 500.0
FULL_RATE_WAGE_FLOOR = 750.0


@dataclass(frozen=True)
class ContributionRates:
    """Rates for one age band, from CPF's Table 1 (effective 1 January 2026).

    total_rate / employee_rate apply to wages above $750. Below that, CPF uses
    the graduated formulas: for total wages of $50–$500 the employer pays
    low_wage_total_rate of total wages and the employee pays nothing; for
    $500–$750 the employee additionally pays
    graduated_employee_coefficient * (total_wages - $500).
    """

    total_rate: float
    employee_rate: float
    low_wage_total_rate: float
    graduated_employee_coefficient: float


# Keyed by the inclusive upper bound of the age band. CPF's bands read
# "55 & below", "Above 55 - 60", ... so a scan for the first band whose bound is
# >= the member's age selects correctly.
CONTRIBUTION_RATES = (
    # age <= 55: total 37%, employee 20% (max on OW $2,960 / $1,600)
    (55, ContributionRates(0.37, 0.20, 0.17, 0.60)),
    # above 55 to 60: total 34%, employee 18% — raised from 32.5% on 1 Jan 2026
    (60, ContributionRates(0.34, 0.18, 0.16, 0.54)),
    # above 60 to 65: total 25%, employee 12.5% — raised from 23.5% on 1 Jan 2026
    (65, ContributionRates(0.25, 0.125, 0.125, 0.375)),
    # above 65 to 70: total 16.5%, employee 7.5%
    (70, ContributionRates(0.165, 0.075, 0.09, 0.225)),
    # above 70: total 12.5%, employee 5%
    (float("inf"), ContributionRates(0.125, 0.05, 0.075, 0.15)),
)


@dataclass(frozen=True)
class AllocationRatios:
    """Share of the total contribution going to each account.

    CPF computes MediSave first, then Special/Retirement, and assigns the
    remainder to Ordinary — so `ordinary` is carried here for reference and
    assertion only. Use the documented order when splitting an actual amount.
    """

    ordinary: float
    special: float
    medisave: float


# From 1 January 2026. Bands read "35 & below", "Above 35 - 45", ...
ALLOCATION_RATES = (
    (35, AllocationRatios(0.6217, 0.1621, 0.2162)),
    (45, AllocationRatios(0.5677, 0.1891, 0.2432)),
    (50, AllocationRatios(0.5136, 0.2162, 0.2702)),
    (55, AllocationRatios(0.4055, 0.3108, 0.2837)),
    # From age 55 the Special Account is closed and this share goes to the
    # Retirement Account instead (up to the Full Retirement Sum). Modelled
    # here for completeness; the simulation stops at 55.
    (60, AllocationRatios(0.353, 0.3382, 0.3088)),
    (65, AllocationRatios(0.14, 0.44, 0.42)),
    (70, AllocationRatios(0.0607, 0.303, 0.6363)),
    (float("inf"), AllocationRatios(0.08, 0.08, 0.84)),
)

for _bound, _ratios in ALLOCATION_RATES:
    _total = _ratios.ordinary + _ratios.special + _ratios.medisave
    assert abs(_total - 1.0) < 1e-9, f"Allocation ratios for band {_bound} sum to {_total}, not 1.0"

# Monthly Ordinary Wage subject to CPF. Raised in steps under Budget 2023 and
# at its final planned level of $8,000 from 1 January 2026.
ORDINARY_WAGE_CEILING_BY_YEAR = {
    2023: 6000.0,
    2024: 6800.0,
    2025: 7400.0,
    2026: 8000.0,
}

# Caps OW + AW combined across a calendar year. Unchanged for many years.
ANNUAL_TOTAL_WAGE_CEILING = 102000.0

# MediSave cap. Raised to $79,000 for members below 65 in 2026; a member's BHS
# is frozen at the value in the year they turn 65.
BASIC_HEALTHCARE_SUM_BY_YEAR = {
    2024: 71500.0,
    2025: 75500.0,
    2026: 79000.0,
}

# Statutory floors, in force for the whole of 2026.
ORDINARY_ACCOUNT_INTEREST_RATE = 0.025
SPECIAL_ACCOUNT_INTEREST_RATE = 0.04
MEDISAVE_ACCOUNT_INTEREST_RATE = 0.04
RETIREMENT_ACCOUNT_INTEREST_RATE = 0.04

# Members below 55 earn an extra 1% on the first $60,000 of combined balances,
# of which at most $20,000 may come from the Ordinary Account. (Members 55 and
# above get an extra 2% on the first $30,000 and 1% on the next $30,000 — not
# modelled, since the simulation stops at 55.)
EXTRA_INTEREST_RATE = 0.01
EXTRA_INTEREST_BALANCE_CAP = 60000.0
EXTRA_INTEREST_ORDINARY_ACCOUNT_CAP = 20000.0

SPECIAL_ACCOUNT_CLOSURE_AGE = 55


def _lookup_by_age(table, age: float):
    for upper_bound, value in table:
        if age <= upper_bound:
            return value
    raise ValueError(f"No band found for age {age}")


def contribution_rates_for(age: float) -> ContributionRates:
    return _lookup_by_age(CONTRIBUTION_RATES, age)


def allocation_for(age: float) -> AllocationRatios:
    return _lookup_by_age(ALLOCATION_RATES, age)


def _lookup_by_year(table: dict, year: int) -> float:
    if year in table:
        return table[year]
    known_years = sorted(table)
    if year < known_years[0]:
        return table[known_years[0]]
    # Beyond the published tables, hold the latest known value rather than
    # extrapolating a number CPF has not announced.
    return table[known_years[-1]]


def ordinary_wage_ceiling(year: int) -> float:
    return _lookup_by_year(ORDINARY_WAGE_CEILING_BY_YEAR, year)


def basic_healthcare_sum(year: int) -> float:
    return _lookup_by_year(BASIC_HEALTHCARE_SUM_BY_YEAR, year)
