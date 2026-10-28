"""
The statistics. Each test asks: does signal X in quarter t line up with
revenue in quarter t (horizon 0, "nowcast") or t+1 (horizon 1, "lead")?

Safeguards against fooling yourself
-----------------------------------
- Within-company comparison: each company's average is subtracted, so a big
  company can't dominate and a pooled result isn't just "big firms are big".
- Circular-shift permutation test: to build the "no relationship" world we
  slide each company's signal along in time (wrapping around). This keeps the
  signal's own slow-moving patterns - ordinary tests ignore those and report
  too many false positives with year-on-year data.
- Benjamini-Hochberg: adjusts p-values because we run many tests at once.
- Out-of-sample R^2: fit on early quarters, score on later ones, against a
  baseline that predicts each company's average.
"""
import numpy as np
import pandas as pd
from scipy import stats

import config

N_PERMUTATIONS = 2000
RNG_SEED = 42  # fixed so results are reproducible


def signals_in(panel: pd.DataFrame) -> list[str]:
    return sorted(c[:-6] for c in panel.columns if c.endswith("_level"))


def _pairs(panel, signal, measure, horizon):
    """x = signal measure at t, y = revenue measure at t (+1 if horizon=1)."""
    x_col = f"{signal}_{measure}"
    y_col = f"rev_{measure}" + ("_next" if horizon == 1 else "")
    d = panel[["company_id", "period_end", x_col, y_col]].dropna()
    return d.rename(columns={x_col: "x", y_col: "y"})


def _demean(d):
    d = d.copy()
    d["xd"] = d["x"] - d.groupby("company_id")["x"].transform("mean")
    d["yd"] = d["y"] - d.groupby("company_id")["y"].transform("mean")
    return d


def _corr(a, b):
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return np.nan
    return float(np.corrcoef(a, b)[0, 1])


def permutation_pvalue(d: pd.DataFrame, n=N_PERMUTATIONS, seed=RNG_SEED) -> tuple[float, float]:
    """Two-sided p-value for the pooled within-company correlation."""
    d = _demean(d).sort_values(["company_id", "period_end"])
    observed = _corr(d["xd"].values, d["yd"].values)
    if np.isnan(observed):
        return observed, np.nan
    rng = np.random.default_rng(seed)
    groups = [g for _, g in d.groupby("company_id")]
    count = 0
    for _ in range(n):
        xs, ys = [], []
        for g in groups:
            k = len(g)
            shift = rng.integers(4, k - 3) if k >= 8 else rng.integers(1, max(k, 2))
            xs.append(np.roll(g["xd"].values, shift))
            ys.append(g["yd"].values)
        r = _corr(np.concatenate(xs), np.concatenate(ys))
        if abs(r) >= abs(observed):
            count += 1
    return observed, (count + 1) / (n + 1)


def hit_rate(d: pd.DataFrame) -> tuple[float, int, float]:
    """Share of quarters where signal and revenue moved in the same direction."""
    nz = d[(d["x"] != 0) & (d["y"] != 0)]
    n = len(nz)
    if n == 0:
        return np.nan, 0, np.nan
    hits = int((np.sign(nz["x"]) == np.sign(nz["y"])).sum())
    p = stats.binomtest(hits, n, 0.5).pvalue
    return hits / n, n, p


def out_of_sample_r2(d: pd.DataFrame, split=config.OUT_OF_SAMPLE_START) -> float:
    """Fit a pooled within-company slope before `split`; score after it.
    Baseline = each company's training average. >0 means the signal helped."""
    train = d[d["period_end"] < split]
    test = d[d["period_end"] >= split]
    if len(train) < 20 or len(test) < 10:
        return np.nan
    mx = train.groupby("company_id")["x"].mean()
    my = train.groupby("company_id")["y"].mean()
    tr = _demean(train)
    denom = (tr["xd"] ** 2).sum()
    if denom == 0:
        return np.nan
    slope = (tr["xd"] * tr["yd"]).sum() / denom
    test = test[test["company_id"].isin(mx.index)]
    base = test["company_id"].map(my)
    pred = base + slope * (test["x"] - test["company_id"].map(mx))
    sse_model = ((test["y"] - pred) ** 2).sum()
    sse_base = ((test["y"] - base) ** 2).sum()
    return float(1 - sse_model / sse_base) if sse_base > 0 else np.nan


def benjamini_hochberg(p: pd.Series) -> pd.Series:
    p = p.astype(float)
    ok = p.dropna()
    m = len(ok)
    if m == 0:
        return p
    order = ok.sort_values()
    ranked = order.values * m / np.arange(1, m + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = pd.Series(np.nan, index=p.index)
    out[order.index] = np.minimum(ranked, 1.0)
    return out


def scorecard(panel: pd.DataFrame) -> pd.DataFrame:
    """Pooled results: every signal x measure x horizon."""
    rows = []
    for s in signals_in(panel):
        for measure in ("yoy", "accel"):
            for h in (0, 1):
                d = _pairs(panel, s, measure, h)
                if len(d) < 12:
                    continue
                r, p = permutation_pvalue(d)
                hr, n_hr, _ = hit_rate(d)
                rows.append(dict(
                    signal=s, measure=measure, horizon=h, n=len(d),
                    companies=d["company_id"].nunique(),
                    corr_within=r, p_perm=p, hit_rate=hr,
                    oos_r2=out_of_sample_r2(d),
                ))
    out = pd.DataFrame(rows)
    if not out.empty:
        out["p_adjusted"] = benjamini_hochberg(out["p_perm"])
    return out


def company_breakdown(panel: pd.DataFrame, measure="accel", horizon=0) -> pd.DataFrame:
    """Per-company Spearman correlation and hit rate (descriptive only:
    ~35 quarters per company is too few for strong claims)."""
    rows = []
    for s in signals_in(panel):
        d_all = _pairs(panel, s, measure, horizon)
        for cid, d in d_all.groupby("company_id"):
            if len(d) < 8:
                continue
            rho = stats.spearmanr(d["x"], d["y"]).statistic
            hr, n, p_hr = hit_rate(d)
            rows.append(dict(signal=s, company_id=cid, n=len(d),
                             spearman=float(rho), hit_rate=hr, hit_n=n, hit_p=p_hr))
    return pd.DataFrame(rows)
