"""Exact maximization and maximizer enumeration for Hare Share.

The SAT engine searches the complete binary configuration space.  It uses
affine symmetry only to reduce duplicate optimal configurations; it does not
sample or impose a configuration limit.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from math import comb
from time import monotonic

try:
    from pysat.card import CardEnc, EncType
    from pysat.examples.rc2 import RC2
    from pysat.formula import CNF, WCNF
    from pysat.solvers import Solver
except ImportError as exc:  # pragma: no cover - environment diagnostic
    raise SystemExit(
        "python-sat is required. Run this script with the sat-research "
        "environment's Python interpreter."
    ) from exc

from survival_calculation import (
    additive_energy,
    indices_from_mask,
    mask_from_indices,
    survival_count,
)


@dataclass(frozen=True)
class Maximum:
    p: int
    minutes: int
    value: int
    representative: int
    labelled_count: int
    energy_counts: tuple[tuple[int, int], ...]
    normalized_models: int
    affine_orbits: int


def is_prime(value: int) -> bool:
    if value < 2:
        return False
    return all(value % divisor for divisor in range(2, int(value**0.5) + 1))


def progression_masks(p: int, minutes: int) -> dict[int, int]:
    """Map each distinct nonzero-jump progression mask to its multiplicity."""
    masks: dict[int, int] = {}
    for start in range(p):
        for jump in range(1, p):
            mask = 0
            for step in range(minutes + 1):
                mask |= 1 << ((start + step * jump) % p)
            masks[mask] = masks.get(mask, 0) + 1
    return masks


def _base_cnf(p: int, stump_count: int, symmetry_break: bool) -> tuple[CNF, int]:
    cnf = CNF()
    cardinality = CardEnc.equals(
        lits=list(range(1, p + 1)),
        bound=stump_count,
        top_id=p,
        encoding=EncType.seqcounter,
    )
    cnf.extend(cardinality.clauses)
    top_id = cardinality.nv
    if symmetry_break and stump_count >= 2:
        # Every affine orbit has a representative containing both 0 and 1.
        cnf.append([1])
        cnf.append([2])
    return cnf, top_id


def _objective_encoding(
    p: int,
    minutes: int,
    symmetry_break: bool,
) -> tuple[CNF, list[int], list[int], int]:
    stump_count = (p - 1) // 2
    cnf, top_id = _base_cnf(p, stump_count, symmetry_break)
    objective_vars: list[int] = []
    weights: list[int] = []
    # Keep a separate indicator for each hare.  Some reversed progressions
    # visit the same positions, but distinct indicators let the installed
    # pure-cardinality encoder express an exact objective equality without
    # requiring the optional pypblib package.
    for start in range(p):
        for jump in range(1, p):
            top_id += 1
            progression = sorted({
                (start + step * jump) % p
                for step in range(minutes + 1)
            })
            # y iff every position in this progression is a stump.
            for index in progression:
                cnf.append([-top_id, index + 1])
            cnf.append([top_id, *(-(index + 1) for index in progression)])
            objective_vars.append(top_id)
            weights.append(1)
    return cnf, objective_vars, weights, top_id


def maximize_value(p: int, minutes: int, verbose: bool = True) -> int:
    """Prove and return max_S F(S,p,minutes)."""
    stump_count = (p - 1) // 2
    if minutes == 0:
        return p * stump_count
    if minutes == 1:
        return stump_count * stump_count
    if minutes >= stump_count:
        return stump_count

    cnf, objective_vars, weights, _ = _objective_encoding(
        p, minutes, symmetry_break=True
    )
    formula = WCNF()
    formula.extend(cnf.clauses)
    for variable, weight in zip(objective_vars, weights, strict=True):
        formula.append([variable], weight=weight)
    started = monotonic()
    if verbose:
        print(
            f"[p={p:2d} t={minutes:2d}] optimizing "
            f"{len(objective_vars):,} progression terms...",
            flush=True,
        )
    with RC2(formula, solver="cadical195", adapt=True, exhaust=True) as solver:
        model = solver.compute()
        if model is None:
            raise RuntimeError("unexpected UNSAT optimization instance")
        nonzero_survivors = sum(
            weight for variable, weight in zip(objective_vars, weights, strict=True)
            if model[variable - 1] > 0
        )
    value = stump_count + nonzero_survivors
    if verbose:
        print(
            f"[p={p:2d} t={minutes:2d}] proved F_max={value:,} "
            f"in {monotonic() - started:,.1f}s",
            flush=True,
        )
    return value


def maximize_value_by_decision(p: int, minutes: int, verbose: bool = True) -> int:
    """Find a construction, then prove that no configuration beats it.

    This tends to scale much better than core-guided MaxSAT when a strong
    construction is available.  Every SAT query still ranges over the full
    configuration space (modulo a sound affine symmetry break).
    """
    stump_count = (p - 1) // 2
    if minutes == 0:
        return p * stump_count
    if minutes == 1:
        return stump_count * stump_count
    if minutes >= stump_count:
        return stump_count

    interval = mask_from_indices(range(stump_count), p)
    candidate = survival_count(interval, p, minutes)
    cnf, objective_vars, _, top_id = _objective_encoding(
        p, minutes, symmetry_break=True
    )
    started = monotonic()
    attempt = 0
    while True:
        attempt += 1
        required_nonzero = candidate - stump_count + 1
        better = CardEnc.atleast(
            lits=objective_vars,
            bound=required_nonzero,
            top_id=top_id,
            encoding=EncType.cardnetwrk,
        )
        if verbose:
            print(
                f"[p={p:2d} t={minutes:2d}] decision {attempt}: "
                f"seeking F >= {candidate + 1:,} "
                f"({len(better.clauses):,} bound clauses)...",
                flush=True,
            )
        with Solver(
            name="cadical195",
            bootstrap_with=[*cnf.clauses, *better.clauses],
        ) as solver:
            if not solver.solve():
                if verbose:
                    print(
                        f"[p={p:2d} t={minutes:2d}] proved F_max={candidate:,} "
                        f"in {monotonic() - started:,.1f}s",
                        flush=True,
                    )
                return candidate
            mask = _mask_from_model(solver.get_model(), p)
            improved = survival_count(mask, p, minutes)
            if improved <= candidate:
                raise AssertionError(
                    f"SAT model promised >{candidate} but evaluates to {improved}"
                )
            candidate = improved
            if verbose:
                print(
                    f"[p={p:2d} t={minutes:2d}] found stronger construction "
                    f"F={candidate:,}",
                    flush=True,
                )


def affine_image(mask: int, p: int, multiplier: int, shift: int) -> int:
    image = 0
    for index in indices_from_mask(mask, p):
        image |= 1 << ((multiplier * index + shift) % p)
    return image


def canonical_affine(mask: int, p: int) -> int:
    return min(
        affine_image(mask, p, multiplier, shift)
        for multiplier in range(1, p)
        for shift in range(p)
    )


def affine_orbit_size(mask: int, p: int) -> int:
    stabilizer = sum(
        affine_image(mask, p, multiplier, shift) == mask
        for multiplier in range(1, p)
        for shift in range(p)
    )
    return p * (p - 1) // stabilizer


def normalized_affine_images(mask: int, p: int) -> set[int]:
    """Return orbit members containing the fixed symmetry-break pair {0,1}."""
    return {
        image
        for multiplier in range(1, p)
        for shift in range(p)
        if ((image := affine_image(mask, p, multiplier, shift)) & 3) == 3
    }


def _mask_from_model(model: list[int], p: int) -> int:
    positive = set(literal for literal in model if literal > 0)
    return sum(1 << index for index in range(p) if index + 1 in positive)


def enumerate_maximizers(
    p: int,
    minutes: int,
    maximum: int,
    progress_seconds: float = 10.0,
) -> Maximum:
    """Enumerate all affine orbits attaining a previously proved maximum."""
    stump_count = (p - 1) // 2
    if minutes in (0, 1) or minutes >= stump_count:
        raise ValueError(
            "all configurations maximize at this trivial time; use the "
            "analytic count instead"
        )

    cnf, objective_vars, weights, top_id = _objective_encoding(
        p, minutes, symmetry_break=True
    )
    target = maximum - stump_count
    equality = CardEnc.equals(
        lits=objective_vars,
        bound=target,
        top_id=top_id,
        encoding=EncType.cardnetwrk,
    )
    cnf.extend(equality.clauses)

    canonical_masks: set[int] = set()
    normalized_models = 0
    started = last_report = monotonic()
    with Solver(name="cadical195", bootstrap_with=cnf.clauses) as solver:
        while solver.solve():
            model = solver.get_model()
            mask = _mask_from_model(model, p)
            canonical = canonical_affine(mask, p)
            if canonical in canonical_masks:
                raise AssertionError("an already-blocked affine orbit reappeared")
            canonical_masks.add(canonical)
            # Block the entire affine orbit inside the normalized search space.
            # This turns hundreds of SAT calls per orbit into one while retaining
            # the exact normalized-model count.
            normalized_images = normalized_affine_images(canonical, p)
            normalized_models += len(normalized_images)
            for image in normalized_images:
                solver.add_clause([
                    -(index + 1) if image >> index & 1 else index + 1
                    for index in range(p)
                ])
            now = monotonic()
            if now - last_report >= progress_seconds:
                elapsed = now - started
                print(
                    f"[p={p:2d} t={minutes:2d}] enumerated "
                    f"{normalized_models:,} normalized optima; "
                    f"{len(canonical_masks):,} affine orbits; "
                    f"{normalized_models / elapsed:,.1f} models/s",
                    flush=True,
                )
                last_report = now

    labelled_count = 0
    energy_counts: dict[int, int] = {}
    for mask in canonical_masks:
        orbit_size = affine_orbit_size(mask, p)
        labelled_count += orbit_size
        energy = additive_energy(mask, p)
        energy_counts[energy] = energy_counts.get(energy, 0) + orbit_size
    representative = min(canonical_masks)
    print(
        f"[p={p:2d} t={minutes:2d}] enumeration complete: "
        f"{len(canonical_masks):,} affine orbits, "
        f"{labelled_count:,} labelled maximizers",
        flush=True,
    )
    return Maximum(
        p=p,
        minutes=minutes,
        value=maximum,
        representative=representative,
        labelled_count=labelled_count,
        energy_counts=tuple(sorted(energy_counts.items())),
        normalized_models=normalized_models,
        affine_orbits=len(canonical_masks),
    )


def raw_configuration_count(p: int) -> int:
    return comb(p, (p - 1) // 2)
