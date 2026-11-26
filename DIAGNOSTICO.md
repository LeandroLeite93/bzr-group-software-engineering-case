# Diagnóstico dos dados de precatórios

## Resumo executivo

A diferença entre os números da operação e os do tribunal não tem uma causa
única. O problema mais grave é a falta de idempotência: o processo atual soma
eventos repetidos e versões antigas sempre que um arquivo é reprocessado. Há
também uma divergência de semântica para estornos, eventos inválidos descartados
sem aviso, conflitos cadastrais entre as fontes e prazos calculados incorretamente.

A limpeza encontrou:

- 13 registros de pagamento recebidos;
- 8 eventos vigentes e importáveis;
- 1 duplicata exata descartada;
- 1 versão antiga substituída;
- 3 eventos mantidos em quarentena;
- 6 processos na união das fontes;
- 9 pendências que exigem confirmação humana;
- R$ 126.300,00 de valor de face na base conciliada;
- R$ 34.200,50 de pagamento líquido.

Os valores de campos divergentes não foram escolhidos silenciosamente. Quando o
processo aparece no tribunal, a limpeza usa provisoriamente seu cadastro como
fonte principal e marca a divergência. Quando ele existe somente no Hub, o dado é
preservado, mas permanece pendente.

## Classificação

| Ordem | Gravidade | Problema | Natureza |
|---:|---|---|---|
| 1 | Crítica | Reprocessamento duplica pagamentos e soma versões antigas | Causa raiz |
| 2 | Crítica | Estorno pode ser somado como pagamento | Causa raiz |
| 3 | Alta | Eventos inválidos são ignorados sem aviso | Causa e consequência |
| 4 | Alta | Tribunal e Hub divergem sobre ente, valor e existência | Consequência observada |
| 5 | Alta | Prazos de pagamento estão incorretos ou dependem de fuso não definido | Causa e consequência |
| 6 | Alta | Arquivos reais contradizem o contrato documentado | Causa raiz |
| 7 | Média | Comparação textual exata produz falsos desencontros | Causa raiz |
| 8 | Média | Banco não garante idempotência nem rastreabilidade | Causa estrutural |
| 9 | Média | Datas de apresentação não possuem contrato documentado | Causa estrutural |
| 10 | Média | Conferência manual no Excel pode modificar o insumo | Fator agravante |

## Problemas encontrados

### 1. Reprocessamento duplica pagamentos e soma versões antigas

**Gravidade:** crítica

**Natureza:** causa raiz dos totais de pagamento incorretos.

**Evidências**

