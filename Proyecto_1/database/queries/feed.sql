-- Variables psql requeridas: user_id, limit, cursor_created_at, cursor_id.
-- Para la primera página use cursor_created_at=infinity y
-- cursor_id=ffffffff-ffff-ffff-ffff-ffffffffffff.
WITH visible_authors AS (
    SELECT :'user_id'::uuid AS user_id
    UNION
    SELECT CASE
        WHEN f.user_low_id = :'user_id'::uuid THEN f.user_high_id
        ELSE f.user_low_id
    END
    FROM friendships f
    WHERE :'user_id'::uuid IN (f.user_low_id, f.user_high_id)
)
SELECT p.id, p.author_id, p.description, p.image_key, p.created_at
FROM posts p
JOIN visible_authors va ON va.user_id = p.author_id
WHERE (p.created_at, p.id) < (
    :'cursor_created_at'::timestamptz,
    :'cursor_id'::uuid
)
ORDER BY p.created_at DESC, p.id DESC
LIMIT :'limit'::integer;
