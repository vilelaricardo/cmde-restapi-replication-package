"""Generates the fictitious records of the database used in the re-execution.

The local database is created from the structure of the CMDE database and from its domain
tables, without any record of a person. With no records, every list comes back empty and
the operations that look up one record never answer 200, so the responses the study
analyzes are not observed. This script writes the SQL that fills those tables. It runs
after the domain data and before the materialized views are refreshed.

Nothing here can belong to a real person:
  - CPFs and NISs have a wrong check digit on purpose, so they cannot have been issued;
  - telephone numbers use area code 00, which does not exist;
  - e-mail addresses use the .invalid domain, reserved by RFC 2606;
  - addresses are invented, and names are random combinations of common names.

Volumes follow the database of the original study, as recorded in the pagination totals
of the tests generated in 2025. It held 598,780 students of the network of the API key, of
which 54,714 (9.1%) had a registration validation, 72 change requests and 3 professionals.
Students are scaled down to 5,000, which keeps the time of a request close to that of the
rest of the API, and validations follow them; the two small counts are kept as they were.
The other proportions (optional fields, inactive enrollments) are choices of this script.

Usage: python generate_synthetic_data.py --output 02-z-dados-sinteticos.sql
(The name matters: Postgres runs its init files in the order of its locale, which ignores
hyphens, so a name such as 02b-... would run before 02-data.sql.)
"""
import argparse
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20261104
N_STUDENTS = 5000
N_VALIDATIONS = 457
N_CHANGE_REQUESTS = 72
N_PROFESSIONALS = 3

NETWORK = 2  # the network of the API key: its state education department (Acre)
STATE = 12
MUNICIPALITIES = [1200013, 1200054, 1200104, 1200138, 1200179, 1200203, 1200252, 1200302]
SCHOOLS = [(7014, '12000094'), (7015, '12000108'), (7019, '12000159'), (7020, '12000167'), (7024, '12000256'),
           (7025, '12000264'), (7027, '12000280'), (7029, '12000345'), (7030, '12000370'), (7032, '12000400'),
           (7033, '12000418'), (7034, '12000442'), (7035, '12000450'), (7036, '12000469'), (7037, '12000507'),
           (7038, '12000531'), (7044, '12000612'), (7047, '12000663'), (7049, '12000701'), (7050, '12000736'),
           (7052, '12000779'), (7053, '12000787'), (7057, '12000841'), (7059, '12000876'), (7061, '12000906')]
OTHER_NETWORK_SCHOOLS = [149003, 149004, 149005, 149006, 149007]  # network 20

REGULAR_SERIES = [14, 15, 16, 17, 18, 19, 20, 21, 25, 26, 27, 28]
ADULT_EDUCATION_SERIES = [45, 48, 69, 70]
LAST_YEARS_OF_HIGH_SCHOOL = {27, 28, 45, 48}
APPROVED, FAILED = 10, 12  # co_tipo_justificativa_desmatricula read by the situacao_final filter
OTHER_REASONS = [2, 3]

P_EMAIL = 0.7
P_PHONE = 0.7
P_SOCIAL_NAME = 0.02
P_NIS = 0.8
P_RG = 0.8
P_CNH = 0.03
P_BIRTH_CERTIFICATE = 0.6
P_GUARDIAN = 0.8
P_ADDRESS_COMPLEMENT = 0.3
P_DISABILITY = 0.05
P_ADULT_EDUCATION = 0.05
P_INACTIVE = 0.15
P_PREVIOUS_YEAR = 0.25
P_APPROVED = 0.8
P_OTHER_NETWORK = 0.02
P_FULL_TIME = 0.2

FIRST_NAMES_F = ['Ana', 'Beatriz', 'Camila', 'Daniela', 'Eduarda', 'Fernanda', 'Gabriela', 'Helena', 'Isabela',
                 'Julia', 'Larissa', 'Mariana', 'Natalia', 'Patricia', 'Rafaela', 'Sofia', 'Tatiana', 'Vitoria']
