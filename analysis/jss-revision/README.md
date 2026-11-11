# Analysis of the revised evaluation

Scripts that produce every number, table, and figure of the revised evaluation reported in the
paper: the main campaign (four EvoMaster 6.2.0 techniques, 30 blocks, local deployment with
fictitious data), the complementary low-budget campaign (10 blocks, 20 requests per minute), and the
recomputation of the 2025 study with the corrected measurement tool. The analysis of the first
submission is in `../compute_statistics.py` and `../generate_figures.py`.

## Requirements

- Python 3.12 (run with 3.12.13).
- pandas 3.0.3, numpy 2.4.6, scipy 1.18.0, scikit-posthocs 0.14.0 (which imports statsmodels;
  0.14.4 was used), matplotlib 3.11.2.
- The measurement tool in `../../tool/` (used by `recompute_2025.py`).

## Data

The scripts read the raw data of the two campaigns from `CMDE_DATA`, a directory that holds
`official-6.2.0/` (main campaign) and `low-budget-6.2.0/`. By default this is
`../../tool/data_generated/`, where the campaign runner writes them; to use the archived data,
extract the data archives and point `CMDE_DATA` to the directory that contains both folders. In the
archived data the API key is replaced by a placeholder; no analysis reads it. The 2025 study is read
from `../../results/official-run/` and the archived OpenAPI specification from
`../../results/official-run/api-docs.json`.

## How to run

```sh
CMDE_DATA=/path/to/data PYTHON=python3 ./run_all.sh
```

`run_all.sh` runs the scripts in dependency order (about two minutes) and writes their printed
results to `output/`. Derived tables go to `data/`; `cache/` holds intermediate files
(`run2025/`, the recomputed copy of the 2025 study, and `elements_allocation.pkl`) and is not
versioned. Each script can also be run on its own once the files it reads exist. The bootstrap
confidence intervals of A12 use a fixed seed (20261108) and are reproduced when each script runs as
a separate process, as in `run_all.sh`.

## Scripts and where their results appear in the paper

| Order | Script | Writes | Paper |
|---|---|---|---|
| 1 | `recompute_2025.py` | `data/coverage_2025.csv`, `cache/run2025/` | Sec. 4.2, the initial study recomputed with the corrected tool; the 2025 values compared in Sec. 5.4 and 5.5 |
| 2 | `main_campaign.py` | `data/runs_main.csv`, `cache/elements_allocation.pkl` | Opening of Sec. 5 (integrity of the 120 executions); Sec. 5.1 (tests, HTTP calls, replay time, search requests); Sec. 5.2 (Spearman table); Sec. 5.3 (coverage and A12 tables); comparison with the recomputed 2025 study (Sec. 4.2) |
| 3 | `element_allocation.py` | `data/elements_<criterion>.csv` | Sec. 5.3 and 5.4: elements covered per technique, allocation of the search requests per operation and HTTP method |
| 4 | `rq1_suite_size.py` | `data/rq1_suite_size.csv` | Sec. 5.1, RQ1 table (lines of code, assertions, block-aware check); definitions in Sec. 4.8 |
| 5 | `block_sensitivity.py` | — | Sec. 4.10, the block-aware sensitivity analysis (Friedman and pairwise Wilcoxon); marked pairs of the A12 table in Sec. 5.3; Sec. 5.5 (run with `runs_low_budget.csv`) |
| 6 | `rbpc_assertions.py` | `data/rbpc_assertions.csv` | Sec. 5.4, list operations: item properties are covered only when a kept test read a non-empty list (main campaign and 2025) |
| 7 | `inep_search.py` | `data/inep_search.csv` | Sec. 5.4 and 5.5, calls to the `/inep/{inep}` lists during the search |
| 8 | `inep_lists.py` | — | Sec. 5.4, list lengths behind MIO's coverage of the `/inep/{inep}` lists |
| 9 | `rbpc_sensitivity.py` | `data/rbpc_sensitivity.csv` | Sec. 5.4, RBPC computed from the responses of the re-executed suites and decomposition by list groups; Sec. 7, construct validity |
| 10 | `rbpc_differences.py` | — | Sec. 5.4, properties covered during the search but not observed in the re-execution (batch-error responses) |
| 11 | `low_budget.py` | `data/runs_low_budget.csv` | Sec. 5.5, the low-budget table and text (integrity, comparison among techniques, paired comparison with the main campaign, comparison with 2025, list operations) |
| 12 | `rpvc_post_low_budget.py` | — | Sec. 5.4 (POST calls and RPVC) and Sec. 5.5 (RPVC and POST calls at low budget) |
| 13 | `excluded_operations.py` | — | Sec. 4.5, static analysis of whether the findings of Sec. 5.6 can occur in the 39 excluded operations |
| 14 | `coverage_figure.py` | `output/fig-coverage-2026.pdf` and `.png` | Sec. 5.3, the coverage figure |

Section numbers refer to the revised manuscript.
