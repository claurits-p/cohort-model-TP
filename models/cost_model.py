"""
Cost model for payment processing.
Calculates total costs given volume and pricing structure.
"""
from __future__ import annotations
from dataclasses import dataclass

import config as cfg
from models.volume_forecast import VolumeForecastYear


@dataclass
class YearlyCosts:
    year: int
    cc_cost: float
    ach_cost: float
    bank_network_cost: float
    saas_cogs: float          # 15% of ARR (1 - 85% margin)
    total: float


def compute_yearly_costs(
    vol: VolumeForecastYear,
    saas_arr: float,
    cc_cost_rate: float = cfg.CC_COST_RATE,
    ach_cost_per_txn: float = cfg.ACH_COST_PER_TXN,
    saas_margin: float = cfg.SAAS_ARR_MARGIN,
) -> YearlyCosts:
    """Compute costs for a single year given volume forecast."""

    cc_cost = vol.cc * cc_cost_rate
    ach_cost = vol.ach_txn_count * ach_cost_per_txn
    bank_cost = vol.bank_network_txn_count * ach_cost_per_txn
    saas_cogs = saas_arr * (1 - saas_margin)

    return YearlyCosts(
        year=vol.year,
        cc_cost=cc_cost,
        ach_cost=ach_cost,
        bank_network_cost=bank_cost,
        saas_cogs=saas_cogs,
        total=cc_cost + ach_cost + bank_cost + saas_cogs,
    )