FIRST_NAMES_M = ['Arthur', 'Bruno', 'Caio', 'Daniel', 'Eduardo', 'Felipe', 'Gabriel', 'Henrique', 'Igor',
                 'Joao', 'Lucas', 'Matheus', 'Nicolas', 'Otavio', 'Pedro', 'Rafael', 'Samuel', 'Thiago']
SURNAMES = ['Almeida', 'Araujo', 'Barbosa', 'Cardoso', 'Carvalho', 'Costa', 'Dias', 'Ferreira', 'Freitas', 'Gomes',
            'Lima', 'Martins', 'Melo', 'Mendes', 'Moreira', 'Nascimento', 'Nunes', 'Oliveira', 'Pereira', 'Ribeiro',
            'Rocha', 'Rodrigues', 'Santos', 'Silva', 'Souza', 'Teixeira', 'Vieira']

TIMESTAMP = '2026-03-02 08:00:00'
CHUNK = 500

SEQUENCES = {
    'endereco.tb_endereco': 'endereco.tb_endereco_co_endereco_seq',
    'pessoa.tb_pessoa': 'pessoa.tb_pessoa_co_pessoa_seq',
    'pessoa.tb_pessoa_tipo_deficiencia': 'pessoa.tb_pessoa_tipo_deficiencia_co_pessoa_tipo_deficiencia_seq',
    'academico.tb_matricula': 'academico.tb_matricula_co_matricula_seq',
    'pessoa.tb_validacao_cadastro': 'pessoa.tb_validacao_cadastro_co_validacao_cadastro_seq',
    'pessoa.tb_edicao_pessoa': 'pessoa.tb_edicao_pessoa_co_edicao_pessoa_seq',
    'funcao.tb_profissional_educacao_funcao': 'funcao.tb_profissional_educacao_func_co_profissional_educacao_func_seq',
    'formacao.tb_profissional_educacao_formacao_academica':
        'formacao.tb_profissional_educacao_form_co_profissional_educacao_form_seq',
}


def cpf_check_digit(digits):
    total = sum(int(d) * (len(digits) + 1 - i) for i, d in enumerate(digits))
    return (10 * total) % 11 % 10


def is_valid_cpf(cpf):
    """Misc::validaCpf of the API."""
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False
    return cpf_check_digit(cpf[:9]) == int(cpf[9]) and cpf_check_digit(cpf[:10]) == int(cpf[10])


