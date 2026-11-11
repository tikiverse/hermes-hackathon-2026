INSERT INTO sessions VALUES (:id, 'cli', :model, :title, :ts, :ts, 2, 'sys');
INSERT INTO messages (session_id, role, content, timestamp) VALUES (:id, 'user', :prompt, :ts);
INSERT INTO messages (session_id, role, content, timestamp) VALUES (:id, 'assistant', 'ok', :ts);
