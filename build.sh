#!/bin/sh
# The dashboard loads a single bundle, so index.js = ui.js + dashboard registration.
# (standalone.py serves ui.js directly.) Run after editing ui.js.
cd "$(dirname "$0")/dashboard/dist" && cat ui.js _dashboard.js > index.js && echo "built index.js"
