"""Could the specification findings also occur in the 39 operations outside the evaluated scope?

Static analysis of the archived OpenAPI document (identical in 2025 and 2026). For every operation,
records which components its responses reference and whether each finding category applies.
Category 1 (undeclared status codes observed at runtime) cannot be established statically; we only
report how many operations declare no 4XX response, the situation in which it was observed.
Usage: python excluded_operations.py > output/excluded_operations.txt
"""
import json
from collections import Counter
from pathlib import Path

SPEC = Path(__file__).resolve().parents[2] / 'results/official-run/api-docs.json'
IN_SCOPE = {'Estudantes', 'Profissionais da Educação'}
s = json.load(open(SPEC))
schemas = s['components']['schemas']


def refs_and_flags(node, seen, flags):
    """Collect component names reachable from node; flag oneOf/allOf/anyOf and boolean-typed string enums."""
    if isinstance(node, dict):
        if '$ref' in node:
            name = node['$ref'].split('/')[-1]
            if name not in seen:
                seen.add(name)
                refs_and_flags(schemas.get(name, {}), seen, flags)
        for k in ('oneOf', 'allOf', 'anyOf'):
            if k in node:
                flags.add(k)
        if node.get('type') == 'boolean' and any(isinstance(v, str) for v in node.get('enum', [])):
            flags.add('boolean_string_enum')
        for v in node.values():
            refs_and_flags(v, seen, flags)
    elif isinstance(node, list):
        for v in node:
            refs_and_flags(v, seen, flags)


def root_props(schema):
    """Top-level property names of a response schema (resolving one $ref and allOf parts)."""
    if '$ref' in schema:
        schema = schemas.get(schema['$ref'].split('/')[-1], {})
    props = set(schema.get('properties', {}))
    for part in schema.get('allOf', []):
        props |= root_props(part)
    return props


# Facts about the shared components behind categories 3 and 4
pag = schemas['Pagination']
links = pag.get('properties', {}).get('links', {}).get('properties', {})
print('Pagination.links:', {k: v.get('type') for k, v in links.items()})
sm = schemas['MatriculaSaida'].get('properties', {}).get('situacaoMatricula', {})
print('MatriculaSaida.situacaoMatricula:', {k: sm.get(k) for k in ('type', 'enum')})

rows = []
for path, item in s['paths'].items():
    for method, op in item.items():
        if method not in ('get', 'post', 'put', 'patch', 'delete') or not isinstance(op, dict):
            continue
        responses = op.get('responses', {})
        seen, flags = set(), set()
        refs_and_flags(responses, seen, flags)
        ok = responses.get('200') or responses.get('201') or {}
        ok_schema = ok.get('content', {}).get('application/json', {}).get('schema', {})
        rp = root_props(ok_schema) if ok_schema else set()
        rows.append({
            'op': f'{method.upper()} {path}', 'tag': ', '.join(op.get('tags', [])),
            'scope': bool(IN_SCOPE & set(op.get('tags', []))),
            'codes': sorted(responses), '401': '401' in responses,
            'has_4xx': any(c.startswith('4') for c in responses),
            'pagination': 'Pagination' in seen, 'matricula_saida': 'MatriculaSaida' in seen,
            'composition': bool(flags & {'oneOf', 'allOf', 'anyOf'}),
            'bool_str_enum': 'boolean_string_enum' in flags,
            'ok_has_data': 'data' in rp, 'ok_root_props': len(rp - {'success', 'message', 'data', 'pagination'}),
        })

for scope in (True, False):
    sub = [r for r in rows if r['scope'] == scope]
    label = 'evaluated (19)' if scope else 'excluded (39)'
    print(f'\n=== Operations {label}: n = {len(sub)}')
    print('  declare 401 ........................................', sum(r['401'] for r in sub))
    print('  declare no 4XX response ............................', sum(not r['has_4xx'] for r in sub))
    print('  responses use Pagination (cat. 3) ..................', sum(r['pagination'] for r in sub))
    print('  responses use MatriculaSaida (cat. 4) ..............', sum(r['matricula_saida'] for r in sub))
    print('  responses with boolean + string enum ...............', sum(r['bool_str_enum'] for r in sub))
    print('  responses with oneOf/allOf/anyOf (cat. 5) ..........', sum(r['composition'] for r in sub))
    print('  200/201 schema without "data" and with root properties', sum((not r['ok_has_data']) and r['ok_root_props'] > 0 for r in sub))
    print('  per tag:', dict(Counter(r['tag'] for r in sub)))

print('\nExcluded: detail')
for r in sorted((r for r in rows if not r['scope']), key=lambda r: r['op']):
    marks = [k for k in ('pagination', 'matricula_saida', 'composition', 'bool_str_enum') if r[k]]
    if (not r['ok_has_data']) and r['ok_root_props'] > 0:
        marks.append('root_props')
    print(f"  {r['op']:70s} {','.join(r['codes']):18s} {' '.join(marks)}")
print('\nEvaluated with root properties (without data):',
      [r['op'] for r in rows if r['scope'] and not r['ok_has_data'] and r['ok_root_props'] > 0])
