#!/bin/sh
# quick-eval demo: needs Hermes + Ollama + 2 small models (README "Try it"). Installs nothing itself.
# Sets up a Hermes home of its own (yours untouched) with this branch's plugin, then opens Hermes. Rerun anytime.
# Usage: curl -fsSL <raw url of this file> | sh   (env: QE_BRANCH, QE_DIR, QE_REPO, QE_DEMO_HOME, QE_NO_LAUNCH)
set -eu

branch=${QE_BRANCH:-quick-eval-ui}
dir=${QE_DIR:-$HOME/.cache/quick-eval-pr}
repo=${QE_REPO:-https://github.com/tikiverse/hermes-hackathon-2026}
home=${QE_DEMO_HOME:-$HOME/.hermes-quick-eval-demo}
PATH="$HOME/.local/bin:$PATH"

say() { printf '\n==> %s\n' "$*"; }
missing() { echo "Missing $1. Run this, then rerun the line:  $2" >&2; exit 1; }

need_tools() {
  command -v hermes >/dev/null || missing Hermes "curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash -s -- --skip-setup"
  command -v ollama >/dev/null || missing Ollama "https://ollama.com/download"
  ollama list >/dev/null 2>&1 || missing "a running Ollama" "open the Ollama app, or: ollama serve"
}

get_code() {
  [ -d "$dir" ] || git clone -q "$repo" "$dir"
  git -C "$dir" fetch -q origin "$branch"
  git -C "$dir" checkout -q -B "$branch" FETCH_HEAD
}

need_models() {
  for model in $(sed -n 's/^# pull: //p' "$dir/demo/config.yaml"); do
    ollama list | grep -q "^$model " || missing "model $model" "ollama pull $model"
  done
}

setup_home() {
  mkdir -p "$home"
  [ -f "$home/config.yaml" ] || cp "$dir/demo/config.yaml" "$home/config.yaml"
  HERMES_HOME="$home" "$dir/scripts/link-plugins.sh" quick-eval </dev/null >/dev/null
}

launch() {
  say "Ready. Ask: What happened at Tiananmen Square in 1989?   Then: /quick-eval   (later: HERMES_HOME=$home hermes)"
  [ -n "${QE_NO_LAUNCH:-}" ] && return
  cd "$home" && HERMES_HOME="$home" exec hermes chat --ignore-rules </dev/tty
}

# why: under `curl | sh` stdin is this script; one call on the last line means sh has read it all before any step runs
main() { need_tools; get_code; need_models; setup_home; launch; }
main
