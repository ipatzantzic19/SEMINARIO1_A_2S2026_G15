-- Variables psql requeridas: user_id, friend_id, limit,
-- cursor_created_at y cursor_id.
SELECT m.id, m.sender_id, m.recipient_id, m.content, m.created_at, m.read_at
FROM messages m
WHERE LEAST(m.sender_id, m.recipient_id) = LEAST(:'user_id'::uuid, :'friend_id'::uuid)
  AND GREATEST(m.sender_id, m.recipient_id) = GREATEST(:'user_id'::uuid, :'friend_id'::uuid)
  AND (m.created_at, m.id) < (
      :'cursor_created_at'::timestamptz,
      :'cursor_id'::uuid
  )
ORDER BY m.created_at DESC, m.id DESC
LIMIT :'limit'::integer;
