#!/bin/sh
# Link this repo's plugins into HERMES_HOME, seed a demo config on first run, then start the command.
set -eu

mkdir -p "$HERMES_HOME/plugins"
for dir in /app/plugins/*/; do
  [ -f "$dir/plugin.yaml" ] && ln -sfn "${dir%/}" "$HERMES_HOME/plugins/$(basename "$dir")"
done

if [ ! -f "$HERMES_HOME/config.yaml" ]; then
  cp /app/docker/config.yaml "$HERMES_HOME/config.yaml"
  echo "Created $HERMES_HOME/config.yaml from the demo config."
fi

exec "$@"
