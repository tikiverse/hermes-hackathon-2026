#!/bin/sh
# Install quick-eval from a branch of this repo into Hermes, without touching your own clone. Safe to rerun:
# a rerun fetches the branch's latest push. Usage: sh try-branch.sh [branch]   (env: QE_DIR, QE_REPO)
set -eu

branch=${1:-quick-eval-ui}
dir=${QE_DIR:-$HOME/.cache/quick-eval-pr}
repo=${QE_REPO:-https://github.com/tikiverse/hermes-hackathon-2026}

[ -d "$dir" ] || git clone -q "$repo" "$dir"
git -C "$dir" fetch -q origin "$branch"
git -C "$dir" checkout -q -B "$branch" FETCH_HEAD
"$dir/scripts/link-plugins.sh" quick-eval
echo "Installed. Next: run hermes (restart it if open), ask anything, then /quick-eval. /quick-eval open shows the review page."
