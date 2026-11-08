#!/usr/bin/env bash
# Symlink plugins from this repo into your Hermes home and enable them.
# Usage: scripts/link-plugins.sh [plugin ...]   (defaults to every plugin in plugins/)
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
dest="${HERMES_HOME:-$HOME/.hermes}/plugins"
mkdir -p "$dest"

if [ $# -eq 0 ]; then
  set -- $(cd "$repo/plugins" && for d in */; do [ -f "$d/plugin.yaml" ] && echo "${d%/}"; done)
fi

for name in "$@"; do
  src="$repo/plugins/$name"
  [ -f "$src/plugin.yaml" ] || { echo "no plugin at $src" >&2; exit 1; }
  if [ -e "$dest/$name" ] && [ ! -L "$dest/$name" ]; then
    echo "skipping $name: $dest/$name exists and is not a symlink" >&2
    continue
  fi
  ln -sfn "$src" "$dest/$name"
  (cd "$repo" && uv run hermes plugins enable "$name")
  echo "linked $name -> $dest/$name"
done
