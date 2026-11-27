# Limpeza e conciliação de precatórios

Solução para diagnosticar, limpar e conciliar os arquivos do case de engenharia
de software. O pipeline preserva os insumos, evita dupla contabilização de
pagamentos e produz uma base limpa acompanhada de pendências e auditoria.

O diagnóstico completo, com evidências e impactos, está em
[`DIAGNOSTICO.md`](DIAGNOSTICO.md). A proposta de banco está em
[`sql/001_prevent_data_quality_issues.sql`](sql/001_prevent_data_quality_issues.sql).

## Requisitos

- Python 3.10 ou mais recente;
- Git, caso o projeto seja obtido por clone;
- dependências de execução instaladas automaticamente pelo `pip`;
- `pytest` para executar os testes.

No Windows, a instalação inclui automaticamente o pacote `tzdata`, necessário
para resolver o fuso `America/Sao_Paulo`. macOS e Linux usam a base de fusos do
sistema operacional.

PostgreSQL não é necessário para executar a limpeza. O arquivo em `sql/` é uma
proposta de evolução do banco descrito no case.

## Obter o projeto

Por HTTPS:

```bash
git clone https://github.com/LeandroLeite93/bzr-group-software-engineering-case.git
cd bzr-group-software-engineering-case
```

Também é possível baixar o ZIP pelo GitHub, extraí-lo e abrir o terminal na pasta
que contém este README.

## Instalação no macOS ou Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install '.[dev]'
```

## Instalação no Windows

No PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install ".[dev]"
```

No Prompt de Comando (`cmd.exe`), a ativação equivalente é:

```bat
.venv\Scripts\activate.bat
```

Se a política corporativa do PowerShell bloquear `Activate.ps1`, não é preciso
alterá-la. Use diretamente o Python do ambiente virtual:

```powershell
.\.venv\Scripts\python.exe -m pip install ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m precatorios --raw-dir data/raw --output-dir output
```

Todos os comandos seguintes são iguais nos três sistemas depois da ativação do
ambiente virtual.

## Execução rápida

Com o ambiente virtual ativo:

```bash
python -m pytest
python -m precatorios --raw-dir data/raw --output-dir output
python -m pytest tests/test_source_integrity.py
```

Resultados esperados:

```text
39 passed
6 precatórios gerados
8 eventos de pagamento aceitos
9 pendências registradas
17 ocorrências auditadas
1 passed no teste isolado de integridade
```

O comando instalado `precatorios-cleaner` é uma alternativa equivalente a
`python -m precatorios`:

```bash
precatorios-cleaner --raw-dir data/raw --output-dir output
```

Os argumentos são opcionais. A execução abaixo usa as mesmas pastas padrão:

```bash
python -m precatorios
```

O programa não altera os arquivos em `data/raw` e gera novamente:

- `output/precatorios.csv`: cadastro conciliado, prazo e saldo;
- `output/pagamentos.csv`: eventos válidos, vigentes e deduplicados;
- `output/pendencias.csv`: conflitos ou registros que exigem decisão humana;
- `output/ocorrencias.csv`: correções, descartes e decisões auditáveis;
- `output/resumo.json`: contagens e totais da execução.

Os resultados são determinísticos e não são versionados. Eles podem ser
reproduzidos a qualquer momento a partir dos insumos preservados.

## Testes

```bash
python -m pytest
```

A suíte possui 39 casos e cobre as regras de maior risco: dinheiro com `Decimal`,
normalização CNJ, codificação e dialeto reais do CSV, corte de 2 de abril, fuso,
duplicatas, versões de evento, estornos e execução completa do pipeline.

A integridade dos arquivos originais também pode ser conferida separadamente:

```bash
python -m pytest tests/test_source_integrity.py
```

Esse comando é multiplataforma. Como verificação opcional pelo sistema
operacional, use `shasum -a 256 -c data/raw/SHA256SUMS` no macOS ou
`sha256sum -c data/raw/SHA256SUMS` no Linux.

## Solução de problemas

- Confirme a versão com `python --version`; ela deve ser 3.10 ou mais recente.
- Confirme que o ambiente está ativo. O terminal normalmente exibe `(.venv)`.
- Se `precatorios-cleaner` não estiver no `PATH`, use
  `python -m precatorios`, que executa o mesmo programa.
- Execute os comandos a partir da pasta que contém `pyproject.toml`.
- Para recriar as saídas, basta executar o pipeline novamente; não é necessário
  apagar a pasta `output`.

## Decisões conservadoras

- O tribunal é a fonte cadastral provisória quando o processo aparece nas duas
  bases; qualquer conflito continua pendente.
- A maior versão por `atualizado_em` substitui a anterior. Empate com conteúdo
  diferente não é resolvido automaticamente.
- Estornos mantêm valor positivo e efeito contábil negativo.
- Instantes de apresentação são convertidos para `America/Sao_Paulo` antes do
  cálculo do prazo. Essa premissa precisa de confirmação do tribunal.
- O número CNJ é validado estruturalmente. O dígito verificador não é rejeitado
  porque os processos fictícios do case não passam nessa validação.
- Dados ambíguos permanecem em quarentena; o programa não inventa correções.

## Estrutura

```text
data/raw/             arquivos recebidos e hashes de integridade
src/precatorios/      regras de domínio, pipeline e CLI
tests/                testes unitários e de integração
sql/                  proposta de migração PostgreSQL
output/               resultados reproduzíveis da execução
DIAGNOSTICO.md         diagnóstico, prevenção e dúvidas
```

## Uso de IA

Usei o OpenAI Codex como apoio para explorar os arquivos, discutir a arquitetura,
escrever testes, implementar partes do pipeline e revisar a documentação. As
sugestões não foram aceitas como fonte de verdade automaticamente.

O resultado foi conferido por meio de:

- comparação byte a byte e SHA-256 dos arquivos copiados;
- referências diretas às linhas dos insumos no diagnóstico;
- cálculo manual dos casos de duplicidade, versão e estorno;
- testes automatizados das regras e do pipeline completo;
- execução do comando instalado em ambiente virtual;
- revisão dos arquivos de saída e dos totais por processo;
- separação explícita entre fatos, premissas e dúvidas de negócio.
