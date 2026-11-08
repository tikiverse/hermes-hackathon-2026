import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SCHEMA = """
CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, model TEXT, title TEXT, started_at REAL,
  last_activity_at REAL, message_count INTEGER, system_prompt TEXT);
CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT,
  tool_call_id TEXT, tool_calls TEXT, tool_name TEXT, timestamp REAL, finish_reason TEXT, reasoning TEXT,
  active INTEGER DEFAULT 1);
"""


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        os.environ["EVALPAD_DIR"] = str(d / "evals")
        os.environ["EVALPAD_STATE_DB"] = str(d / "state.db")
        os.environ["HERMES_HOME"] = str(d)
        c = sqlite3.connect(d / "state.db")
        c.executescript(SCHEMA)
        c.execute("INSERT INTO sessions VALUES ('s1','cli','m1','Hello',100,200,5,'sys')")
        tc = json.dumps([{"id": "t1", "function": {"name": "web_search", "arguments": '{"q": "cats"}'}}])
        rows = [
            ("s1", "user", "What is 2+2?", None, None, None, 101),
            ("s1", "assistant", "4", None, None, None, 102),
            ("s1", "user", "Search cats", None, None, None, 103),
            ("s1", "assistant", "", None, tc, None, 104),
            ("s1", "tool", '{"hits": 3}', "t1", None, "web_search", 105),
            ("s1", "assistant", "Found 3 hits.", None, None, None, 106),
        ]
        c.executemany(
            "INSERT INTO messages (session_id, role, content, tool_call_id, tool_calls, tool_name, timestamp) VALUES (?,?,?,?,?,?,?)",
            rows,
        )
        c.commit()
        c.close()
        import evalpad_core as core

        self.core = core

    def tearDown(self):
        self.tmp.cleanup()

    def test_sessions_listed(self):
        s = self.core.list_sessions()
        self.assertEqual([x["id"] for x in s], ["s1"])

    def test_turns_group_tools(self):
        t = self.core.get_turns("s1")["turns"]
        self.assertEqual(len(t), 2)
        self.assertEqual(t[0]["response"], "4")
        self.assertEqual(t[1]["response"], "Found 3 hits.")
        self.assertEqual(t[1]["tools"][0]["name"], "web_search")
        self.assertEqual(t[1]["tools"][0]["arguments"], {"q": "cats"})
        self.assertEqual(t[1]["tools"][0]["result"], {"hits": 3})

    def test_eval_roundtrip_and_dedupe(self):
        turn = self.core.get_turns("s1")["turns"][0]
        base = {"session_id": "s1", "message_id": turn["message_id"], "prompt": turn["prompt"], "response": turn["response"]}
        a = self.core.create_eval({**base, "verdict": "pass", "score": 5, "tags": ["great"]})
        b = self.core.create_eval({**base, "verdict": "fail", "score": 2})
        self.assertEqual(a["id"], b["id"])  # same turn -> update, not duplicate
        self.assertEqual(len(self.core.list_evals()), 1)
        self.assertEqual(self.core.list_evals()[0]["verdict"], "fail")
        self.assertTrue(self.core.get_turns("s1")["turns"][0]["evaluated"])
        self.core.delete_eval(a["id"])
        self.assertEqual(self.core.list_evals(), [])

    def test_validation(self):
        with self.assertRaises(ValueError):
            self.core.create_eval({"score": 9})
        with self.assertRaises(ValueError):
            self.core.create_eval({"verdict": "maybe"})

    def test_stats_and_export(self):
        self.core.create_eval({"message_id": 1, "session_id": "s1", "verdict": "pass", "score": 4})
        self.core.create_eval({"message_id": 2, "session_id": "s1", "verdict": "fail", "score": 2})
        s = self.core.stats()
        self.assertEqual(s["total"], 2)
        self.assertAlmostEqual(s["pass_rate"], 0.5)
        lines = self.core.export_jsonl().strip().splitlines()
        self.assertEqual(len(lines), 2)
        json.loads(lines[0])

    def test_torn_line_tolerated(self):
        self.core.create_eval({"message_id": 1, "session_id": "s1"})
        with open(self.core.evals_path(), "a") as f:
            f.write('{"broken\n')
        self.assertEqual(len(self.core.list_evals()), 1)

    def test_dispatcher(self):
        st, body = self.core.handle("GET", "/sessions/s1/turns", {}, None)
        self.assertEqual(st, 200)
        self.assertEqual(len(body["turns"]), 2)
        st, _ = self.core.handle("GET", "/sessions/nope/turns", {}, None)
        self.assertEqual(st, 404)
        st, body = self.core.handle("POST", "/compare", {}, {"prompt": "hi", "model": "x", "base_url": "http://127.0.0.1:1"})
        self.assertIn(st, (400, 502))  # no key configured -> clean error, never a crash

    def test_slash_command_parse(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("evalpad_pkg", Path(__file__).resolve().parent.parent / "__init__.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod._parse("good nice one"), ("pass", 5, "nice one"))
        self.assertEqual(mod._parse("bad"), ("fail", 1, ""))
        self.assertEqual(mod._parse("3 meh"), (None, 3, "meh"))
        out = mod._eval_command("good great")
        self.assertIn("saved (pass)", out)
        self.assertEqual(self.core.list_evals()[0]["response"], "Found 3 hits.")


if __name__ == "__main__":
    unittest.main()
