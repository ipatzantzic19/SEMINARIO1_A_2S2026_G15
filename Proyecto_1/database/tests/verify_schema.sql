\set ON_ERROR_STOP on
BEGIN;

DO $$
DECLARE
    actual integer;
BEGIN
    SELECT count(*) INTO actual FROM schema_migrations;
    IF actual < 3 THEN
        RAISE EXCEPTION 'Se esperaban al menos 3 migraciones; encontradas: %', actual;
    END IF;

    SELECT count(*) INTO actual
    FROM pg_indexes
    WHERE schemaname = 'public'
      AND indexname IN (
          'friend_requests_one_pending_pair_idx',
          'posts_author_created_id_idx',
          'messages_conversation_created_id_idx'
      );
    IF actual <> 3 THEN
        RAISE EXCEPTION 'Faltan índices críticos; encontrados: % de 3', actual;
    END IF;
END $$;

INSERT INTO users (id, cognito_sub, email, full_name, dpi)
VALUES
    ('10000000-0000-4000-8000-000000000001', 'verify-a', 'verify-a@example.invalid', 'Verify A', '9000000000001'),
    ('10000000-0000-4000-8000-000000000002', 'verify-b', 'verify-b@example.invalid', 'Verify B', '9000000000002');

INSERT INTO friend_requests (requester_id, addressee_id)
VALUES (
    '10000000-0000-4000-8000-000000000001',
    '10000000-0000-4000-8000-000000000002'
);

DO $$
BEGIN
    BEGIN
        INSERT INTO friend_requests (requester_id, addressee_id)
        VALUES (
            '10000000-0000-4000-8000-000000000002',
            '10000000-0000-4000-8000-000000000001'
        );
        RAISE EXCEPTION 'La solicitud pendiente inversa duplicada fue aceptada';
    EXCEPTION
        WHEN unique_violation THEN NULL;
    END;
END $$;

ROLLBACK;
SELECT 'schema verification passed' AS result;
