#!/bin/sh
set -eu
# Initialize only volume roots; server containers cannot write /base.
mkdir -p /control /instance
chown 10001:10001 /control /instance
if [ "$1" = updater ]; then
    mkdir -p /base
    chown 10001:10001 /base
fi
exec runuser -u fleet -- python3 -u /app/runtime.py "$@"
