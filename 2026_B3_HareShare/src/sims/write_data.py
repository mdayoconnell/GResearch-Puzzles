"""Populate maxima.csv and s_max.csv with certified Hare Share results."""

from __future__ import annotations

import argparse
import csv
import sys
from math import comb
from pathlib import Path

from survival_calculation import indices_from_mask, mask_from_indices
from survival_maximization import (
    Maximum,
    enumerate_maximizers,
    is_prime,
    maximize_value_by_decision,
    raw_configuration_count,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MAXIMA_PATH = DATA / "maxima.csv"
S_MAX_PATH = DATA / "s_max.csv"


def weighted_percentile(
    energy_counts: tuple[tuple[int, int], ...], numerator: int, denominator: int
) -> int:
    total = sum(count for _, count in energy_counts)
    rank = (numerator * total + denominator - 1) // denominator
    cumulative = 0
    for energy, count in energy_counts:
        cumulative += count
        if cumulative >= rank:
            return energy
    raise AssertionError("empty energy distribution")


def append_rows(maximum: Maximum) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    maxima_exists = MAXIMA_PATH.exists()
    with MAXIMA_PATH.open("a", newline="") as handle:
        writer = csv.writer(handle)
        if not maxima_exists:
            writer.writerow([
                "p", "t", "F_max", "S_max_example", "proven", "search_method",
            ])
        writer.writerow([
            maximum.p,
            maximum.minutes,
            maximum.value,
            "{" + ", ".join(
                map(str, indices_from_mask(maximum.representative, maximum.p))
            ) + "}",
            "true",
            "sat_certified",
        ])

    stats_exists = S_MAX_PATH.exists()
    with S_MAX_PATH.open("a", newline="") as handle:
        writer = csv.writer(handle)
        if not stats_exists:
            writer.writerow([
                "p",
                "t",
                "maximizing_S_count",
                "affine_orbit_count",
                "normalized_models_enumerated",
                "additive_energy_p25",
                "additive_energy_p50",
                "additive_energy_p75",
                "additive_energy_p99",
                "energy_distribution_complete",
                "proven",
                "search_method",
            ])
        writer.writerow([
            maximum.p,
            maximum.minutes,
            maximum.labelled_count,
            maximum.affine_orbits,
            maximum.normalized_models,
            weighted_percentile(maximum.energy_counts, 25, 100),
            weighted_percentile(maximum.energy_counts, 50, 100),
            weighted_percentile(maximum.energy_counts, 75, 100),
            weighted_percentile(maximum.energy_counts, 99, 100),
            "true",
            "sat_certified",
            "true",
        ])


def append_trivial_row(p: int, minutes: int) -> None:
    """Write an analytically settled time at which every stump set maximizes."""
    stump_count = (p - 1) // 2
    representative = mask_from_indices(range(stump_count), p)
    value = stump_count * stump_count if minutes == 1 else stump_count
    DATA.mkdir(parents=True, exist_ok=True)
    maxima_exists = MAXIMA_PATH.exists()
    with MAXIMA_PATH.open("a", newline="") as handle:
        writer = csv.writer(handle)
        if not maxima_exists:
            writer.writerow([
                "p", "t", "F_max", "S_max_example", "proven", "search_method",
            ])
        writer.writerow([
            p,
            minutes,
            value,
            "{" + ", ".join(map(str, indices_from_mask(representative, p))) + "}",
            "true",
            "analytic",
        ])

    stats_exists = S_MAX_PATH.exists()
    with S_MAX_PATH.open("a", newline="") as handle:
        writer = csv.writer(handle)
        if not stats_exists:
            writer.writerow([
                "p",
                "t",
                "maximizing_S_count",
                "affine_orbit_count",
                "normalized_models_enumerated",
                "additive_energy_p25",
                "additive_energy_p50",
                "additive_energy_p75",
                "additive_energy_p99",
                "energy_distribution_complete",
                "proven",
                "search_method",
            ])
        writer.writerow([
            p,
            minutes,
            comb(p, stump_count),
            "",
            0,
            "",
            "",
            "",
            "",
            "false",
            "true",
            "analytic",
        ])


def completed_rows() -> set[tuple[int, int]]:
    if not MAXIMA_PATH.exists():
        return set()
    with MAXIMA_PATH.open(newline="") as handle:
        return {
            (int(row["p"]), int(row["t"]))
            for row in csv.DictReader(handle)
            if row["proven"].lower() == "true"
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-prime", type=int, default=41)
    parser.add_argument("--min-prime", type=int, default=3)
    parser.add_argument("--progress-seconds", type=float, default=10.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    primes = [
        p for p in range(args.min_prime, args.max_prime + 1) if is_prime(p)
    ]
    done = completed_rows()
    for p in primes:
        stump_count = (p - 1) // 2
        print(
            f"[p={p:2d}] starting exhaustive sweep over "
            f"{raw_configuration_count(p):,} labelled configurations",
            flush=True,
        )
        for minutes in range(1, stump_count + 1):
            if (p, minutes) in done:
                print(f"[p={p:2d} t={minutes:2d}] already complete", flush=True)
                continue
            # At t=1 and t>=|S| all stump sets maximize.  Their maximum and
            # count are exact; energy-distribution fields are explicitly left
            # incomplete rather than replaced by sampled percentiles.
            if minutes == 1 or minutes >= stump_count:
                value = stump_count * stump_count if minutes == 1 else stump_count
                print(
                    f"[p={p:2d} t={minutes:2d}] analytic F_max={value:,}; "
                    f"all {raw_configuration_count(p):,} sets maximize",
                    flush=True,
                )
                append_trivial_row(p, minutes)
                continue
            value = maximize_value_by_decision(p, minutes)
            result = enumerate_maximizers(
                p, minutes, value, args.progress_seconds
            )
            append_rows(result)
        print(f"[p={p:2d}] nontrivial sweep complete", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted; completed CSV rows are preserved.", file=sys.stderr)
        raise SystemExit(130)
