#!/bin/sh
# quick-eval demo in one line, all inside Docker: Hermes plus two small local models (~1.5 GB, CPU), no account, no key.
# Nothing is installed on your machine. Remove every trace: same line with `QE_CLEAN=1 sh` at the end.
# Usage: curl -fsSL <raw url of this file> | sh   (env: QE_SRC = build source, QE_CLEAN = remove the demo, QE_TTY = chat input)
set -eu

src=${QE_SRC:-https://github.com/tikiverse/hermes-hackathon-2026.git#quick-eval-ui}
image=quick-eval-demo
ollama=quick-eval-ollama
models=quick-eval-models
home=quick-eval-home
url=https://raw.githubusercontent.com/tikiverse/hermes-hackathon-2026/quick-eval-ui/scripts/demo.sh

say() { printf '\n==> %s\n' "$*"; }

need_docker() {
  docker info >/dev/null 2>&1 && return
  echo "Needs Docker running: https://docs.docker.com/get-docker/ then rerun this line." >&2; exit 1
}

clean() {
  docker rm -f "$ollama" >/dev/null 2>&1 || true
  docker volume rm -f "$models" "$home" >/dev/null
  docker rmi -f "$image" >/dev/null 2>&1 || true
  say "Removed the demo: image, container, volumes."
}

build() {
  say "Building the Hermes image (first run takes a few minutes)"
  docker build -q -t "$image" "$src" >/dev/null
}

start_ollama() {
  docker ps -q -f name="^$ollama$" | grep -q . && return
  docker run -d --rm --name "$ollama" -v "$models:/root/.ollama" ollama/ollama:0.40.11 >/dev/null
}

chat() {
  docker run -it --rm --network "container:$ollama" -v "$home:/data/hermes" "$image" <"${QE_TTY:-/dev/tty}"
}

stop_ollama() { docker stop "$ollama" >/dev/null 2>&1 || true; }

# why: under `curl | sh` stdin is this script; one call on the last line means sh has read it all before any step runs
main() {
  need_docker
  [ -n "${QE_CLEAN:-}" ] && { clean; return; }
  build; start_ollama; chat || true; stop_ollama
  say "Rerun anytime. Remove everything: curl -fsSL $url | QE_CLEAN=1 sh"
}
main
