import numpy as np
import pandas as pd

from inbox_agent.evals import stats as S


def test_bootstrap_ci_contains_mean_and_narrows():
    rng = np.random.default_rng(0)
    small = rng.binomial(1, 0.8, 20)
    large = rng.binomial(1, 0.8, 400)
    m1, lo1, hi1 = S.bootstrap_ci(small)
    m2, lo2, hi2 = S.bootstrap_ci(large)
    assert lo1 <= m1 <= hi1 and lo2 <= m2 <= hi2
    assert (hi2 - lo2) < (hi1 - lo1)


def test_per_example_means_collapse_repetitions():
    df = pd.DataFrame({"example_id": ["a", "a", "a", "b"], "m": [1, 0, 1, 1]})
    means = S.per_example_means(df, "m")
    assert means["a"] == 2 / 3 and means["b"] == 1


def test_paired_delta_identical_is_within_noise():
    a = pd.Series([1, 0, 1, 1, 0], index=list("abcde"), dtype=float)
    ci = S.paired_bootstrap_delta(a, a.copy())
    assert ci[0] == 0 and S.within_noise(ci)
    b = pd.Series([1, 1, 1, 1, 1], index=list("abcde"), dtype=float)
    a2 = pd.Series([0, 0, 0, 0, 0], index=list("abcde"), dtype=float)
    assert not S.within_noise(S.paired_bootstrap_delta(a2, b))


def test_percentile_p95():
    assert S.percentile(range(1, 101), 95) == np.percentile(range(1, 101), 95)


def test_kappa():
    assert S.cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0
    rng = np.random.default_rng(1)
    a, b = rng.integers(0, 2, 2000), rng.integers(0, 2, 2000)
    assert abs(S.cohen_kappa(a, b)) < 0.1


def test_slice_table_counts_multi_tagged_examples():
    df = pd.DataFrame(
        {
            "example_id": ["a", "b", "c"],
            "slices": [["normal"], ["normal", "pii"], ["pii"]],
            "m": [1.0, 0.0, 1.0],
        }
    )
    table = S.slice_table(df, "m").set_index("slice")
    assert table.loc["normal", "n"] == 2 and table.loc["pii", "n"] == 2


def test_wilson():
    lo, hi = S.wilson_interval(8, 10)
    assert 0 < lo < 0.8 < hi < 1
