"""Exact survival counts for Hare Share.

Positions and jump sizes are elements of Z/pZ.  A hare (x, a) survives
through minute t when x, x+a, ..., x+t*a are all tree stumps.
"""

from __future__ import annotations

from collections.abc import Iterable


def mask_from_indices(indices: Iterable[int], p: int) -> int:
    """Return the p-bit stump mask for *indices*."""
    mask = 0
    for index in indices:
        if not 0 <= index < p:
            raise ValueError(f"stump index {index} is outside 0..{p - 1}")
        mask |= 1 << index
    return mask


def indices_from_mask(mask: int, p: int) -> tuple[int, ...]:
    """Return the sorted stump indices represented by *mask*."""
    return tuple(index for index in range(p) if mask >> index & 1)


def survival_count(mask: int, p: int, minutes: int) -> int:
    """Calculate F(S, p, minutes) exactly."""
    if minutes < 0:
        raise ValueError("minutes must be nonnegative")
    stumps = indices_from_mask(mask, p)
    total = 0
    for start in stumps:
        for jump in range(p):
            if all(mask >> ((start + step * jump) % p) & 1
                   for step in range(minutes + 1)):
                total += 1
    return total


def survival_curve(mask: int, p: int) -> tuple[int, ...]:
    """Return F(S,p,t) for every 0 <= t <= p-2.

    A run-length calculation obtains all times in one pass.  The jump-zero
    hares contribute |S| at every time.  For a nonzero jump, a run of L
    consecutive stumps contributes max(L-t, 0) survivors at minute t.
    """
    full_mask = (1 << p) - 1
    if mask & ~full_mask:
        raise ValueError("mask contains positions outside Z/pZ")
    stump_count = mask.bit_count()
    curve = [stump_count] * (p - 1)  # jump size zero
    curve[0] = p * stump_count

    for jump in range(1, p):
        sequence = [bool(mask >> ((step * jump) % p) & 1)
                    for step in range(p)]
        # There is at least one hole in every valid instance.  Rotate to begin
        # immediately after a hole, making every stump run non-circular.
        hole = sequence.index(False)
        run = 0
        for offset in range(1, p + 1):
            if sequence[(hole + offset) % p]:
                run += 1
            elif run:
                for minutes in range(1, min(run, p - 2) + 1):
                    curve[minutes] += run - minutes
                run = 0
    return tuple(curve)


def additive_energy(mask: int, p: int) -> int:
    """Return #{(a,b,c,d) in S^4 : a+b=c+d mod p}."""
    counts = [0] * p
    stumps = indices_from_mask(mask, p)
    for a in stumps:
        for b in stumps:
            counts[(a + b) % p] += 1
    return sum(count * count for count in counts)

