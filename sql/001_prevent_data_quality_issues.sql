BEGIN;

-- A migração não escolhe silenciosamente entre pagamentos já duplicados.
-- A limpeza deve ser executada e aprovada antes caso este bloco encontre dados.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pagamento
        GROUP BY evento_id
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION
            'Existem evento_id duplicados em pagamento; concilie-os antes da migração';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM precatorio
        WHERE btrim(numero_processo) !~ '^[0-9]{20}$'
    ) THEN
        RAISE EXCEPTION
            'Existem números de processo que não podem ser normalizados com segurança';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM precatorio
        WHERE btrim(ente_devedor) = '' OR valor_face <= 0
    ) THEN
        RAISE EXCEPTION
            'Existem precatórios com ente vazio ou valor de face não positivo';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pagamento
        WHERE btrim(evento_id) = ''
    ) THEN
        RAISE EXCEPTION
            'Existem pagamentos sem evento_id; corrija-os antes da migração';
    END IF;
END
$$;

CREATE TABLE importacao_lote (
    id                  BIGSERIAL PRIMARY KEY,
    origem              TEXT        NOT NULL,
    arquivo_nome        TEXT        NOT NULL,
    arquivo_sha256      CHAR(64),
    chave_idempotencia  TEXT        NOT NULL UNIQUE,
    status              TEXT        NOT NULL CHECK (
        status IN ('recebido', 'processando', 'concluido', 'concluido_com_pendencias', 'falhou')
    ),
    recebido_em         TIMESTAMPTZ NOT NULL DEFAULT now(),
    iniciado_em         TIMESTAMPTZ,
    concluido_em        TIMESTAMPTZ,
    total_registros     INTEGER     CHECK (total_registros >= 0),
    total_aplicados     INTEGER     CHECK (total_aplicados >= 0),
    total_pendentes     INTEGER     CHECK (total_pendentes >= 0),
    erro                TEXT,
    CHECK (
        arquivo_sha256 IS NULL
        OR arquivo_sha256 ~ '^[0-9a-f]{64}$'
    )
);

CREATE UNIQUE INDEX importacao_lote_origem_sha256_uidx
    ON importacao_lote (origem, arquivo_sha256)
    WHERE arquivo_sha256 IS NOT NULL;

CREATE TABLE pagamento_recebido (
    id                  BIGSERIAL PRIMARY KEY,
    importacao_lote_id  BIGINT      NOT NULL REFERENCES importacao_lote (id),
    registro_origem     INTEGER     NOT NULL CHECK (registro_origem > 0),
    evento_id           TEXT,
    payload             JSONB       NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    status              TEXT        NOT NULL CHECK (
        status IN ('pendente', 'aplicado', 'duplicado', 'substituido', 'rejeitado')
    ),
    motivo_codigo       TEXT,
    motivo_detalhe      TEXT,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (importacao_lote_id, registro_origem),
    CHECK (
        (status IN ('pendente', 'aplicado', 'duplicado', 'substituido'))
        OR motivo_codigo IS NOT NULL
    )
);

CREATE INDEX pagamento_recebido_evento_idx
    ON pagamento_recebido (evento_id);

CREATE INDEX pagamento_recebido_status_idx
    ON pagamento_recebido (status)
    WHERE status IN ('pendente', 'rejeitado');

-- Os dados anteriores à rastreabilidade ficam ligados a um lote técnico explícito.
INSERT INTO importacao_lote (
    origem,
    arquivo_nome,
    chave_idempotencia,
    status,
    iniciado_em,
    concluido_em
)
VALUES (
    'migracao',
    'dados-legados',
    'migracao:dados-legados',
    'concluido',
    now(),
    now()
);

ALTER TABLE precatorio
    ALTER COLUMN numero_processo TYPE VARCHAR(25)
    USING (
        substring(btrim(numero_processo), 1, 7)
        || '-'
        || substring(btrim(numero_processo), 8, 2)
        || '.'
        || substring(btrim(numero_processo), 10, 4)
        || '.'
        || substring(btrim(numero_processo), 14, 1)
        || '.'
        || substring(btrim(numero_processo), 15, 2)
        || '.'
        || substring(btrim(numero_processo), 17, 4)
    );

