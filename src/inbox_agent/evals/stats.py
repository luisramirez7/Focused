"""Statistics for honest reporting: repetitions are averaged per example first, then confidence
intervals are bootstrapped over examples (the unit we sampled), never over raw runs."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

import numpy as np
import pandas as pd

SEED = 1234
N_BOOT = 2000


def per_example_means(df: pd.DataFrame, metric: str, example_col: str = "example_id") -> pd.Series:
    """Collapse repetitions: one mean score per example (NaNs = not applicable, dropped)."""
    return df.dropna(subset=[metric]).groupby(example_col)[metric].mean()


def bootstrap_ci(
    values: Sequence[float], n_boot: int = N_BOOT, alpha: float = 0.05, seed: int = SEED
) -> tuple[float, float, float]:
    """Mean and percentile bootstrap CI over examples."""
    arr = np.asarray([v for v in values if v is not None and not math.isnan(v)], dtype=float)
    if arr.size == 0:
        return (math.nan, math.nan, math.nan)
    rng = np.random.default_rng(seed)
    boots = rng.choice(arr, size=(n_boot, arr.size), replace=True).mean(axis=1)
    lo, hi = np.quantile(boots, [alpha / 2, 1 - alpha / 2])
    return (float(arr.mean()), float(lo), float(hi))


def paired_bootstrap_delta(
    a: pd.Series, b: pd.Series, n_boot: int = N_BOOT, alpha: float = 0.05, seed: int = SEED
) -> tuple[float, float, float]:
    """Mean of (b - a) over examples present in both, with a paired bootstrap CI."""
    joined = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    if joined.empty:
        return (math.nan, math.nan, math.nan)
    return bootstrap_ci((joined["b"] - joined["a"]).to_numpy(), n_boot, alpha, seed)


def within_noise(ci: tuple[float, float, float]) -> bool:
    return ci[1] <= 0 <= ci[2]


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = successes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (center - half, center + half)


def percentile(values: Iterable[float], q: float) -> float:
    arr = np.asarray(list(values), dtype=float)
    return float(np.percentile(arr, q)) if arr.size else math.nan


def explode_slices(df: pd.DataFrame, slices_col: str = "slices") -> pd.DataFrame:
    """One row per (row, slice) so multi-tagged examples count toward each of their slices."""
    return df.explode(slices_col).rename(columns={slices_col: "slice"})


def slice_table(df: pd.DataFrame, metric: str, example_col: str = "example_id") -> pd.DataFrame:
    rows = []
    exploded = explode_slices(df)
    for name, group in exploded.groupby("slice"):
        means = per_example_means(group, metric, example_col)
        mean, lo, hi = bootstrap_ci(means.to_numpy())
        rows.append({"slice": name, "n": len(means), "mean": mean, "ci_low": lo, "ci_high": hi})
    return pd.DataFrame(rows).sort_values("slice").reset_index(drop=True)


def cohen_kappa(a: Sequence, b: Sequence) -> float:
    from sklearn.metrics import cohen_kappa_score

    if len(set(a) | set(b)) < 2:
        return 1.0 if list(a) == list(b) else 0.0
    return float(cohen_kappa_score(a, b))
