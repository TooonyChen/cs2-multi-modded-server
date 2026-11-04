FROM registry.gitlab.steamos.cloud/steamrt/steamrt4/platform:latest-container-runtime-depot
LABEL org.opencontainers.image.source="https://github.com/TooonyChen/cs2-multi-modded-server" \
      org.opencontainers.image.licenses="LGPL-3.0-only"
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates curl lib32gcc-s1 lib32stdc++6 lib32z1 util-linux tini && rm -rf /var/lib/apt/lists/*
RUN groupadd -g 10001 fleet && useradd -u 10001 -g fleet -m fleet && mkdir /steamcmd && curl -fsSL https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz | tar xz -C /steamcmd && chown -R fleet:fleet /steamcmd
COPY LICENSE docs/UPSTREAM.md /usr/share/doc/cs2-fleet/
COPY runtime/runtime.py runtime/rcon_client.py runtime/entrypoint.sh /app/
ENTRYPOINT ["tini", "--", "sh", "/app/entrypoint.sh"]
CMD ["server"]
