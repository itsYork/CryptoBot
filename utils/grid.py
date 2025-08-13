from __future__ import annotations

from typing import List


def symmetric_grid(anchor: float, step: float, levels: int) -> List[float]:
    """Build a symmetric price grid around anchor with given step and number of levels."""
    return [anchor + step * i for i in range(-levels, levels + 1)]
