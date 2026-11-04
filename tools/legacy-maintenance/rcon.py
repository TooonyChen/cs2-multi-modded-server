#!/usr/bin/env python3
"""Local-only RCON; credentials read in memory from the existing container."""
import json, re, socket, struct, subprocess, sys


def command(text):
    info = json.loads(subprocess.check_output(['docker','inspect','cs2-modded-server']))[0]
    env = dict(v.split('=', 1) for v in info['Config']['Env'] if '=' in v)
    password = env.get('RCON_PASSWORD', '')
    if not password:
        raise RuntimeError('No configured RCON password')
    def send(sock, ident, kind, value):
        body = struct.pack('<ii', ident, kind) + value.encode() + b'\0\0'
        sock.sendall(struct.pack('<i', len(body)) + body)
    def recv(sock):
        def exact(n):
            out = b''
            while len(out) < n:
                part = sock.recv(n-len(out))
                if not part: raise RuntimeError('RCON closed')
                out += part
            return out
        n = struct.unpack('<i', exact(4))[0]
        if not 10 <= n <= 4*1024*1024: raise RuntimeError('Invalid RCON packet')
        data = exact(n)
        ident, kind = struct.unpack('<ii', data[:8])
        return ident, kind, data[8:-2].decode(errors='replace')
    with socket.create_connection(('127.0.0.1', 27015), timeout=5) as sock:
        send(sock, 1, 3, password)
        while True:
            ident, kind, _ = recv(sock)
            if ident == -1: raise RuntimeError('RCON authentication rejected')
            if kind == 2: break
        send(sock, 2, 2, text)
        send(sock, 3, 2, '')
        output = []
        while True:
            ident, kind, value = recv(sock)
            if ident == 3: break
            if ident == 2: output.append(value)
        return ''.join(output)


if __name__ == '__main__':
    print(command(' '.join(sys.argv[1:]) or 'status'))
