#!/bin/sh
# why: put the pinned catalog entry on a branch of a hermes-agent fork, the same way every time. Opens no PR:
# the repo owner opens it from the printed compare link (catalog rule 5). Rerun with a new sha to re-pin.
# Usage: scripts/catalog-push.sh <40-hex sha>      (env: QE_FORK_OWNER default: the gh login)
set -eu

sha=${1:?usage: catalog-push.sh <40-hex sha>}
upstream=NousResearch/hermes-agent
branch=plugin-catalog/quick-eval
path=plugin-catalog/quick-eval.yaml
here=$(cd "$(dirname "$0")" && pwd)
owner=${QE_FORK_OWNER:-$(gh api user --jq .login)}
fork=$owner/hermes-agent
entry=$(mktemp)
trap 'rm -f "$entry"' EXIT

uv run python -I "$here/catalog_entry.py" "$sha" "$entry"

gh repo fork "$upstream" --clone=false >/dev/null 2>&1 || true
gh api "repos/$fork" --jq .full_name >/dev/null

if ! gh api "repos/$fork/git/ref/heads/$branch" >/dev/null 2>&1; then
  base=$(gh api "repos/$upstream/commits/main" --jq .sha)
  gh api "repos/$fork/git/refs" -f ref="refs/heads/$branch" -f sha="$base" >/dev/null
fi

old=$(gh api "repos/$fork/contents/$path?ref=$branch" --jq .sha 2>/dev/null || true)
set -- -X PUT "repos/$fork/contents/$path" -f message="plugin-catalog: add quick-eval (Plugin Hackathon entry)" \
  -f content="$(base64 < "$entry" | tr -d '\n')" -f branch="$branch"
[ -n "$old" ] && set -- "$@" -f sha="$old"
gh api "$@" --jq .commit.html_url

echo "compare: https://github.com/$upstream/compare/main...$owner:hermes-agent:$branch"
