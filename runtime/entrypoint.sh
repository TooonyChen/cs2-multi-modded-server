#!/bin/sh
set -eu
# Initialize only volume roots; server containers cannot write /base.
mkdir -p /control /instance
chown 10001:10001 /control /instance
# Operator-authored instance inputs may come from root or a private umask (0700).
# Hand them to the runtime user; symlinks are left alone and rejected by the runtime.
for input in /instance/instance.json /instance/overlay; do
    if [ -e "$input" ] && [ ! -L "$input" ]; then
        chown -hR 10001:10001 "$input"
        chmod -R u+rwX "$input"
    fi
done
if [ "$1" = updater ]; then
    mkdir -p /base
    chown 10001:10001 /base
fi
exec runuser -u fleet -- python3 -u /app/runtime.py "$@"
