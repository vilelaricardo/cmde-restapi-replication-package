# Pacote de Replicação

Este diretório reúne a ferramenta e os resultados agregados usados no estudo de
geração automática de dados de teste para APIs RESTful (técnicas RANDOM, WTS e
SMARTS, via [EvoMaster](https://www.evomaster.org)).

## Licença

O código (`tool/`, `analysis/`) é distribuído sob a licença MIT. Os dados em
`results/` (saídas do experimento, testes gerados, dados de cobertura) são
distribuídos sob Creative Commons Attribution 4.0 (CC BY 4.0). Ver [LICENSE](LICENSE).

## ⚠️ Sobre dados sensíveis

A API alvo do estudo (CMDE — Conjunto Mínimo de Dados Educacionais, mantida pelo
Ministério da Educação) é responsável por receber os dados que alimentam o programa
Pé-de-Meia, uma das principais políticas públicas do governo federal. A
**documentação da API é pública**
(<https://api-cmde.gestaopresente.mec.gov.br/v1/documentation>), então a
especificação OpenAPI (`api-docs.json`) e os critérios derivados dela
(`criteria/*.json`) estão incluídos neste pacote sem restrição.

> **Nota de versão:** o `api-docs.json` aqui incluído é uma cópia **arquivada no
> momento do experimento** (maio de 2025). A documentação pública no link acima pode
> ter mudado desde então — não assuma que os dois são idênticos.

Já os testes gerados pelo EvoMaster (`generated_tests/*.py`, em
`results/official-run/`) continham, embutida em cada requisição, **uma chave de
autenticação real (`x-api-key`) usada para acessar a API**. Diferente da
especificação, essa chave não é informação pública — foi **redigida (substituída por
`REDACTED_API_KEY`) em todos os 76 arquivos** antes de serem incluídos aqui. O
conteúdo dos payloads (nomes, CPFs, endereços etc.) que aparece nesses testes é dado
**sintético gerado automaticamente pelo EvoMaster** para fins de fuzzing — não foram
encontrados indícios de dados reais de estudantes nas amostras verificadas
(nomes como "Donald Jackson"/"Timothy Garcia", endereços como "Rua teste", e-mails
como "elegibel@elegivel.com" e números repetidos como "11111111111" são padrões
típicos de dado gerado por fuzzing, não de registros reais). Ainda assim, os arquivos
não foram auditados um a um — se for reutilizar este material, vale essa checagem.

O binário `evomaster.jar` não é versionado aqui; baixe a versão usada diretamente do
[repositório oficial do EvoMaster](https://github.com/WebFuzzing/EvoMaster/releases).

## Estrutura

```
replication-package/
├── tool/                        # Ferramenta de execução do experimento (genérica)
│   ├── main.py
│   ├── criteria_analyzer.py
│   ├── extract_criteria_from_swagger.py
│   ├── extract_tests_data.py
│   ├── run_get_statistics_csv.py
│   ├── analyze_minimization.py  # extrai dados da fase de minimização dos logs brutos
│   ├── helpers.py
│   ├── exceptions.py
│   ├── requirements.txt
│   └── configs/
│       ├── em.yaml.example      # copie para em.yaml e aponte para a SUA API
│       └── setup_experiment.json
├── analysis/                    # Análise estatística e geração das figuras do artigo
│   ├── compute_statistics.py    # reproduz todo número estatístico citado no artigo
│   ├── generate_figures.py      # reproduz todas as figuras (grava em analysis/output/)
│   └── requirements.txt
├── results/
│   ├── statistics/               # resultados agregados (CSV + JSON) das 4 execuções
│   │   └── minimization_analysis.csv  # gerado por tool/analyze_minimization.py
│   └── official-run/             # dados brutos completos do dataset oficial (ver abaixo)
│       ├── api-docs.json         # spec OpenAPI arquivada em maio/2025
│       ├── criteria/             # paths/parâmetros extraídos da spec
│       └── repetition_0..9/      # RANDOM/SMARTS/WTS × 10 repetições
│           └── <ALGORITMO>/
│               ├── generated_tests/       # testes gerados (chave redigida)
│               ├── execution_output.txt   # log bruto (tempo real, potential faults)
│               ├── criteria_analyzed/     # cobertura por critério, desta execução
│               ├── covered_targets.txt
│               └── extracted_test_data.json
├── Dockerfile
└── docker-compose.yaml
```

## Resultados: qual arquivo é o "oficial"

A pasta `results/statistics/` contém resumos agregados de **4 execuções completas**
(10 repetições × 3 técnicas cada), feitas em datas diferentes durante o
desenvolvimento do estudo. **Apenas uma delas é o dataset reportado no artigo** — e é
a única cujos dados brutos completos estão em `results/official-run/`:

| Execução | `max_time` configurado | Usado no artigo? | Dados brutos inclusos? |
|---|---|---|---|
| `experiment-date-03-05-25-time-01-29-53-388` | 15m | Não (piloto) | Não (só resumo agregado) |
| **`experiment-date-03-05-25-time-21-29-51-725`** | **30m** | **Sim — dataset oficial** | **Sim — `results/official-run/`** |
| `experiment-date-05-05-25-time-00-15-46-626` | 20m | Não (piloto) | Não (só resumo agregado) |
| `experiment-date-06-05-25-time-19-56-26-372` | 15m | Não (piloto) | Não (só resumo agregado) |

> **Nota:** o `max_time` real usado na execução oficial (a de 21:29:51) foi de 30
> minutos por execução, consistente com o orçamento de busca de 30 minutos descrito
> no artigo.

### O que tem em `results/official-run/` que ainda não foi usado no artigo

Cada `execution_output.txt` registra, além do que já está reportado nas Tabelas do
artigo, duas métricas nunca exploradas: **tempo real de execução** (`Passed time
(seconds)`) e uma contagem de **indícios de defeito** (`Potential faults`) detectados
automaticamente pelo EvoMaster. Os arquivos `generated_tests/EvoMaster_faults_Test.py`
contêm exemplos concretos desses indícios (endpoint, payload, resposta). Os achados
de especificação discutidos na Seção 5.4 do artigo (códigos de status não
declarados, inconsistências de schema, tipagem de paginação, etc.) foram extraídos
justamente destes arquivos; as duas métricas em si (tempo real de execução e
potencial de falhas) permanecem como direção não explorada para trabalhos futuros.

## Como reproduzir a análise estatística e as figuras

Todos os números estatísticos (Shapiro-Wilk, Kruskal-Wallis, post-hoc de Dunn com
correção de Bonferroni, correlação de Spearman, tamanhos de efeito η²_H) e todas as
figuras de resultado do artigo são recalculados diretamente a partir dos dados já
incluídos neste pacote (`results/statistics/*.csv` e
`results/official-run/*/execution_output.txt`) — não é necessário rodar o
experimento de novo para isso.

```bash
cd analysis
pip install -r requirements.txt
python compute_statistics.py    # imprime todo número reportado no artigo
python generate_figures.py      # grava as 6 figuras em analysis/output/
```

`compute_statistics.py` foi conferido número a número contra o texto e as tabelas
do artigo (Seções 5.1–5.3) antes de ser incluído aqui. `generate_figures.py`
reproduz as mesmas figuras usadas no artigo (`../../figuras/` no repositório
principal) a partir dos dados brutos.

Se os dados da fase de minimização (`results/statistics/minimization_analysis.csv`)
precisarem ser regerados a partir dos logs brutos, rode primeiro:

```bash
python tool/analyze_minimization.py
```

## Como reproduzir o experimento

Para rodar o experimento novamente contra a CMDE (requer uma `x-api-key` própria,
não incluída aqui) ou contra outra API REST com especificação OpenAPI:

1. Copie `tool/configs/em.yaml.example` para `tool/configs/em.yaml` e configure
   `bbSwaggerUrl` apontando para a especificação OpenAPI da API alvo (para a CMDE:
   <https://api-cmde.gestaopresente.mec.gov.br/v1/documentation>), além de
   `maxTime` e demais opções desejadas
   ([documentação de opções do EvoMaster](https://github.com/WebFuzzing/EvoMaster/blob/master/docs/options.md)).
2. Ajuste `tool/configs/setup_experiment.json` com os algoritmos e número de
   repetições desejados.
3. Baixe `evomaster.jar` (ver link acima) e coloque em `tool/`.
4. Rode com Docker (`docker compose up --build`) ou localmente
   (`python tool/main.py`, requer Python 3.8+ e Java 8).

Os resultados serão salvos em `tool/data_generated/<nome_experimento>/`, e o CSV de
estatísticas pode ser gerado com:

```bash
python tool/run_get_statistics_csv.py -n <nome_experimento>
```
