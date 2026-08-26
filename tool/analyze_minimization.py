"""Extracts EvoMaster's per-execution minimization-phase statistics from the
raw console logs in results/official-run/repetition_*/{RANDOM,WTS,SMARTS}/execution_output.txt,
supporting the minimization-phase analysis reported in Section 5.1.2 of the paper.

Usage: run from the replication-package root:
    python tool/analyze_minimization.py

Writes results/statistics/minimization_analysis.csv.
"""
import csv
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "results" / "official-run"
OUT = Path(__file__).resolve().parent.parent / "results" / "statistics" / "minimization_analysis.csv"


def extract(log_text):
    m_raw = re.search(r"Recomputing full coverage for (\d+) tests", log_text)
    m_candidates = re.search(r"Analyzing (\d+) tests with size greater than 1", log_text)
    m_timeout = "Minimization phase has timed-out" in log_text
    m_duration = re.search(r"Minimization phase took (\d+) seconds", log_text)
    m_saved = re.search(r"Going to save (\d+) tests", log_text)
    return {
        "raw_tests": int(m_raw.group(1)) if m_raw else None,
        "candidates_gt1": int(m_candidates.group(1)) if m_candidates else None,
        "timed_out": m_timeout,
        "minim_seconds": int(m_duration.group(1)) if m_duration else None,
        "final_tests": int(m_saved.group(1)) if m_saved else None,
    }


def main():
    rows = []
    for rep_dir in sorted(BASE.glob("repetition_*")):
        rep = int(rep_dir.name.split("_")[1])
        for algo_dir in rep_dir.iterdir():
            if not algo_dir.is_dir() or algo_dir.name == "criteria":
                continue
            log = algo_dir / "execution_output.txt"
            if not log.exists():
                continue
            row = {"algorithm": algo_dir.name, "repetition": rep}
            row.update(extract(log.read_text(errors="ignore")))
            rows.append(row)

    rows.sort(key=lambda r: (r["repetition"], r["algorithm"]))
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
