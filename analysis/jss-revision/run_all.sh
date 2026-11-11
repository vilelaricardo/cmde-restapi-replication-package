#!/bin/sh
# Runs every analysis of the revised evaluation in dependency order, writing the printed results to
# output/. Set CMDE_DATA to the directory holding official-6.2.0/ and low-budget-6.2.0/ (default:
# ../../tool/data_generated) and PYTHON to the interpreter (default: python3).
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
mkdir -p data output cache
$PY recompute_2025.py                         > output/recompute_2025.txt
$PY main_campaign.py                          > output/main_campaign.txt
$PY element_allocation.py                     > output/element_allocation.txt
$PY rq1_suite_size.py                         > output/rq1_suite_size.txt
$PY block_sensitivity.py runs_main.csv        > output/block_sensitivity_main.txt
$PY rbpc_assertions.py                        > output/rbpc_assertions.txt
$PY inep_search.py                            > output/inep_search.txt
$PY inep_lists.py                             > output/inep_lists.txt
$PY rbpc_sensitivity.py                       > output/rbpc_sensitivity.txt
$PY rbpc_differences.py                       > output/rbpc_differences.txt
$PY low_budget.py                             > output/low_budget.txt
$PY block_sensitivity.py runs_low_budget.csv  > output/block_sensitivity_low_budget.txt
$PY rpvc_post_low_budget.py                   > output/rpvc_post_low_budget.txt
$PY excluded_operations.py                    > output/excluded_operations.txt
$PY coverage_figure.py                        > output/coverage_figure.txt
echo done
