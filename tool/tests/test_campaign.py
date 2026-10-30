"""Planning and bookkeeping of an experiment campaign (campaign.py). The parts that drive
Docker and EvoMaster are exercised by the pilot runs."""
import json

import pytest

from campaign import (check_options_not_repeated, evomaster_command, evomaster_summary, load_or_create_plan,
                      make_plan, pending_runs, run_directory, seconds_of, set_aside, stop_requested,
                      unittest_summary)

ALGORITHMS = ['MIO', 'RANDOM', 'SMARTS', 'WTS']


def test_each_block_runs_every_technique_once():
    plan = make_plan(ALGORITHMS, 30, seed=7)
    assert len(plan) == 120
    for block in range(30):
        runs = [r for r in plan if r['block'] == block]
        assert sorted(r['algorithm'] for r in runs) == sorted(ALGORITHMS)
        assert [r['position'] for r in runs] == [0, 1, 2, 3]


def test_blocks_follow_each_other_so_stopping_between_them_keeps_techniques_balanced():
    plan = make_plan(ALGORITHMS, 5, seed=7)
    assert [r['block'] for r in plan] == sorted(r['block'] for r in plan)


def test_order_within_blocks_is_drawn_from_the_seed():
    plan = make_plan(ALGORITHMS, 30, seed=7)
    orders = {tuple(r['algorithm'] for r in plan if r['block'] == block) for block in range(30)}
    assert len(orders) > 1
    assert make_plan(ALGORITHMS, 30, seed=7) == plan
    assert make_plan(ALGORITHMS, 30, seed=8) != plan


def test_every_execution_has_its_own_seed():
    seeds = [r['seed'] for r in make_plan(ALGORITHMS, 30, seed=7)]
    assert len(set(seeds)) == len(seeds)
    assert all(seed > 0 for seed in seeds)


def test_saved_plan_is_reused(tmp_path):
    plan = load_or_create_plan(tmp_path, ALGORITHMS, 3, 7)
    assert json.loads((tmp_path / 'plan.json').read_text()) == plan
    assert load_or_create_plan(tmp_path, ALGORITHMS, 3, 7) == plan


def test_saved_plan_made_with_other_settings_is_refused(tmp_path):
    load_or_create_plan(tmp_path, ALGORITHMS, 3, 7)
    with pytest.raises(ValueError):
        load_or_create_plan(tmp_path, ALGORITHMS, 3, 8)


def leave(tmp_path, run, status):
    directory = run_directory(tmp_path, run)
    directory.mkdir(parents=True)
    (directory / 'run.json').write_text(json.dumps({**run, 'status': status}))


def test_finished_executions_are_skipped_on_resume(tmp_path):
    plan = make_plan(ALGORITHMS, 2, seed=7)
    leave(tmp_path, plan[0], 'done')
    leave(tmp_path, plan[1], 'failed')
    leave(tmp_path, plan[2], 'running')
    assert pending_runs(plan, tmp_path) == plan[1:]


def test_unfinished_execution_is_set_aside(tmp_path):
    run = make_plan(ALGORITHMS, 1, seed=7)[0]
    leave(tmp_path, run, 'running')
    moved = set_aside(run_directory(tmp_path, run), tmp_path)
    assert not run_directory(tmp_path, run).exists()
    assert moved.parent == tmp_path / 'incomplete'
    assert (moved / 'run.json').exists()


def test_layout_is_the_one_the_statistics_script_reads(tmp_path):
    run = {'block': 3, 'position': 1, 'algorithm': 'WTS', 'seed': 1}
    assert run_directory(tmp_path, run) == tmp_path / 'repetition_3' / 'WTS'


def test_stop_file_ends_the_campaign_only_between_blocks(tmp_path):
    plan = make_plan(ALGORITHMS, 2, seed=7)
    assert not stop_requested(tmp_path, plan[4])
    (tmp_path / 'STOP').touch()
    assert not stop_requested(tmp_path, plan[1])
    assert stop_requested(tmp_path, plan[4])


def test_evomaster_command(tmp_path):
    run = {'block': 0, 'position': 0, 'algorithm': 'MIO', 'seed': 42}
    command = evomaster_command('java', 'evomaster.jar', 'em.yaml',
                                {'maxTime': '30m', 'ratePerMinute': 0, 'minimize': False}, run, tmp_path)
    assert command[:5] == ['java', '-jar', 'evomaster.jar', '--configPath', 'em.yaml']
    assert dict(zip(command[5::2], command[6::2])) == {
        '--maxTime': '30m', '--ratePerMinute': '0', '--minimize': 'false', '--algorithm': 'MIO', '--seed': '42',
        '--outputFolder': str(tmp_path / 'generated_tests'),
        '--statisticsFile': str(tmp_path / 'statistics.csv'),
        '--coveredTargetFile': str(tmp_path / 'covered_targets.txt')}


def test_an_option_is_set_in_one_file_only():
    with pytest.raises(ValueError, match='maxTime'):
        check_options_not_repeated({'maxTime': '30m', 'header0': 'x-api-key: k'}, {'maxTime': '30m'})
    check_options_not_repeated({'header0': 'x-api-key: k'}, {'maxTime': '30m'})


@pytest.mark.parametrize('text, seconds', [('30m', 1800), ('60s', 60), ('1h30m', 5400), ('2m', 120)])
def test_search_budget_in_seconds(text, seconds):
    assert seconds_of(text) == seconds


def test_evomaster_summary():
    output = '* Evaluated tests: 209\n* Evaluated actions: 1130\n* \x1b[34mGoing to save 98 tests to /x\x1b[0m\n'
    assert evomaster_summary(output) == {'evaluated_tests': 209, 'evaluated_actions': 1130, 'saved_tests': 98}


def test_unittest_summary():
    assert unittest_summary('test_0 ... ok\nRan 12 tests in 3.201s\n\nFAILED (failures=2, errors=1)\n') == {
        'tests_run': 12, 'failures': 2, 'errors': 1}
    assert unittest_summary('Ran 1 test in 0.100s\n\nOK\n') == {'tests_run': 1, 'failures': 0, 'errors': 0}
