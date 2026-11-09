#!/bin/sh
# In the demo image: seed the Hermes home, link quick-eval, pull the models into the Ollama container, start chat.
set -eu
mkdir -p "$HERMES_HOME"
[ -f "$HERMES_HOME/config.yaml" ] || cp /app/demo/config.yaml "$HERMES_HOME/config.yaml"
/app/scripts/link-plugins.sh quick-eval >/dev/null
for model in $(sed -n 's/^# pull: //p' /app/demo/config.yaml); do
  echo "==> Model $model (first run downloads it)"
  curl -fsS http://localhost:11434/api/pull -d "{\"model\":\"$model\",\"stream\":false}" >/dev/null
done
echo "==> Ready. Ask: What happened at Tiananmen Square in 1989?   Then: /quick-eval   Quit: /exit"
cd "$HERMES_HOME"
exec hermes chat --ignore-rules "$@"
