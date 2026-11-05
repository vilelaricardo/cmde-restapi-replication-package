"""The fictitious records of the local database (generate_synthetic_data.py)."""
import pytest

from generate_synthetic_data import (N_CHANGE_REQUESTS, N_PROFESSIONALS, N_STUDENTS, N_VALIDATIONS, build_tables,
                                     is_valid_cpf, is_valid_nis, to_sql)


@pytest.fixture(scope='module')
def tables():
    return build_tables()


def column(tables, table, name):
    position = tables[table]['columns'].index(name)
    return [row[position] for row in tables[table]['rows']]


def test_the_check_digit_functions_follow_the_api():
    assert is_valid_cpf('52998224725')
    assert not is_valid_cpf('52998224726')
    assert not is_valid_cpf('11111111111')
    assert is_valid_nis('12056412545')
    assert not is_valid_nis('12056412546')


def test_the_same_seed_gives_the_same_records():
    assert to_sql(build_tables(seed=1)) == to_sql(build_tables(seed=1))
    assert to_sql(build_tables(seed=1)) != to_sql(build_tables(seed=2))


def test_volumes(tables):
    assert len(tables['pessoa.tb_pessoa']['rows']) == N_STUDENTS + N_PROFESSIONALS
    assert len(tables['pessoa.tb_estudante']['rows']) == N_STUDENTS
    assert len(tables['pessoa.tb_profissional_educacao']['rows']) == N_PROFESSIONALS
    assert len(tables['pessoa.tb_validacao_cadastro']['rows']) == N_VALIDATIONS
    assert len(tables['pessoa.tb_edicao_pessoa']['rows']) == N_CHANGE_REQUESTS


def test_no_cpf_can_belong_to_a_real_person(tables):
    cpfs = (column(tables, 'pessoa.tb_pessoa', 'nu_cpf')
            + [c for c in column(tables, 'pessoa.tb_estudante', 'nu_cpf_responsavel') if c]
            + column(tables, 'pessoa.tb_edicao_pessoa', 'nu_cpf_novo'))
    assert all(len(c) == 11 and c.isdigit() and not is_valid_cpf(c) for c in cpfs)


def test_no_nis_can_belong_to_a_real_person(tables):
    numbers = ([n for n in column(tables, 'pessoa.tb_complemento_cadastro', 'nu_nis') if n]
               + [n for n in column(tables, 'pessoa.tb_estudante', 'nu_nis_responsavel') if n])
    assert numbers and all(len(n) == 11 and n.isdigit() and not is_valid_nis(n) for n in numbers)


def test_contacts_cannot_reach_anyone(tables):
    phones = [p for p in column(tables, 'pessoa.tb_pessoa', 'nu_telefone') if p]
    emails = [e for e in column(tables, 'pessoa.tb_pessoa', 'ds_email') if e]
    assert phones and all(p.startswith('00') and len(p) == 11 for p in phones)
    assert emails and all(e.endswith('.invalid') for e in emails)


def test_values_that_the_database_requires_to_be_unique_are_unique(tables):
    for table, name in [('pessoa.tb_pessoa', 'nu_cpf'), ('pessoa.tb_complemento_cadastro', 'nu_nis'),
                        ('pessoa.tb_validacao_cadastro', 'co_pessoa')]:
        values = [v for v in column(tables, table, name) if v is not None]
        assert len(values) == len(set(values)), (table, name)


def test_gender_and_sex_use_the_codes_of_their_own_tables(tables):
    assert set(column(tables, 'pessoa.tb_pessoa', 'co_genero')) <= set(range(10))
    assert set(column(tables, 'pessoa.tb_pessoa', 'co_sexo')) <= set(range(5))


def test_every_enrollment_has_a_series_because_the_api_requires_one(tables):
    assert all(s is not None for s in column(tables, 'academico.tb_matricula', 'co_serie_ano'))


def test_enrollments_are_unique_per_person_school_series_and_year(tables):
    rows = list(zip(*(column(tables, 'academico.tb_matricula', c)
                      for c in ['co_pessoa', 'co_instituicao', 'co_serie_ano', 'nu_ano_matricula'])))
    assert len(rows) == len(set(rows))


def test_records_exercise_the_filters_of_the_api(tables):
    active = column(tables, 'academico.tb_matricula', 'st_matricula_ativa')
    reasons = set(column(tables, 'academico.tb_matricula', 'co_tipo_justificativa_desmatricula'))
    assert True in active and False in active
    assert {10, 12} <= reasons  # situacao_final APROVADAS and REPROVADAS
    assert {2024, 2025, 2026} <= set(column(tables, 'academico.tb_matricula', 'nu_ano_matricula'))


def test_some_students_are_also_enrolled_in_another_network(tables):
    from generate_synthetic_data import OTHER_NETWORK_SCHOOLS
    schools = set(column(tables, 'academico.tb_matricula', 'co_instituicao'))
    assert schools & set(OTHER_NETWORK_SCHOOLS)


def test_sql_quotes_values_and_writes_nulls():
    sql = to_sql({'s.t': {'columns': ['a', 'b', 'c', 'd'], 'rows': [["O'Neil", None, 3, True]]}})
    assert "INSERT INTO s.t (a, b, c, d) VALUES\n('O''Neil', NULL, 3, TRUE);" in sql


def test_sequences_continue_after_the_records(tables):
    sql = to_sql(tables)
    assert f"setval('pessoa.tb_pessoa_co_pessoa_seq', {N_STUDENTS + N_PROFESSIONALS})" in sql


def test_nothing_depends_on_the_day_it_runs(tables):
    assert 'now()' not in to_sql(tables).lower()