- O processo operacional manda somar cada valor e permite executar novamente o
  mesmo arquivo depois de uma falha
  ([ENUNCIADO.md, linhas 15–16](data/raw/ENUNCIADO.md#L15-L16)).
- `ev-002` aparece duas vezes com o mesmo conteúdo
  ([pagamentos.json, linhas 10–17](data/raw/dados/pagamentos.json#L10-L17) e
  [linhas 26–33](data/raw/dados/pagamentos.json#L26-L33)).
- `ev-001` aparece primeiro com R$ 15.000,00
  ([linhas 2–9](data/raw/dados/pagamentos.json#L2-L9)) e depois com
  R$ 15.500,00 e `atualizado_em` posterior
  ([linhas 66–73](data/raw/dados/pagamentos.json#L66-L73)).
- `pagamento.evento_id` não possui restrição `UNIQUE`
  ([schema.sql, linha 11](data/raw/schema.sql#L11)).
- O banco não armazena o `atualizado_em` recebido.

**Impacto**

Para o processo `0012345-10.2019.8.26.0053`, somar todas as ocorrências produz
R$ 35.501,00. Mantendo somente a versão mais recente de `ev-001` e uma ocorrência
de `ev-002`, o total é R$ 18.000,50. A diferença de R$ 17.500,50 é uma
superavaliação causada apenas por duplicidade e versionamento.

O erro cresce a cada tentativa do operador e pode fazer um precatório parecer
mais pago do que realmente está.

**Relação causal**

A janela móvel de sete dias e a possibilidade de reexecução tornam repetições
normais. A ausência de idempotência no importador e no banco transforma essa
característica esperada em erro financeiro.

**Tratamento na limpeza**

- duplicata exata: descartada e registrada na auditoria;
- mesmo `evento_id` com atualizações diferentes: mantida a versão de maior
  `atualizado_em`;
- versões diferentes com o mesmo `atualizado_em`: nenhuma é escolhida
  arbitrariamente; o evento fica pendente.

### 2. Estorno pode ser somado como pagamento

**Gravidade:** crítica

**Natureza:** causa raiz de total pago incorreto.

**Evidências**

- `ev-007` tem `tipo = "estorno"` e valor positivo de R$ 5.000,00
  ([pagamentos.json, linhas 58–65](data/raw/dados/pagamentos.json#L58-L65)).
- A documentação afirma que `tipo` é sempre `pagamento`
  ([DOCUMENTACAO_TRIBUNAL.md, linha 15](data/raw/DOCUMENTACAO_TRIBUNAL.md#L15)).
- O banco, ao contrário da documentação, aceita `pagamento` e `estorno`
  ([schema.sql, linha 12](data/raw/schema.sql#L12)).
- O fluxo descrito apenas soma cada valor
  ([ENUNCIADO.md, linha 16](data/raw/ENUNCIADO.md#L16)).

**Impacto**

No processo `0034567-32.2018.8.26.0405`, `ev-006` paga R$ 5.000,00 e `ev-007`
estorna R$ 5.000,00. O efeito líquido correto é zero. Somar os dois valores
resultaria em R$ 10.000,00 pagos, invertendo o efeito do estorno.

**Relação causal**

O contrato, o dado e o schema discordam sobre o domínio de `tipo`. Sem uma regra
explícita, o importador aplica ao estorno a mesma operação usada no pagamento.

**Tratamento na limpeza**

O valor armazenado continua positivo, preservando o evento recebido. O efeito
contábil é positivo para `pagamento` e negativo para `estorno`.

### 3. Eventos inválidos são ignorados sem aviso

**Gravidade:** alta

**Natureza:** consequência dos defeitos de origem e causa da falta de explicação
dos totais.

**Evidências**

- O fluxo determina que o script ignore eventos não importáveis e não avise
  ninguém ([ENUNCIADO.md, linha 19](data/raw/ENUNCIADO.md#L19)).
- `ev-004` tem valor nulo
  ([pagamentos.json, linhas 34–41](data/raw/dados/pagamentos.json#L34-L41)).
- `ev-009` é um `pagamento` com valor negativo
  ([linhas 82–89](data/raw/dados/pagamentos.json#L82-L89)).
- `ev-010` não informa processo
  ([linhas 90–97](data/raw/dados/pagamentos.json#L90-L97)).

**Impacto**

O operador não consegue distinguir entre arquivo totalmente processado e arquivo
parcialmente processado. O valor de `ev-004` não pode ser recuperado do arquivo;
os R$ 750,00 de `ev-010` não podem ser atribuídos; e os R$ -200,00 de `ev-009`
podem ser erro de sinal ou um estorno classificado incorretamente. Corrigir esses
casos automaticamente inventaria informação.

**Relação causal**

Os registros inválidos são defeitos de origem. O descarte silencioso é uma
segunda falha: ele transforma defeitos localizados em divergências sem explicação.

**Tratamento na limpeza**

Os três eventos ficam em `pendencias.csv`, com arquivo, registro, identificador e
motivo. O processamento dos demais continua e cada rejeição também aparece em
`ocorrencias.csv`.

### 4. Tribunal e Hub divergem sobre ente, valor e existência

**Gravidade:** alta

**Natureza:** consequência observada de integração e conciliação insuficientes.

**Evidências**

- Processo `0023456-21.2020.8.26.0053`: R$ 30.000,00 no tribunal
  ([tribunal.csv, linha 3](data/raw/dados/tribunal.csv#L3)) e R$ 31.000,00 no Hub
  ([hub.csv, linha 3](data/raw/dados/hub.csv#L3)).
- Processo `0045678-43.2021.5.02.0011`: ente `União` no tribunal
  ([tribunal.csv, linha 5](data/raw/dados/tribunal.csv#L5)) e
  `Município de Santos` no Hub
  ([hub.csv, linha 5](data/raw/dados/hub.csv#L5)).
- Processo `0056789-54.2017.4.03.6100` existe no Hub
  ([hub.csv, linha 6](data/raw/dados/hub.csv#L6)), mas não no tribunal.
- Processo `0067890-65.2016.8.26.0053` existe no tribunal
  ([tribunal.csv, linha 6](data/raw/dados/tribunal.csv#L6)), mas não no Hub.

**Impacto**

O conflito de ente pode direcionar cobrança, comunicação ou análise ao devedor
errado. O conflito de valor altera saldo e exposição em R$ 1.000,00. Processos
ausentes de uma fonte podem ser indevidamente incluídos ou excluídos da carteira.

**Relação causal**

Essas são divergências de negócio reais, não diferenças de formatação. Elas
ficam escondidas quando a operação depende de comparação manual e não mantém um
relatório estruturado de conciliação.

**Tratamento na limpeza**

O cadastro do tribunal é usado provisoriamente quando presente, por ser a lista
oficial recebida. O valor do Hub é preservado no motivo da pendência. Processos
presentes em somente uma fonte continuam na saída com status `pendente`.

### 5. Prazos de pagamento incorretos e fuso não definido

**Gravidade:** alta

**Natureza:** consequência de regra de corte implementada incorretamente e causa
de priorização errada.

**Evidências**

- A regra informa que apresentações até 2 de abril vencem no fim do ano seguinte
  ([ENUNCIADO.md, linha 11](data/raw/ENUNCIADO.md#L11)).
- O processo `0012345-10.2019.8.26.0053` foi apresentado em `2025-04-02`, mas o
  Hub registra prazo `2027-12-31`
  ([hub.csv, linha 2](data/raw/dados/hub.csv#L2)). O prazo calculado pela regra é
  `2026-12-31`.
- O processo `0056789-54.2017.4.03.6100` foi apresentado como
  `2025-04-03T01:00:00Z`
  ([apresentacoes.json, linhas 18–21](data/raw/dados/apresentacoes.json#L18-L21)).
  Em São Paulo, esse instante corresponde a 2 de abril às 22h.

**Impacto**

Um prazo deslocado em um ano altera a priorização da carteira e pode atrasar a
atuação sobre um crédito. No segundo caso, resultados diferentes são possíveis
dependendo de usar a data UTC, a data textual ou a data civil do tribunal.

**Relação causal**

O primeiro erro é confirmado e sugere que 2 de abril foi tratado como "depois do
corte". O segundo é uma ambiguidade de contrato: a regra fala em data, enquanto o
arquivo fornece um instante, sem dizer qual fuso define o dia jurídico.

**Tratamento na limpeza**

A limpeza considera 2 de abril inclusivo e converte instantes para
`America/Sao_Paulo`. O prazo do segundo processo permanece destacado como decisão
a confirmar antes da produção.

### 6. Arquivos reais contradizem o contrato documentado

**Gravidade:** alta

**Natureza:** causa raiz de falhas de leitura e descartes.

**Evidências**

| Contrato | Arquivo recebido |
|---|---|
| `tribunal.csv` em UTF-8 | ISO-8859-1; por exemplo, `í` está gravado como byte `0xED` |
| campos separados por vírgula | cabeçalho e registros separados por `;` |
| valor com ponto decimal | valores como `45.000,00` |
| `valor` do pagamento é número | `ev-002` usa a string `"2.500,50"` |
| data no formato `AAAA-MM-DD` | `ev-002` usa `10/04/2025` |
| `tipo` sempre é `pagamento` | `ev-007` é `estorno` |
| processo no formato CNJ pontuado | `ev-005` usa `00234562120208260053` |

O leiaute prometido para o CSV está em
[DOCUMENTACAO_TRIBUNAL.md, linhas 18–26](data/raw/DOCUMENTACAO_TRIBUNAL.md#L18-L26).
As divergências de `ev-002`, `ev-005` e `ev-007` aparecem respectivamente em
[pagamentos.json, linhas 10–17](data/raw/dados/pagamentos.json#L10-L17),
[linhas 42–49](data/raw/dados/pagamentos.json#L42-L49) e
[linhas 58–65](data/raw/dados/pagamentos.json#L58-L65).

**Impacto**

Um importador implementado conforme a documentação pode falhar ao abrir o CSV,
produzir texto corrompido, dividir colunas incorretamente ou rejeitar pagamentos
válidos. Soluções permissivas demais, por outro lado, podem interpretar valores
ambíguos sem registrar a correção.

**Relação causal**

O contrato deixou de representar o produtor real. Parte dos eventos rejeitados e
da conferência manual existe porque consumidor e produtor seguem formatos
diferentes.

**Tratamento na limpeza**

O leitor aceita explicitamente o leiaute observado, converte dinheiro com
`Decimal` e registra cada normalização. Formatos desconhecidos não são inferidos.

### 7. Comparação textual exata produz falsos desencontros

**Gravidade:** média

**Natureza:** causa raiz de falsos positivos na conciliação.

**Evidências**

- O fluxo compara nome e processo exatamente como escritos
  ([ENUNCIADO.md, linha 17](data/raw/ENUNCIADO.md#L17)).
- `0023456-21.2020.8.26.0053` está pontuado no tribunal
  ([tribunal.csv, linha 3](data/raw/dados/tribunal.csv#L3)) e sem pontuação no Hub
  ([hub.csv, linha 3](data/raw/dados/hub.csv#L3)).
- `Município de São Paulo` no tribunal
  ([tribunal.csv, linha 2](data/raw/dados/tribunal.csv#L2)) corresponde a
  `MUNICIPIO DE SAO PAULO` no Hub
  ([hub.csv, linha 2](data/raw/dados/hub.csv#L2)).

**Impacto**

O mesmo processo ou ente pode parecer ausente, aumentando trabalho manual e
escondendo as divergências reais entre vários falsos positivos.

**Relação causal**

É uma falha do critério de junção, agravada pela codificação divergente do CSV.
Não explica os conflitos de R$ 30.000,00 versus R$ 31.000,00 ou `União` versus
`Município de Santos`, que continuam sendo conflitos reais.

**Tratamento na limpeza**

O processo é convertido para uma representação CNJ canônica. Para comparação,
o nome recebe uma chave sem diferença de caixa, acentos e espaços; o texto
original continua preservado para exibição e auditoria.

### 8. Banco não garante idempotência nem rastreabilidade

**Gravidade:** média, com efeito financeiro potencialmente crítico

**Natureza:** causa estrutural dos problemas 1 e 3.

**Evidências**

- `evento_id` é obrigatório, mas não é único
  ([schema.sql, linha 11](data/raw/schema.sql#L11)).
- `atualizado_em` não é armazenado.
- Não existem lote de importação, hash do arquivo, estado de processamento,
  motivo de rejeição ou histórico de versões.
- `numero_processo` usa `CHAR(20)`
  ([schema.sql, linha 3](data/raw/schema.sql#L3)), enquanto a representação CNJ
  pontuada documentada possui 25 caracteres.

**Impacto**

Mesmo que o script seja corrigido, o banco ainda permite inserir novamente o
mesmo evento. Depois da inserção, não é possível explicar qual arquivo originou o
registro, qual versão foi aplicada ou quais registros foram recusados.

**Relação causal**

O banco não atua como última barreira de integridade. A incompatibilidade do
número CNJ também incentiva representações diferentes entre integração e banco.

**Tratamento na limpeza**

A execução atual gera trilha de ocorrências e pendências fora do banco. A correção
definitiva exige constraints, lotes e `UPSERT`, detalhados na etapa de prevenção.

### 9. Datas de apresentação não possuem contrato documentado

**Gravidade:** média

**Natureza:** causa estrutural da ambiguidade de prazo.

**Evidências**

- `DOCUMENTACAO_TRIBUNAL.md` descreve apenas `pagamentos.json` e `tribunal.csv`.
- `apresentacoes.json` mistura datas simples, como `2025-04-02`
  ([linhas 2–5](data/raw/dados/apresentacoes.json#L2-L5)), e instantes com fuso,
  como `2025-04-02T23:30:00-03:00`
  ([linhas 14–17](data/raw/dados/apresentacoes.json#L14-L17)).

**Impacto**

Não está definido se horário deve ser descartado, convertido para o fuso do
tribunal ou interpretado no fuso do sistema. Perto de 2 de abril, essa decisão
pode deslocar o vencimento em um ano.

**Relação causal**

A ausência de contrato permite variação de tipo no mesmo campo e impede validar
se o Hub aplicou a regra jurídica esperada.

**Tratamento na limpeza**

Datas sem horário são preservadas como datas civis. Instantes precisam ter fuso e
são convertidos para `America/Sao_Paulo`. A escolha é explícita, testada e deve
ser confirmada com o tribunal.

### 10. Conferência manual no Excel pode modificar o insumo

**Gravidade:** média

**Natureza:** fator agravante dos problemas de formato e conciliação.

**Evidências**

O operador abre, confere e salva o CSV no Excel antes de comparar
([ENUNCIADO.md, linha 17](data/raw/ENUNCIADO.md#L17)).

**Impacto**

Abrir e salvar pode alterar codificação, delimitador, zeros à esquerda e formatos
numéricos. Também elimina a garantia de que o arquivo analisado é exatamente o
arquivo enviado pelo tribunal.

**Relação causal**

Não há evidência suficiente para afirmar que o Excel causou as anomalias deste
lote. O passo, porém, impede separar com segurança um defeito do tribunal de uma
alteração feita durante a operação.

**Tratamento na limpeza**

Os arquivos recebidos são tratados como somente leitura e possuem hashes SHA-256
registrados em `data/raw/SHA256SUMS`. Todo resultado é escrito em outra pasta.

## Resultado conciliado

| Processo | Valor de face usado | Pago líquido | Situação |
|---|---:|---:|---|
| `0012345-10.2019.8.26.0053` | R$ 45.000,00 | R$ 18.000,50 | Prazo divergente |
| `0023456-21.2020.8.26.0053` | R$ 30.000,00 | R$ 9.200,00 | Valor de face divergente |
| `0034567-32.2018.8.26.0405` | R$ 12.500,00 | R$ 0,00 | Conciliado |
| `0045678-43.2021.5.02.0011` | R$ 9.800,00 | R$ 3.000,00 | Ente devedor divergente |
| `0056789-54.2017.4.03.6100` | R$ 22.000,00 | R$ 0,00 | Ausente no tribunal e prazo a confirmar |
| `0067890-65.2016.8.26.0053` | R$ 7.000,00 | R$ 4.000,00 | Ausente no Hub |

Os valores de face acima seguem provisoriamente o tribunal quando o processo está
presente nele e o Hub quando ele é a única fonte. Essa escolha não resolve as
pendências de negócio; apenas permite produzir uma base operacional rastreável.

## Propostas de prevenção

### Processo operacional

1. **Preservar o arquivo recebido.** O anexo deve entrar diretamente em uma área
   somente leitura. Nome, origem, horário de recebimento, tamanho e SHA-256 devem
   ser registrados antes de qualquer interpretação.
2. **Eliminar o salvamento intermediário no Excel.** O operador pode consultar
   uma cópia ou um relatório, mas o arquivo usado pela importação deve ser o anexo
   original. Assim é possível atribuir um defeito ao produtor ou ao consumidor.
3. **Formalizar e versionar o contrato.** Tribunal e operação devem aprovar
   codificação, delimitador, casas decimais, tipos permitidos, fuso e semântica de
   atualização. Uma mudança de leiaute precisa gerar uma nova versão, não uma
   variação silenciosa dentro da versão 2.1.
4. **Automatizar a conciliação semanal.** O resultado deve separar:
   conciliados, diferenças apenas cosméticas, conflitos de negócio e registros
   presentes em somente uma fonte.
5. **Definir responsável e prazo para pendências.** Cada conflito precisa de
   responsável, estado, comentário e data de resolução. Pendência sem dono volta a
   ser um descarte silencioso com outro nome.
6. **Alertar pelo resultado, não apenas por falha técnica.** Um lote pode terminar
   como `concluido`, `concluido_com_pendencias` ou `falhou`. Eventos rejeitados,
   divergências novas ou ausência do arquivo esperado devem gerar alerta.
7. **Acompanhar indicadores.** No mínimo: lotes recebidos, atraso do último lote,
   registros aplicados, duplicados, substituídos, rejeitados e tempo das
   pendências abertas.

### Script de importação

O importador deve seguir uma sequência determinística:

1. calcular o SHA-256 e tentar criar o lote com uma chave idempotente formada por
   origem e hash;
2. se o lote já estiver concluído, encerrar com sucesso sem aplicar valores outra
   vez;
3. armazenar cada objeto JSON original antes de validá-lo;
4. normalizar somente representações conhecidas, preservando o valor de origem;
5. validar campos obrigatórios, processo, dinheiro, data, tipo e fuso;
6. agrupar por `evento_id` e selecionar a maior versão por `atualizado_em`;
7. tratar repetição idêntica como operação sem efeito;
8. colocar em pendência versões diferentes com o mesmo `atualizado_em`;
9. aplicar o evento com `INSERT ... ON CONFLICT`, condicionado a uma versão mais
   recente;
10. concluir o lote com contagens e enviar o resumo à operação.

Dinheiro deve usar decimal exato. O valor do evento deve continuar positivo; o
tipo define se seu efeito é positivo ou negativo. O total pago não deve ser um
acumulador incrementado pelo script, mas uma soma derivada dos eventos vigentes.

Cada registro pode falhar isoladamente sem interromper os demais, desde que a
falha seja persistida e comunicada. Erros do arquivo inteiro, como JSON inválido
ou cabeçalho desconhecido, devem falhar o lote: continuar nesse caso poderia
produzir uma importação estruturalmente incorreta.

Os testes automatizados devem cobrir, no mínimo:

- reexecução do mesmo arquivo;
- sobreposição entre arquivos de janelas de sete dias;
- duplicata exata e correção posterior;
- conflito no mesmo `atualizado_em`;
- pagamento e estorno;
- valores nulos, negativos e com formatos alternativos;
- processo com e sem pontuação;
- 2 e 3 de abril em diferentes fusos;
- CSV documentado e CSV efetivamente recebido;
- falha parcial seguida de nova execução.

### Banco de dados

A migração proposta está em
[`sql/001_prevent_data_quality_issues.sql`](sql/001_prevent_data_quality_issues.sql).
Ela implementa as seguintes barreiras:

- `evento_id` único na tabela de pagamentos;
- `atualizado_em` e lote de origem obrigatórios;
- lote identificado por origem e SHA-256;
- armazenamento do payload recebido, inclusive quando rejeitado;
- status e motivo de cada registro;
- processo no formato CNJ canônico de 25 caracteres;
- constraints para processo, ente e valores;
- data de apresentação separada de instante e prazo gerado pelo banco;
- total pago calculado por uma view, com estorno negativo;
- índices para consulta por processo, lote, estado e evento.

A migração aborta se encontrar `evento_id` duplicado ou processo legado que não
possa ser normalizado com segurança. Isso é intencional: migração de estrutura não
deve decidir qual pagamento apagar. Os conflitos devem passar primeiro pela
limpeza e por aprovação da operação.

Como o schema antigo não guarda `atualizado_em`, a migração associa os registros
existentes a um lote técnico e usa `criado_em` como marcador legado. Esse valor não
deve ser apresentado como horário fornecido pelo tribunal.

`data_apresentacao` permanece inicialmente opcional porque o schema atual não
possui essa informação. Depois do backfill conciliado, uma segunda migração deve
torná-la obrigatória caso todo precatório ativo realmente precise ter uma data.

### Entrada em produção

1. Fazer backup e extrair uma fotografia dos totais atuais.
2. Executar a limpeza em modo sombra, sem escrever no banco de produção.
3. Resolver as decisões bloqueadoras listadas abaixo.
4. Comparar os totais por processo e aprovar formalmente as correções.
5. Executar as validações iniciais da migração.
6. Migrar primeiro em homologação e testar reprocessamento e falha parcial.
7. Ativar o novo importador com monitoramento e possibilidade de retorno.
8. Manter a conciliação antiga apenas para conferência durante um período curto
   e depois retirá-la, evitando duas fontes operacionais permanentes.

## Dúvidas antes de colocar a limpeza em produção

### Para o tribunal

1. Qual é o leiaute vigente de fato? O CSV deve ser ISO-8859-1 com `;` e decimal
   brasileiro, ou o arquivo enviado está fora da versão 2.1?
2. `evento_id` é único globalmente, por tribunal ou apenas dentro de um arquivo?
3. Uma nova ocorrência do mesmo `evento_id` substitui integralmente a anterior?
   Pode haver exclusão ou cancelamento sem um evento de estorno?
4. Qual é a semântica oficial de `estorno`? Seu valor deve chegar positivo com o
   sinal definido pelo tipo?
5. Um `pagamento` negativo deve ser rejeitado ou significa um estorno enviado com
   tipo incorreto? Como recuperar o valor nulo de `ev-004`?
6. Qual fuso define a data jurídica de apresentação? Um instante em UTC deve ser
   convertido para o fuso do tribunal antes de aplicar o corte de 2 de abril?
7. A lista semanal é uma fotografia completa ou apenas um conjunto de alterações?
   A ausência de um processo significa exclusão?
8. Eventos podem chegar com mais de sete dias de atraso? Por quanto tempo um
   evento anterior ainda pode ser corrigido?
9. Os dígitos verificadores CNJ devem ser validados na integração? Os números
   fictícios deste case não passam nessa validação, por isso a limpeza atual valida
   a estrutura, mas não rejeita pelo dígito.

### Para a operação

1. Em conflitos cadastrais, qual sistema é a fonte oficial para ente devedor e
   valor de face? A precedência provisória dada ao tribunal está correta?
2. Qual é a decisão para o processo `0023456-21.2020.8.26.0053`: R$ 30.000,00 ou
   R$ 31.000,00?
3. Qual é o ente correto de `0045678-43.2021.5.02.0011`: `União` ou
   `Município de Santos`?
4. Por que `0056789-54.2017.4.03.6100` está somente no Hub e
   `0067890-65.2016.8.26.0053` somente no tribunal? Eles devem permanecer ativos?
5. O prazo deve usar `America/Sao_Paulo`? A data do Hub foi calculada antes ou
   depois de converter o instante para esse fuso?
6. Existem pagamentos históricos fora dos arquivos fornecidos? Qual total atual
   por processo deve ser usado como ponto de reconciliação?
7. Pagamento líquido negativo ou superior ao valor de face é permitido, ou deve
   abrir uma pendência?
8. Quem pode aprovar uma divergência e qual é o prazo esperado para resolvê-la?
9. Por quanto tempo arquivos originais, payloads e rejeições devem ser mantidos?
   Há requisitos de acesso ou proteção de dados para esses arquivos?
10. O operador precisa corrigir registros por uma interface, ou a correção deve
    sempre vir em um novo arquivo do tribunal?

### Decisões bloqueadoras

Antes da escrita em produção, considero obrigatório confirmar:

- autoridade para ente devedor e valor de face;
- semântica de versão do `evento_id`;
- sinal e representação de estornos;
- fuso usado no corte de 2 de abril;
- significado de ausência na lista semanal;
- destino dos três eventos de pagamento em quarentena;
- resolução dos dois conflitos cadastrais e dos dois processos presentes em
  apenas uma fonte.
