"""Successful-hop statistic used by the Cantelli investigation."""

from __future__ import annotations


def successful_hops(x: int, a: int, mask: int, p: int, minutes: int) -> int:
    """Count stump positions among x, x+a, ..., x+minutes*a."""
    return sum(
        bool(mask >> ((x + step * a) % p) & 1)
        for step in range(minutes + 1)
    )

