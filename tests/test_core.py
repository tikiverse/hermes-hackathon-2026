import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import quickeval_compare  # noqa: E402
import quickeval_routes as routes  # noqa: E402
import quickeval_sessions as sessions  # noqa: E402
import quickeval_store as store  # noqa: E402


def load_plugin():
    spec = importlib.util.spec_from_file_location("quickeval_pkg", ROOT / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        os.environ.update(QUICKEVAL_DIR=str(tmp / "evals"), QUICKEVAL_STATE_DB=str(tmp / "state.db"),
                          HERMES_HOME=str(tmp))
        conn = sqlite3.connect(tmp / "state.db")
        conn.executescript((ROOT / "tests" / "seed.sql").read_text())
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_sessions_listed(self):
        self.assertEqual([s["id"] for s in sessions.list_sessions()], ["s1"])

    def test_turns_group_tools(self):
        turns = sessions.get_turns("s1")["turns"]
        self.assertEqual([t["response"] for t in turns], ["4", "Found 3 hits."])
        call = turns[1]["tools"][0]
        self.assertEqual((call["name"], call["arguments"], call["result"]), ("web_search", {"q": "cats"}, {"hits": 3}))

    def test_eval_roundtrip_and_dedupe(self):
        turn = sessions.get_turns("s1")["turns"][0]
        base = {"session_id": "s1", "message_id": turn["message_id"], "prompt": turn["prompt"]}
        first = store.create_eval({**base, "verdict": "pass", "score": 5, "tags": ["great"]})
        second = store.create_eval({**base, "verdict": "fail", "score": 2})
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(store.list_evals()), 1)
        self.assertEqual(store.list_evals()[0]["verdict"], "fail")
        self.assertTrue(sessions.get_turns("s1")["turns"][0]["evaluated"])
        store.delete_eval(first["id"])
        self.assertEqual(store.list_evals(), [])

    def test_validation(self):
        with self.assertRaises(ValueError):
            store.create_eval({"score": 9})
        with self.assertRaises(ValueError):
            store.create_eval({"verdict": "maybe"})

    def test_stats_and_export(self):
        store.create_eval({"message_id": 1, "session_id": "s1", "verdict": "pass", "score": 4})
        store.create_eval({"message_id": 2, "session_id": "s1", "verdict": "fail", "score": 2})
        self.assertEqual(store.stats()["total"], 2)
        self.assertAlmostEqual(store.stats()["pass_rate"], 0.5)
        lines = store.export_jsonl().strip().splitlines()
        self.assertEqual(len(lines), 2)
        json.loads(lines[0])

    def test_torn_line_tolerated(self):
        store.create_eval({"message_id": 1, "session_id": "s1"})
        with open(store.paths.evals_path(), "a") as handle:
            handle.write('{"broken\n')
        self.assertEqual(len(store.list_evals()), 1)

    def test_dispatcher(self):
        status, body = routes.handle("GET", "/sessions/s1/turns", {}, None)
        self.assertEqual((status, len(body["turns"])), (200, 2))
        self.assertEqual(routes.handle("GET", "/sessions/nope/turns", {}, None)[0], 404)
        self.assertEqual(routes.handle("GET", "/nothing", {}, None)[0], 404)
        self.assertEqual(routes.handle("POST", "/evals", {}, {"score": 9})[0], 400)

    def test_compare_without_key_is_a_clean_error(self):
        os.environ.pop("QUICKEVAL_TEST_KEY", None)
        body = {"prompt": "hi", "model": "x", "base_url": "http://127.0.0.1:1", "api_key_env": "QUICKEVAL_TEST_KEY"}
        with self.assertRaises(ValueError):
            quickeval_compare.compare(body)

    def test_slash_command(self):
        plugin = load_plugin()
        self.assertEqual(plugin.parse_args("good nice one"), ("pass", 5, "nice one"))
        self.assertEqual(plugin.parse_args("bad"), ("fail", 1, ""))
        self.assertEqual(plugin.parse_args("3 meh"), (None, 3, "meh"))
        self.assertEqual(plugin.parse_args("just a note"), (None, None, "just a note"))
        self.assertIn("saved (pass)", plugin.eval_command("good great"))
        self.assertEqual(store.list_evals()[0]["response"], "Found 3 hits.")


if __name__ == "__main__":
    unittest.main()
