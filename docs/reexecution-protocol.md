# Re-execution protocol (2026)

This document fixes, before the campaign starts, how the study is re-executed for the
revision of the paper. Any change made after the campaign starts is recorded under
[Deviations](#deviations), with its date and reason.

The original study (May 2025, EvoMaster 3.4.0, `results/official-run/`) is kept as it
is; its coverage is recomputed with the revised coverage tool.

## Why a re-execution, and why EvoMaster 6.2.0

Checking the three techniques against the behavior of EvoMaster 3.4.0 (its source code
and pilot executions against the API) showed that, in black-box mode:

- **MIO cannot run.** The black-box module of 3.4.0 binds no mutator, so MIO stops with
  `UninitializedPropertyAccessException: lateinit property mutator has not been
  initialized` at its first mutation. The defect was fixed upstream in February 2026
  (issue #1442, commit `ae877255b`); the first release with the fix is 5.1.0.
- **WTS behaved as random sampling in the original study.** WTS first builds an initial
  population of 30 suites of 1 to 50 random tests each (about 765 tests on average)
  and only then starts crossover and mutation. In the original executions it evaluated
  84 to 107 tests in the 30-minute budget, so the search ended inside the initial
  population. Had it reached its mutation step, it would have stopped on the same
  missing mutator.

Version 3.4.0 therefore cannot run two of the four techniques as designed in black-box
mode. The re-execution uses EvoMaster **6.2.0** (released on 15 September 2026), the
latest release when this protocol was written (October 2026).

## Tool

| Item | Value |
|---|---|
| EvoMaster | 6.2.0, `evomaster.jar` from the GitHub release, SHA-256 `93f9c4a0de88b01395d2a1009776aa739973e9f64343778d2fd49c212fd17915` |
| Java | Eclipse Temurin 17.0.21+9 (6.2.0 requires Java 17) |
| Mode | black-box, REST, Python unittest output |
| Campaign file | [`tool/configs/campaign-6.2.0.json`](../tool/configs/campaign-6.2.0.json) |
| Runner | [`tool/campaign.py`](../tool/campaign.py) |

## Techniques and settings

- **Techniques:** MIO, RANDOM, SMARTS and WTS, each with EvoMaster's default parameters.
- **Search budget:** 30 minutes of search per execution (`maxTime 30m`, stopping
  criterion TIME), as in the original study.
- **Request rate:** no limit (`ratePerMinute 0`, EvoMaster's default). The original
  study limited it to 70 requests per minute to protect a shared environment; here the
  API is local and dedicated. With 70 requests per minute, WTS would again not finish
  its initial population (about 430 tests in 30 minutes in a pilot).
- **Phases after the search are disabled:** minimization (`minimize false`), security
  testing (`security false`) and the additional HTTP oracles (`httpOracles false`).
  They add or change tests after the search, independently of the technique, and in
  the original study the minimization never finished (it timed out in all 30
  executions). The generated suite is therefore exactly what each technique's search
  kept.
- **Connection to the API** (`tool/configs/em.yaml`, not versioned because it holds the
  API key): `blackBox true`, `bbSwaggerUrl http://localhost:8000/docs?api-docs.json`,
  `endpointTagFilter "Estudantes, Profissionais da Educação"` (the same 19 operations
  as the original study), `header0 "x-api-key: …"`.

## Repetitions and order

- **30 repetitions per technique**, organized in 30 blocks. Each block executes the
  four techniques once, in an order drawn from the campaign seed (`20261030`).
- Each execution has its own EvoMaster seed, drawn from the same generator. The order
  and the seeds are saved in `plan.json` before the first execution.
- The campaign may only stop between blocks, so every technique always has the same
  number of repetitions.
- An execution that fails is executed again, with the same seed, after the remaining
  ones; what it left behind is kept in `incomplete/`.

## Environment

The CMDE API runs locally from the same code used in the original study, with:

- PostgreSQL 17 created from a schema dump and from the tables that hold domain data
  (codes, schools, institutions, API keys), filled with fictitious records of students
  and education professionals (see [Records in the database](#records-in-the-database));
- Kumo emulating the SQS queues and the S3 bucket that the API uses in AWS;
- a queue worker consuming the batch queue (in the original study nothing consumed it).

Differences from the original environment, to be reported in the paper:

| | Original study (2025) | Re-execution (2026) |
|---|---|---|
| Database | test database on AWS RDS (us-east-1), shared, with fictitious records | local PostgreSQL 17 with fictitious records generated for this study, restored before each execution |
| Students of the network of the API key | 598,780 | 5,000 |
| Registration validations | 54,714 | 457 |
| Change requests | 72 | 72 |
| Education professionals | 3 | 3 |
| Queues and storage | AWS SQS and S3 | Kumo (local) |
| Queue consumer | none | worker running |
| Request rate | about 20 requests per minute, bounded by latency to AWS | bounded only by the local API |
| API key | a key of one education network (*rede*) in the development environment | another existing key of the same network |

The counts of the original study are the pagination totals recorded in its generated tests.

In both environments the API runs without Redis, which it uses only as a cache. Every attempt
to reach it fails and is written to the Laravel log ("Falha ao utilizar Redis"), and the API
runs the same query on PostgreSQL, so the responses do not change. This is not a difference
between the environments.

The machine, operating system, Java, Python, Docker and container image versions, and the
SHA-256 of the files that create the database, are recorded automatically at every invocation
of the runner (`invocations/*.json`). The machine runs only the campaign while it is in
progress.

### Records in the database

The local database would otherwise hold no record of a person: every list would come back
empty and the operations that look up one record would never answer 200, so most of the
responses the study analyzes would not be observed.
[`tool/generate_synthetic_data.py`](../tool/generate_synthetic_data.py) writes the records,
always the same ones (fixed seed).

- **Nothing can belong to a real person.** CPFs and NISs have a wrong check digit on purpose,
  telephone numbers use the nonexistent area code 00, e-mail addresses use the reserved
  `.invalid` domain, addresses are invented and names are random combinations of common names.
  Because of the wrong check digit, a request that writes one of these CPFs is rejected by the
  API's validation, as any invalid CPF is.
- **Volumes follow the original study.** Students are scaled down to 5,000, which keeps the time
  of a request close to that of the rest of the API; validations keep their proportion (9.1%);
  the two small counts are kept. The other proportions (optional fields, inactive enrollments)
  are choices of the script and are stated in it.

The records use the 25 first active schools of the network of the API key. A few students are
also enrolled in another network, which the responses report.

## Each execution

1. Reset: what the requests changed is undone, without loading the records again. The
   database is created once per invocation of the runner, from the dumps and the fictitious
   records, and a copy of it is kept; each reset replaces the database with that copy, which
   also restores records that a request changed. The API containers are recreated (empty
   queues and bucket), the Laravel log and cache are emptied, and the API is polled until it
   answers.
2. EvoMaster search with the technique and seed of the plan.
3. The API logs of the search are saved: nginx access and error logs, Laravel log,
   worker log.
4. The generated suite is executed twice, each time after a new reset and with every
   HTTP exchange recorded (request, response, status, time and the test that made it;
   the API key is not recorded), and the API logs of each execution are saved:
   - **as generated**, which gives the time to execute the suite and which tests pass;
   - **without assertions** (`python -O`). The tests were generated against the state
     the search had built up, so on a reset environment some assertions no longer hold
     (in a pilot, 17 to 46 tests out of 80 to 109) and the test stops before its
     remaining requests. Without assertions every request in the suite is made, which
     is what the analysis of the responses reads.
5. The coverage criteria are computed from the generated tests with the revised tool.

Every phase has its start, end and duration recorded in `run.json`.

## Measures

- **Generated suite:** number of tests and of HTTP calls (from the tests and from the
  recorded traffic).
- **Time:** search time, time to execute the generated suite, and the other phases.
- **Coverage:** the seven criteria (path, operation, parameter, parameter value, status
  code class, status code, response body properties) as defined in the revised paper.
- **Responses:** the response bodies actually returned while executing the suite,
  recorded for the analysis of response body properties.
- **Search effort:** tests evaluated during the search (EvoMaster output and statistics
  file) and requests the API received (nginx access log of the search). EvoMaster's own
  count of HTTP calls can be higher than what the API received: in a pilot, by 2% for MIO
  and 11% for SMARTS, with no difference for RANDOM and WTS.

## Low-budget campaign

A second campaign repeats the procedure with the request rate of the original study, to
test whether the differences between techniques depend on how many requests the search
can make. In the original study the API was slow (its database was remote), so the
searches made 413 to 767 requests in 30 minutes, about 20 per minute, although the limit
was set to 70. The low-budget campaign (`configs/campaign-6.2.0-low-budget.json`) differs
from the main one in two settings only:

- **Request rate:** 20 requests per minute (`ratePerMinute 20`), about 600 requests in
  the 30 minutes of search. EvoMaster waits between requests; the API is not slowed down.
- **Repetitions:** 10 per technique (10 blocks), as in the original study. The plan comes
  from the same campaign seed, so its order and EvoMaster seeds are those of the first 10
  blocks of the main campaign.

With this budget WTS does not finish its initial population, as in the original study.
EvoMaster checks the budget between tests, so the last test of a search can end after
the 30 minutes; with 3 seconds between requests this adds up to about half a minute (21
seconds in a pilot).

## Pilots

Pilot campaigns check the whole procedure before the campaign and are not part of the
results. They use the same campaign file with fewer blocks and a shorter budget, e.g.

```
python campaign.py --config configs/campaign-6.2.0.json --output data_generated/pilot-01 --blocks 1 --max-time 2m
```

One pilot had the full size of the campaign (30 blocks, 30 minutes per execution) on a
database with no records of people. It showed the limitation described in
[Records in the database](#records-in-the-database), which is why the records were added
before the campaign.

## Deviations

None so far.
