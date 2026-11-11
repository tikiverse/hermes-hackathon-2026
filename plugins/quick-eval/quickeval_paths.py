"""why: one place decides where Hermes state, eval files and SQL live."""
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


def hermes_home():
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def evals_dir():
    path = Path(os.environ.get("QUICKEVAL_DIR") or hermes_home() / "evals")
    path.mkdir(parents=True, exist_ok=True)
    return path


def evals_path():
    return evals_dir() / "evals.jsonl"


def state_db_path():
    return Path(os.environ.get("QUICKEVAL_STATE_DB") or hermes_home() / "state.db")


def sql(name):
    return (HERE / "sql" / f"{name}.sql").read_text(encoding="utf-8")