def nis_check_digit(digits):
    weights = [3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    digit = 11 - sum(w * int(d) for w, d in zip(weights, digits)) % 11
    return 0 if digit in (10, 11) else digit


def is_valid_nis(nis):
    """Misc::validaNIS of the API."""
    return len(nis) == 11 and nis.isdigit() and nis_check_digit(nis[:10]) == int(nis[10])


class Generator:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.used = set()

    def digits(self, length):
        return ''.join(self.rng.choice('0123456789') for _ in range(length))

    def unique(self, make):
        while True:
            value = make()
            if value not in self.used:
                self.used.add(value)
                return value

    def fictitious_cpf(self):
        def make():
            base = self.digits(9)
            first = cpf_check_digit(base)
            second = cpf_check_digit(base + str(first))
            return f'{base}{first}{(second + 1) % 10}'
        return self.unique(make)

    def fictitious_nis(self):
        def make():
            base = self.digits(10)
            return f'{base}{(nis_check_digit(base) + 1) % 10}'
        return self.unique(make)

    def phone(self):
        return '00' + '9' + self.digits(8)

    def maybe(self, probability, make):
        return make() if self.rng.random() < probability else None

    def surnames(self):
        return f'{self.rng.choice(SURNAMES)} {self.rng.choice(SURNAMES)}'

    def name(self, gender):
        first = FIRST_NAMES_F if gender == 2 else FIRST_NAMES_M
        return f'{self.rng.choice(first)} {self.surnames()}'

    def date_between(self, start, end):
        return (start + timedelta(days=self.rng.randint(0, (end - start).days))).isoformat()

    def person_columns(self, person_id, gender, birth_start, birth_end, name, status=1):
        slug = name.lower().replace(' ', '.')
        return [person_id, self.fictitious_cpf(), name, self.date_between(birth_start, birth_end), gender,
                self.rng.randint(0, 5), person_id,
                self.maybe(P_EMAIL, lambda: f'{slug}.{person_id}@exemplo.invalid'),
                self.maybe(P_PHONE, self.phone), status,
                self.maybe(P_SOCIAL_NAME, lambda: self.name(gender)), gender if gender in (1, 2) else 0,
                TIMESTAMP, TIMESTAMP]

    def address_row(self, address_id):
        return [address_id, f'Rua Ficticia {self.rng.randint(1, 400)}', f'Bairro Ficticio {self.rng.randint(1, 60)}',
                self.maybe(P_ADDRESS_COMPLEMENT, lambda: f'Casa {self.rng.randint(1, 9)}'),
                str(self.rng.randint(1, 3000)), f'699{self.digits(5)}', self.rng.choice(MUNICIPALITIES), STATE,
                TIMESTAMP, TIMESTAMP]

    def gender(self):
        return self.rng.choices([1, 2, 0, 3, 8], weights=[47, 47, 3, 1, 2])[0]


def table(*columns):
    return {'columns': list(columns), 'rows': []}


def enrollment(gen, matricula_id, person_id, school, series, year, active, reason):
    is_adult_education = series in ADULT_EDUCATION_SERIES
    started = date(year, 2, 1)
    certificate = gen.date_between(date(year, 12, 1), date(year, 12, 20)) \
        if reason == APPROVED and series in LAST_YEARS_OF_HIGH_SCHOOL else None
    return [matricula_id, person_id, school, gen.date_between(started, started + timedelta(days=40)),
            None if active else gen.date_between(date(year, 11, 1), date(year, 12, 20)),
            active, TIMESTAMP, TIMESTAMP, series, reason, f'MAT-{matricula_id:07d}', certificate,
            started.isoformat(), gen.rng.randint(1, 6), gen.rng.randint(1, 4),
            gen.rng.randint(1, 4) if is_adult_education else None,
            gen.rng.random() < P_FULL_TIME, 0, f'{year}-02-15 08:00:00', year]


def build_students(gen, tables):
    validated = set(gen.rng.sample(range(1, N_STUDENTS + 1), N_VALIDATIONS))
    matricula_id = 0
    deficiency_id = 0
    for person_id in range(1, N_STUDENTS + 1):
        gender = gen.gender()
        tables['endereco.tb_endereco']['rows'].append(gen.address_row(person_id))
        status = gen.rng.choice([2, 3]) if person_id in validated else 1
        tables['pessoa.tb_pessoa']['rows'].append(
            gen.person_columns(person_id, gender, date(2006, 1, 1), date(2019, 12, 31), gen.name(gender), status))
        school = gen.rng.choice(SCHOOLS)[0]
        has_guardian = gen.rng.random() < P_GUARDIAN
        tables['pessoa.tb_estudante']['rows'].append(
            [person_id, gen.fictitious_cpf() if has_guardian else None, gen.fictitious_nis() if has_guardian else None,
             gen.name(2), TIMESTAMP, TIMESTAMP, school, f'EST-{person_id:07d}'])
        has_rg = gen.rng.random() < P_RG
        tables['pessoa.tb_complemento_cadastro']['rows'].append(
            [person_id, gen.digits(9) if has_rg else None, 'SSP/AC' if has_rg else None,
             gen.maybe(P_CNH, lambda: gen.digits(11)), gen.maybe(P_BIRTH_CERTIFICATE, lambda: gen.digits(32)),
             gen.maybe(P_NIS, gen.fictitious_nis), TIMESTAMP, TIMESTAMP])
        if gen.rng.random() < P_DISABILITY:
            deficiency_id += 1
            tables['pessoa.tb_pessoa_tipo_deficiencia']['rows'].append(
                [deficiency_id, person_id, gen.rng.randint(1, 10), TIMESTAMP, TIMESTAMP])

        adult = gen.rng.random() < P_ADULT_EDUCATION
        series = gen.rng.choice(ADULT_EDUCATION_SERIES if adult else REGULAR_SERIES)
        year = gen.rng.choices([2024, 2025, 2026], weights=[2, 4, 4])[0]
        active = gen.rng.random() >= P_INACTIVE
        reason = None if active else gen.rng.choice([APPROVED, FAILED, *OTHER_REASONS])
        matricula_id += 1
        tables['academico.tb_matricula']['rows'].append(
            enrollment(gen, matricula_id, person_id, school, series, year, active, reason))
        if gen.rng.random() < P_PREVIOUS_YEAR:
            matricula_id += 1
            previous = APPROVED if gen.rng.random() < P_APPROVED else FAILED
            tables['academico.tb_matricula']['rows'].append(
                enrollment(gen, matricula_id, person_id, school, series, year - 1, False, previous))
        if gen.rng.random() < P_OTHER_NETWORK:
            matricula_id += 1
            tables['academico.tb_matricula']['rows'].append(
                enrollment(gen, matricula_id, person_id, gen.rng.choice(OTHER_NETWORK_SCHOOLS), series, year, True, None))
    return sorted(validated)


def build_validations(gen, tables, validated):
    people = {row[0]: row for row in tables['pessoa.tb_pessoa']['rows']}
    mothers = {row[0]: row[3] for row in tables['pessoa.tb_estudante']['rows']}
    for validation_id, person_id in enumerate(validated, start=1):
        person = people[person_id]
        tables['pessoa.tb_validacao_cadastro']['rows'].append(
            [validation_id, person_id, gen.rng.random() < 0.9, gen.rng.random() < 0.9, gen.rng.random() < 0.9,
             gen.rng.choice([0, 0, 0, 0, 2, 3, 4, 5, 8, 9, 10]), f'2026-02-{gen.rng.randint(1, 28):02d} 10:00:00',
             TIMESTAMP, TIMESTAMP, round(gen.rng.uniform(60, 100), 2), round(gen.rng.uniform(60, 100), 2),
             person[2], person[3], mothers[person_id]])


def build_change_requests(gen, tables):
    people = {row[0]: row for row in tables['pessoa.tb_pessoa']['rows']}
    mothers = {row[0]: row[3] for row in tables['pessoa.tb_estudante']['rows']}
    chosen = gen.rng.sample(range(1, N_STUDENTS + 1), N_CHANGE_REQUESTS)
    for request_id, person_id in enumerate(sorted(chosen), start=1):
        person = people[person_id]
        gender = person[4]
        new_cpf = gen.fictitious_cpf()
        new_name = gen.name(gender)
        new_mother = gen.name(2)
        birth = gen.date_between(date(2006, 1, 1), date(2019, 12, 31))
        tables['pessoa.tb_edicao_pessoa']['rows'].append(
            [request_id, person_id, person[1], new_cpf, new_cpf, person[2], new_name, new_name, person[3], birth, birth,
             mothers[person_id], new_mother, new_mother, TIMESTAMP, TIMESTAMP,
             f'2026-02-{gen.rng.randint(1, 28):02d} 10:00:00', gen.rng.choice([0, 0, 0, 2, 3, 4, 5, 8, 9, 10]),
             gen.rng.randint(1, 4), gen.rng.random() < 0.9, gen.rng.random() < 0.9, gen.rng.random() < 0.9,
             round(gen.rng.uniform(60, 100), 2), round(gen.rng.uniform(60, 100), 2), NETWORK])


def build_professionals(gen, tables):
    deficiency_id = len(tables['pessoa.tb_pessoa_tipo_deficiencia']['rows'])
    for offset in range(N_PROFESSIONALS):
        number = offset + 1
        person_id = N_STUDENTS + number
        gender = gen.rng.choice([1, 2])
        school = SCHOOLS[offset * 8][0]
        tables['endereco.tb_endereco']['rows'].append(gen.address_row(person_id))
        tables['pessoa.tb_pessoa']['rows'].append(
            gen.person_columns(person_id, gender, date(1965, 1, 1), date(1998, 12, 31), gen.name(gender)))
        tables['pessoa.tb_profissional_educacao']['rows'].append(
            [person_id, TIMESTAMP, TIMESTAMP, gen.rng.randint(1, 4), gen.rng.randint(5, 10)])
        tables['funcao.tb_profissional_educacao_funcao']['rows'].append(
            [number, person_id, school, gen.rng.choice([20, 30, 40]), number != 2, TIMESTAMP, TIMESTAMP,
             '2020-02-03', '2025-12-19' if number == 2 else None, 1 if number != 2 else 2, gen.rng.randint(1, 3),
             f'PROF-{number:04d}', gen.rng.randint(1, 5)])
        tables['formacao.tb_profissional_educacao_formacao_academica']['rows'].append(
            [number, person_id, 'Universidade Ficticia', 2010 + number, 2014 + number, gen.rng.randint(1, 10), True,
             TIMESTAMP, TIMESTAMP, gen.rng.randint(1, 8)])
        if number == 3:
            deficiency_id += 1
            tables['pessoa.tb_pessoa_tipo_deficiencia']['rows'].append(
                [deficiency_id, person_id, gen.rng.randint(1, 10), TIMESTAMP, TIMESTAMP])


def build_tables(seed=SEED):
    gen = Generator(seed)
    tables = {
        'endereco.tb_endereco': table('co_endereco', 'no_logradouro', 'no_bairro', 'ds_complemento_endereco',
                                      'nu_endereco', 'nu_cep', 'co_municipio', 'co_uf', 'created_at', 'updated_at'),
        'pessoa.tb_pessoa': table('co_pessoa', 'nu_cpf', 'no_pessoa', 'dt_nascimento', 'co_genero', 'co_etnia',
                                  'co_endereco', 'ds_email', 'nu_telefone', 'st_cadastro_validado', 'no_social',
                                  'co_sexo', 'created_at', 'updated_at'),
        'pessoa.tb_estudante': table('co_pessoa', 'nu_cpf_responsavel', 'nu_nis_responsavel', 'no_mae', 'created_at',
                                     'updated_at', 'co_instituicao', 'co_estudante_rede'),
        'pessoa.tb_complemento_cadastro': table('co_pessoa', 'nu_rg', 'no_orgao_emissor_rg', 'nu_cnh',
                                                'nu_certidao_nascimento', 'nu_nis', 'created_at', 'updated_at'),
        'pessoa.tb_profissional_educacao': table('co_pessoa', 'created_at', 'updated_at',
                                                 'co_tipo_ensino_medio_formacao', 'co_nivel_escolaridade_profissional'),
        'pessoa.tb_pessoa_tipo_deficiencia': table('co_pessoa_tipo_deficiencia', 'co_pessoa', 'co_tipo_deficiencia',
                                                   'created_at', 'updated_at'),
        'academico.tb_matricula': table('co_matricula', 'co_pessoa', 'co_instituicao', 'dt_inicio', 'dt_fim',
                                        'st_matricula_ativa', 'created_at', 'updated_at', 'co_serie_ano',
                                        'co_tipo_justificativa_desmatricula', 'co_matricula_rede',
                                        'dt_emissao_certificado', 'dt_inicio_periodo_letivo',
                                        'co_forma_oraganizacao_turma', 'nu_turma_organizacao_quantidade_total',
                                        'nu_estudante_eja_ano_periodo', 'fl_estudante_integral',
                                        'co_local_prisional_socioeducativo', 'dt_ativacao', 'nu_ano_matricula'),
        'pessoa.tb_validacao_cadastro': table('co_validacao_cadastro', 'co_pessoa', 'fl_no_pessoa_validado',
                                              'fl_dt_nascimento_validado', 'fl_no_mae_validado', 'st_situacao_cpf',
                                              'dt_validacao_cadastral', 'created_at', 'updated_at',
                                              'vl_rate_no_pessoa_validado', 'vl_rate_no_mae_validado',
                                              'no_pessoa_receita', 'dt_nascimento_receita', 'no_mae_receita'),
        'pessoa.tb_edicao_pessoa': table('co_edicao_pessoa', 'co_pessoa', 'nu_cpf_atual', 'nu_cpf_novo',
                                         'nu_cpf_receita', 'no_pessoa_atual', 'no_pessoa_novo', 'no_pessoa_receita',
                                         'dt_nascimento_atual', 'dt_nascimento_nova', 'dt_nascimento_receita',
                                         'no_mae_atual', 'no_mae_novo', 'no_mae_receita', 'created_at', 'updated_at',
                                         'dt_validacao_cadastral', 'co_situacao_cpf', 'co_tipo_situacao',
                                         'fl_no_pessoa_validado', 'fl_dt_nascimento_validado', 'fl_no_mae_validado',
                                         'vl_rate_no_pessoa_validado', 'vl_rate_no_mae_validado', 'co_rede_alteracao'),
        'funcao.tb_profissional_educacao_funcao': table('co_profissional_educacao_funcao', 'co_pessoa',
                                                        'co_instituicao', 'qt_carga_horaria', 'st_situacao_ativa',
                                                        'created_at', 'updated_at', 'dt_inicio_ocupacao_funcao',
                                                        'dt_fim_ocupacao_funcao',
                                                        'co_situacao_profissional_educacao_funcao',
                                                        'co_ocupacao_funcao', 'nu_matricula_instituicao',
                                                        'co_tipo_vinculo_profissional_educacao'),
        'formacao.tb_profissional_educacao_formacao_academica': table(
            'co_profissional_educacao_formacao_academica', 'co_pessoa', 'no_instituicao_formacao_profissional_outra',
            'nu_ano_inicio', 'nu_ano_conclusao', 'co_area_conhecimento_nivel_superior', 'fl_principal', 'created_at',
            'updated_at', 'co_tipo_formacao_academica'),
    }
    validated = build_students(gen, tables)
    build_validations(gen, tables, validated)
    build_change_requests(gen, tables)
    build_professionals(gen, tables)
    return tables


def sql_value(value):
    if value is None:
        return 'NULL'
    if value is True:
        return 'TRUE'
    if value is False:
        return 'FALSE'
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def to_sql(tables):
    parts = ['-- Fictitious records, written by generate_synthetic_data.py. Do not edit.\nBEGIN;\n']
    for name, content in tables.items():
        columns = ', '.join(content['columns'])
        rows = content['rows']
        for start in range(0, len(rows), CHUNK):
            values = ',\n'.join('(' + ', '.join(sql_value(v) for v in row) + ')' for row in rows[start:start + CHUNK])
            parts.append(f'INSERT INTO {name} ({columns}) VALUES\n{values};\n')
    for name, sequence in SEQUENCES.items():
        if name in tables and tables[name]['rows']:
            parts.append(f"SELECT setval('{sequence}', {max(row[0] for row in tables[name]['rows'])});\n")
    parts.append('COMMIT;\n')
    return ''.join(parts)


def main():
    parser = argparse.ArgumentParser(description='Writes the SQL with the fictitious records (see the module docstring).')
    parser.add_argument('--output', required=True, help='SQL file to write')
    parser.add_argument('--seed', type=int, default=SEED)
    arguments = parser.parse_args()
    Path(arguments.output).write_text(to_sql(build_tables(arguments.seed)), encoding='utf-8')


if __name__ == '__main__':
    main()
