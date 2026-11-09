#!/bin/sh
# quick-eval demo in one line: two small local models (no account, no key) in a Hermes home of its own; yours is
# untouched. Installs what's missing: Hermes, Ollama, the models (~1.5 GB). Rerun anytime: it updates the plugin.
# Usage: curl -fsSL <raw url of this file> | sh   (env: QE_BRANCH, QE_DIR, QE_REPO, QE_DEMO_HOME, QE_NO_LAUNCH)
set -eu

branch=${QE_BRANCH:-quick-eval-ui}
dir=${QE_DIR:-$HOME/.cache/quick-eval-pr}
repo=${QE_REPO:-https://github.com/tikiverse/hermes-hackathon-2026}
home=${QE_DEMO_HOME:-$HOME/.hermes-quick-eval-demo}
PATH="$HOME/.local/bin:$PATH"

say() { printf '\n==> %s\n' "$*"; }

get_code() {
  [ -d "$dir" ] || git clone -q "$repo" "$dir"
  git -C "$dir" fetch -q origin "$branch"
  git -C "$dir" checkout -q -B "$branch" FETCH_HEAD
}

need_hermes() {
  command -v hermes >/dev/null && return
  say "Installing Hermes (official installer, setup questions skipped)"
  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash -s -- --skip-setup
}

need_ollama() {
  command -v ollama >/dev/null && return
  say "Installing Ollama"
  if command -v brew >/dev/null; then brew install ollama
  elif [ "$(uname)" = Linux ]; then curl -fsSL https://ollama.com/install.sh | sh
  else echo "Install Ollama from https://ollama.com/download, then rerun this line." >&2; exit 1; fi
}

start_ollama() {
  ollama list >/dev/null 2>&1 && return
  (ollama serve >/dev/null 2>&1 &)
  for _ in 1 2 3 4 5 6 7 8 9 10; do ollama list >/dev/null 2>&1 && return; sleep 1; done
  echo "Ollama did not start. Run 'ollama serve', then rerun this line." >&2; exit 1
}

pull_models() {
  for model in $(sed -n 's/^# pull: //p' "$dir/demo/config.yaml"); do ollama pull "$model"; done
}

setup_home() {
  mkdir -p "$home"
  [ -f "$home/config.yaml" ] || cp "$dir/demo/config.yaml" "$home/config.yaml"
  HERMES_HOME="$home" "$dir/scripts/link-plugins.sh" quick-eval </dev/null
}

launch() {
  say "Ready. Ask: What happened at Tiananmen Square in 1989?   Then: /quick-eval   (later: HERMES_HOME=$home hermes)"
  [ -n "${QE_NO_LAUNCH:-}" ] && return
  cd "$home" && HERMES_HOME="$home" exec hermes chat --ignore-rules </dev/tty
}

# why: under `curl | sh` stdin is this script; one call on the last line means sh has read it all before any
# step runs, so a step that reads stdin cannot eat the rest
main() { get_code; need_hermes; need_ollama; start_ollama; pull_models; setup_home; launch; }
main
