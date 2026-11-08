SELECT id, source, model, title, started_at, last_activity_at, message_count
FROM sessions
WHERE message_count > 0
  AND (:q = '' OR title LIKE '%' || :q || '%' OR id LIKE '%' || :q || '%' OR model LIKE '%' || :q || '%')
ORDER BY COALESCE(last_activity_at, started_at) DESC
LIMIT :limit
