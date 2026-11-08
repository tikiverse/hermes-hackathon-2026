SELECT id, role, content, tool_call_id, tool_calls, tool_name, timestamp, finish_reason, reasoning
FROM messages
WHERE session_id = ? AND COALESCE(active, 1) = 1
ORDER BY id
