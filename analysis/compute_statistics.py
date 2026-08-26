"""Reproduces every statistical result reported in the paper (Section 5 and the
minimization analysis in Section 5.1.2): Shapiro-Wilk normality checks,
Kruskal-Wallis tests, Dunn's post-hoc test with Bonferroni correction, Spearman
correlations, and eta^2_H effect sizes.

Data sources (all pre-existing in this replication package -- nothing here re-runs
EvoMaster or the ../tool/ extraction scripts):
  - results/statistics/experiment-date-03-05-25-time-21-29-51-725.csv
      (canonical dataset: num_tests + the 7 REST-specific coverage criteria,
      30 rows = 3 techniques x 10 repetitions)
  - results/official-run/repetition_*/<ALGO>/execution_output.txt
      (EvoMaster's raw console logs, for real execution time and the
      minimization-phase analysis)
  - results/statistics/minimization_analysis.csv
      (produced by ../tool/analyze_minimization.py from the logs above)

Usage: run from replication-package/analysis/:
    pip install -r requirements.txt
    python compute_statistics.py
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd
import scikit_posthocs as sp
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
CANONICAL_CSV = ROOT / "results" / "statistics" / "experiment-date-03-05-25-time-21-29-51-725.csv"
MINIMIZATION_CSV = ROOT / "results" / "statistics" / "minimization_analysis.csv"
OFFICIAL_RUN = ROOT / "results" / "official-run"

TECHS = ["RANDOM", "SMARTS", "WTS"]

CRIT_COLS = {
    "PC": "input_path_coverage",
    "OC": "input_operation_coverage",
    "RPC": "input_parameter_coverage",
    "RPVC": "input_parameter_value_coverage",
    "SCC": "output_status_code_coverage",
    "SCCC": "output_status_code_class_coverage",
    "RBPC": "output_response_body_properties_coverage",
}


def hr(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def eta2_h(H, k, n):
    """eta^2_H = (H - k + 1) / (n - k), per Tomczak & Tomczak (2014)."""
    return (H - k + 1) / (n - k)


def kruskal_and_dunn(df, col, label):
    groups = [df[df.algorithm == t][col].dropna().values for t in TECHS]
    H, p = stats.kruskal(*groups)
    eff = eta2_h(H, k=3, n=sum(len(g) for g in groups))
    print(f"\n[{label}] Kruskal-Wallis: H={H:.2f}, p={p:.6f}, eta^2_H={eff:.2f}")
    if p < 0.05:
        dunn = sp.posthoc_dunn(df, val_col=col, group_col="algorithm", p_adjust="bonferroni")
        print(f"[{label}] Dunn's post-hoc (Bonferroni-corrected p-values):")
        print(dunn.round(4).to_string())
    return H, p


def load_canonical():
    df = pd.read_csv(CANONICAL_CSV)
    df["aggregate"] = df[list(CRIT_COLS.values())].mean(axis=1)
    return df


def extract_real_execution_time():
    rows = []
    for rep_dir in sorted(OFFICIAL_RUN.glob("repetition_*")):
        for algo_dir in rep_dir.iterdir():
            if not algo_dir.is_dir() or algo_dir.name == "criteria":
                continue
            log = algo_dir / "execution_output.txt"
            if not log.exists():
                continue
            text = log.read_text(errors="ignore")
            m = re.search(r"Passed time \(seconds\): (\d+)", text)
            if m:
                rows.append({"algorithm": algo_dir.name, "minutes": int(m.group(1)) / 60})
    return pd.DataFrame(rows)


def section_shapiro(df):
    hr("Shapiro-Wilk normality checks")
    for t in TECHS:
        w, p = stats.shapiro(df[df.algorithm == t]["num_tests"])
        print(f"num_tests, {t}: W={w:.3f}, p={p:.4f}")


def section_rq1_test_suite_size(df):
    hr("RQ1a -- Test-suite size (NT)")
    print(df.groupby("algorithm")["num_tests"].agg(["mean", "median", "std"]).round(2))
    kruskal_and_dunn(df, "num_tests", "NT")


def section_rq1_real_time():
    hr("RQ1b -- Real execution time")
    et = extract_real_execution_time()
    print(et.groupby("algorithm")["minutes"].agg(["mean", "median", "std"]).round(2))
    q = et.groupby("algorithm")["minutes"].quantile([0.25, 0.75]).unstack()
    print("\nQ1-Q3 (minutes):")
    print(q.round(1))
    et["algorithm"] = et["algorithm"].astype(str)
    kruskal_and_dunn(et.rename(columns={"minutes": "minutes"}), "minutes", "real execution time")


def section_minimization():
    hr("RQ1b (mechanism) -- Minimization-phase analysis")
    mdf = pd.read_csv(MINIMIZATION_CSV)
    print(mdf.groupby("algorithm")[["candidates_gt1", "minim_seconds"]].agg(["mean", "median"]).round(2))
    mdf["removed"] = mdf["raw_tests"] - mdf["final_tests"]
    print("\nTests removed by minimization (raw_tests - final_tests):")
    print(mdf.groupby("algorithm")["removed"].agg(["mean", "median", "max"]))
    print(f"\nAll executions timed out: {mdf['timed_out'].all()} ({mdf['timed_out'].sum()}/{len(mdf)})")

    kruskal_and_dunn(mdf, "candidates_gt1", "candidates_gt1")
    kruskal_and_dunn(mdf, "removed", "tests removed")

    rho, p = stats.spearmanr(mdf["candidates_gt1"], mdf["minim_seconds"])
    print(f"\nSpearman(candidates_gt1, minim_seconds), pooled: rho={rho:.4f}, p={p:.6f}")


def section_rq2_correlation(df):
    hr("RQ2 -- Spearman correlation between NT and coverage criteria")
    for crit in ["RPC", "RPVC", "SCC", "RBPC"]:
        rho, p = stats.spearmanr(df["num_tests"], df[CRIT_COLS[crit]])
        print(f"NT vs {crit}: rho={rho:.2f}, p={p:.4f}")


def section_rq3_per_criterion(df):
    hr("RQ3 -- Per-criterion coverage (Kruskal-Wallis + Dunn's)")
    for crit, col in CRIT_COLS.items():
        if df[col].std() < 1e-9:
            print(f"\n[{crit}] no variance across executions (100% in all runs) -- n/a")
            continue
        kruskal_and_dunn(df, col, crit)

    print("\nMedians per technique (used in Table 4):")
    print(df.groupby("algorithm")[[CRIT_COLS[c] for c in ["RPC", "RPVC", "RBPC"]]].median().round(1))


def section_rq3_aggregate(df):
    hr("RQ3 -- Descriptive aggregate coverage score")
    print(df.groupby("algorithm")["aggregate"].agg(["mean", "median", "std"]).round(2))
    kruskal_and_dunn(df, "aggregate", "aggregate score")


def main():
    df = load_canonical()
    section_shapiro(df)
    section_rq1_test_suite_size(df)
    section_rq1_real_time()
    section_minimization()
    section_rq2_correlation(df)
    section_rq3_per_criterion(df)
    section_rq3_aggregate(df)
    hr("Done -- compare the numbers above against the paper's tables/text.")


if __name__ == "__main__":
    main()