ALTER TABLE precatorio
    ADD CONSTRAINT precatorio_numero_processo_formato_ck
        CHECK (
            numero_processo ~
            '^[0-9]{7}-[0-9]{2}\.[0-9]{4}\.[0-9]\.[0-9]{2}\.[0-9]{4}$'
        ),
    ADD CONSTRAINT precatorio_ente_devedor_nao_vazio_ck
        CHECK (btrim(ente_devedor) <> ''),
    ADD CONSTRAINT precatorio_valor_face_positivo_ck
        CHECK (valor_face > 0),
    ADD COLUMN data_apresentacao DATE,
    ADD COLUMN prazo_pagamento DATE GENERATED ALWAYS AS (
        CASE
            WHEN data_apresentacao IS NULL THEN NULL
            WHEN data_apresentacao
                <= make_date(extract(year FROM data_apresentacao)::INTEGER, 4, 2)
            THEN make_date(
                extract(year FROM data_apresentacao)::INTEGER + 1,
                12,
                31
            )
            ELSE make_date(
                extract(year FROM data_apresentacao)::INTEGER + 2,
                12,
                31
            )
        END
    ) STORED;

COMMENT ON COLUMN precatorio.data_apresentacao IS
    'Data civil no fuso jurídico acordado; deve ser preenchida após o backfill validado';

ALTER TABLE pagamento
    ADD COLUMN atualizado_em TIMESTAMPTZ,
    ADD COLUMN importacao_lote_id BIGINT,
    ADD COLUMN alterado_em TIMESTAMPTZ NOT NULL DEFAULT now();

-- O horário real não existe no esquema legado. O criado_em é usado apenas como
-- marcador técnico e o lote de migração torna essa limitação auditável.
UPDATE pagamento
SET
    atualizado_em = criado_em,
    importacao_lote_id = (
        SELECT id
        FROM importacao_lote
        WHERE chave_idempotencia = 'migracao:dados-legados'
    );

ALTER TABLE pagamento
    ALTER COLUMN atualizado_em SET NOT NULL,
    ALTER COLUMN importacao_lote_id SET NOT NULL,
    ADD CONSTRAINT pagamento_evento_id_nao_vazio_ck
        CHECK (btrim(evento_id) <> ''),
    ADD CONSTRAINT pagamento_evento_id_uid UNIQUE (evento_id),
    ADD CONSTRAINT pagamento_importacao_lote_fk
        FOREIGN KEY (importacao_lote_id) REFERENCES importacao_lote (id);

CREATE INDEX pagamento_precatorio_pago_em_idx
    ON pagamento (precatorio_id, pago_em);

CREATE INDEX pagamento_importacao_lote_idx
    ON pagamento (importacao_lote_id);

-- O total é derivado dos eventos vigentes, evitando um acumulador que pode ser
-- incrementado duas vezes. Estorno permanece positivo na tabela e negativo na soma.
CREATE VIEW precatorio_total_pago AS
SELECT
    p.id AS precatorio_id,
    COALESCE(
        sum(
            CASE
                WHEN pg.tipo = 'pagamento' THEN pg.valor
                WHEN pg.tipo = 'estorno' THEN -pg.valor
                ELSE 0
            END
        ),
        0
    )::NUMERIC(15, 2) AS total_pago
FROM precatorio AS p
LEFT JOIN pagamento AS pg ON pg.precatorio_id = p.id
GROUP BY p.id;

COMMIT;

-- Exemplo da escrita idempotente que deve ser usada pelo importador depois de
-- inserir o payload em pagamento_recebido. Uma versão antiga nunca sobrescreve
-- a atual; igualdade de atualizado_em com payload diferente deve ir para pendência.
--
-- INSERT INTO pagamento (
--     precatorio_id,
--     evento_id,
--     tipo,
--     valor,
--     pago_em,
--     atualizado_em,
--     importacao_lote_id
-- )
-- VALUES ($1, $2, $3, $4, $5, $6, $7)
-- ON CONFLICT (evento_id) DO UPDATE
-- SET
--     precatorio_id = EXCLUDED.precatorio_id,
--     tipo = EXCLUDED.tipo,
--     valor = EXCLUDED.valor,
--     pago_em = EXCLUDED.pago_em,
--     atualizado_em = EXCLUDED.atualizado_em,
--     importacao_lote_id = EXCLUDED.importacao_lote_id,
--     alterado_em = now()
-- WHERE EXCLUDED.atualizado_em > pagamento.atualizado_em;
