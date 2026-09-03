def compute_cagr(start_price: float, end_price: float, years: float) -> float:
    if years <= 0:
        raise ValueError(f"years must be positive, got {years}")
    if start_price <= 0:
        raise ValueError(f"start_price must be positive, got {start_price}")
    return (end_price / start_price) ** (1 / years) - 1


def annual_rate_to_periodic_rate(annual_rate: float, periods_per_year: int = 12) -> float:
    if periods_per_year <= 0:
        raise ValueError(f"periods_per_year must be positive, got {periods_per_year}")
    return (1 + annual_rate) ** (1 / periods_per_year) - 1
