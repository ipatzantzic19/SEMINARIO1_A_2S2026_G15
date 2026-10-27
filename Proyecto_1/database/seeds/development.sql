BEGIN;

INSERT INTO users (
    id, cognito_sub, email, full_name, dpi, profile_image_key, face_reference_key
) VALUES
    (
        '00000000-0000-4000-8000-000000000101',
        '00000000-0000-4000-8000-0000000000a1',
        'alice@example.invalid',
        'Alice',
        '1000000000001',
        'Fotos_Perfil/public/00000000-0000-4000-8000-0000000000a1/avatar-initial-v1.png',
        'Fotos_Perfil/references/00000000-0000-4000-8000-0000000000a1/reference.webp'
    ),
    (
        '00000000-0000-4000-8000-000000000102',
        '00000000-0000-4000-8000-0000000000b2',
        'bob@example.invalid',
        'Bob',
        '1000000000002',
        'Fotos_Perfil/public/00000000-0000-4000-8000-0000000000b2/avatar-initial-v1.png',
        'Fotos_Perfil/references/00000000-0000-4000-8000-0000000000b2/reference.webp'
    )
ON CONFLICT (id) DO NOTHING;

INSERT INTO friend_requests (
    id, requester_id, addressee_id, status, responded_at
) VALUES (
    '00000000-0000-4000-8000-000000000201',
    '00000000-0000-4000-8000-000000000101',
    '00000000-0000-4000-8000-000000000102',
    'accepted',
    CURRENT_TIMESTAMP
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO friendships (user_low_id, user_high_id, request_id)
VALUES (
    '00000000-0000-4000-8000-000000000101',
    '00000000-0000-4000-8000-000000000102',
    '00000000-0000-4000-8000-000000000201'
)
ON CONFLICT (user_low_id, user_high_id) DO NOTHING;

INSERT INTO posts (id, author_id, description, image_key)
VALUES (
    '00000000-0000-4000-8000-000000000301',
    '00000000-0000-4000-8000-000000000101',
    'Publicación de prueba compartida por ambos backends.',
    'Fotos_Publicadas/00000000-0000-4000-8000-0000000000a1/post-001.webp'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO post_labels (post_id, normalized_label, source_label, confidence)
VALUES (
    '00000000-0000-4000-8000-000000000301',
    'naturaleza',
    'Nature',
    98.50
)
ON CONFLICT (post_id, normalized_label) DO NOTHING;

INSERT INTO comments (id, post_id, author_id, content)
VALUES (
    '00000000-0000-4000-8000-000000000401',
    '00000000-0000-4000-8000-000000000301',
    '00000000-0000-4000-8000-000000000102',
    'Comentario de prueba de Bob.'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO messages (id, sender_id, recipient_id, content)
VALUES (
    '00000000-0000-4000-8000-000000000501',
    '00000000-0000-4000-8000-000000000101',
    '00000000-0000-4000-8000-000000000102',
    'Mensaje persistido para validar el chat entre instancias.'
)
ON CONFLICT (id) DO NOTHING;

COMMIT;
