"""
3-year volume forecast using real cohort Vol/MRR and Card Vol/MRR ratios.

Monthly ratios are averages across 24 historical cohorts (Q1 2020 – Q4 2025).
Volume = ratio * per-deal MRR for each month.
Payment mix: Card % from real data, Bank = 5% flat, ACH = remainder.
"""
from __future__ import annotations
from dataclasses import dataclass

import config as cfg

BANK_PCT = 0.05
YEAR3_CARD_PCT = 0.30

# Average Total Volume / MRR by month-since-close (24 cohorts).
MONTHLY_VOL_MRR = {
    1: 0.39, 2: 1.79, 3: 14.97, 4: 27.33, 5: 48.75, 6: 73.10,
    7: 94.77, 8: 116.05, 9: 137.01, 10: 149.22, 11: 160.73, 12: 169.68,
    13: 174.24, 14: 176.66, 15: 191.01, 16: 183.69, 17: 187.53, 18: 196.78,
    19: 195.75, 20: 202.44, 21: 208.86, 22: 222.75, 23: 218.00, 24: 233.93,
    25: 228.37, 26: 228.33, 27: 233.39, 28: 238.29, 29: 235.21, 30: 243.55,
    31: 229.59, 32: 232.23, 33: 235.11, 34: 211.73, 35: 206.77, 36: 212.82,
}

# Average Card Volume / MRR by month-since-close (24 cohorts).
MONTHLY_CARD_MRR = {
    1: 0.26, 2: 1.03, 3: 2.95, 4: 9.39, 5: 20.02, 6: 31.39,
    7: 39.39, 8: 49.30, 9: 56.56, 10: 60.08, 11: 59.33, 12: 68.71,
    13: 69.78, 14: 70.83, 15: 72.61, 16: 71.97, 17: 72.85, 18: 72.75,
    19: 73.41, 20: 76.64, 21: 80.57, 22: 82.19, 23: 83.13, 24: 90.29,
    25: 89.22, 26: 84.37, 27: 86.15, 28: 86.08, 29: 83.73, 30: 82.61,
    31: 84.44, 32: 82.47, 33: 81.66, 34: 81.10, 35: 83.29, 36: 83.92,
}


@dataclass
class VolumeForecastYear:
    year: int
    total: float
    cc: float
    ach: float
    bank_network: float

    @property
    def ach_txn_count(self) -> int:
        if cfg.ACH_AVG_TXN_SIZE <= 0:
            return 0
        return int(self.ach / cfg.ACH_AVG_TXN_SIZE)

    @property
    def bank_network_txn_count(self) -> int:
        if cfg.ACH_AVG_TXN_SIZE <= 0:
            return 0
        return int(self.bank_network / cfg.ACH_AVG_TXN_SIZE)


def forecast_volume_y1_y3(
    per_deal_arr: float,
) -> dict[int, VolumeForecastYear]:
    """
    Returns {1: VolumeForecastYear, 2: ..., 3: ...}.

    Uses real monthly Vol/MRR and Card Vol/MRR ratios from historical cohorts.
    Card % comes from data, Bank = 5% of total, ACH = remainder.
    """
    per_deal_mrr = per_deal_arr / 12.0

    forecast: dict[int, VolumeForecastYear] = {}

    for year in (1, 2, 3):
        m_start = (year - 1) * 12 + 1
        m_end = year * 12 + 1

        year_total = 0.0
        year_card = 0.0

        for m in range(m_start, m_end):
            year_total += MONTHLY_VOL_MRR.get(m, 0) * per_deal_mrr
            year_card += MONTHLY_CARD_MRR.get(m, 0) * per_deal_mrr

        if year == 3:
            year_card = year_total * YEAR3_CARD_PCT

        year_bank = year_total * BANK_PCT
        year_ach = year_total - year_card - year_bank

        forecast[year] = VolumeForecastYear(
            year=year,
            total=year_total,
            cc=year_card,
            ach=year_ach,
            bank_network=year_bank,
        )

    return forecast
