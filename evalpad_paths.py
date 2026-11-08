"""why: one place decides where Hermes state, eval files and SQL live."""
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


def hermes_home():
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def evals_dir():
    path = Path(os.environ.get("EVALPAD_DIR") or hermes_home() / "evals")
    path.mkdir(parents=True, exist_ok=True)
    return path


def evals_path():
    return evals_dir() / "evals.jsonl"


def state_db_path():
    return Path(os.environ.get("EVALPAD_STATE_DB") or hermes_home() / "state.db")


def sql(name):
    return (HERE / "sql" / f"{name}.sql").read_text(encoding="utf-8")


def dotenv_value(name):
    env = hermes_home() / ".env"
    lines = env.read_text(encoding="utf-8", errors="ignore").splitlines() if env.exists() else []
    hits = [line.split("=", 1)[1] for line in lines if line.strip().startswith(name + "=")]
    return hits[0].strip().strip("'\"") if hits else None


def read_key(name):
    return os.environ.get(name) or dotenv_value(name)
