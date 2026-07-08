"""内置样例数据(seeds)."""

from __future__ import annotations

from wto_policy.core.tariff_model import HsCode
from wto_policy.data.seed.htsus_sample import SAMPLE_HTSUS, load_sample

__all__ = ["SAMPLE_HTSUS", "HsCode", "load_sample"]
