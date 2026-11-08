CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, model TEXT, title TEXT, started_at REAL,
  last_activity_at REAL, message_count INTEGER, system_prompt TEXT);
CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT,
  tool_call_id TEXT, tool_calls TEXT, tool_name TEXT, timestamp REAL, finish_reason TEXT, reasoning TEXT,
  active INTEGER DEFAULT 1);
INSERT INTO sessions VALUES ('s1', 'cli', 'm1', 'Hello', 100, 200, 5, 'sys');
INSERT INTO messages (session_id, role, content, timestamp) VALUES ('s1', 'user', 'What is 2+2?', 101);
INSERT INTO messages (session_id, role, content, timestamp) VALUES ('s1', 'assistant', '4', 102);
INSERT INTO messages (session_id, role, content, timestamp) VALUES ('s1', 'user', 'Search cats', 103);
INSERT INTO messages (session_id, role, content, tool_calls, timestamp) VALUES ('s1', 'assistant', '',
  '[{"id": "t1", "function": {"name": "web_search", "arguments": "{\"q\": \"cats\"}"}}]', 104);
INSERT INTO messages (session_id, role, content, tool_call_id, tool_name, timestamp)
  VALUES ('s1', 'tool', '{"hits": 3}', 't1', 'web_search', 105);
INSERT INTO messages (session_id, role, content, timestamp) VALUES ('s1', 'assistant', 'Found 3 hits.', 106);
