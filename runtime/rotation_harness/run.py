#!/usr/bin/env python3
"""Compile pinned upstream match-end code with deterministic engine boundary stubs.
Requires Docker + .NET 10 SDK image; no NuGet packages or game installation.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def source(component, suffix):
    manifest = json.loads((ROOT / 'docs/bundled-baseline.json').read_text())
    item = next(s for s in manifest['sources'] if s['component'] == component)
    archive = ROOT / item['source_archive']
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == item['source_sha256']
    with tarfile.open(archive) as tar:
        matches = [m for m in tar.getmembers() if m.name.endswith('/' + suffix)]
        assert len(matches) == 1, (suffix, matches)
        handle = tar.extractfile(matches[0])
        assert handle is not None
        return handle.read().decode('utf-8-sig')


def method(text, signature):
    # These pinned methods have balanced braces even in comments/string interpolation.
    start = text.index(signature)
    opening = text.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def main():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        (out / 'NuGet.Config').write_text('<configuration><packageSources><clear /></packageSources></configuration>')
        for name in ('Harness.cs', 'Harness.csproj'):
            (out / name).write_bytes((HERE / name).read_bytes())
        for file in ('CrossCutting/ServerManager.cs', 'Core/RotationManager.cs', 'Core/TimeLimitManager.cs'):
            (out / Path(file).name).write_text(source('GameModeManager', 'GameModeManager/' + file))
        bridge = source('GameModeManager', 'GameModeManager/Core/MapChooserBridge.cs')
        (out / 'Bridge.cs').write_text('using CounterStrikeSharp.API; namespace GameModeManager.Core { public partial class MapChooserBridge { ' + method(bridge, 'public void ChangeToNextMap()') + ' } }')
        gg = source('GG1MapChooser', 'GG1MapChooser.cs')
        methods = [method(gg, sig) for sig in (
            'public void ChangeNextMapCommand(', 'private void DoMapChange(', 'private void ChangeMapInFive(')]
        (out / 'GG.cs').write_text('using CounterStrikeSharp.API; using CounterStrikeSharp.API.Core; using CounterStrikeSharp.API.Modules.Commands; using CounterStrikeSharp.API.Modules.Timers; using Microsoft.Extensions.Logging; public partial class GG { ' + '\n'.join(methods) + ' }')
        subprocess.run(['docker', 'run', '--rm', '--network=none', '--user', f'{os.getuid()}:{os.getgid()}',
                        '-e', 'DOTNET_CLI_HOME=/harness', '-e', 'DOTNET_CLI_TELEMETRY_OPTOUT=1',
                        '-v', str(out) + ':/harness', '-v', str(ROOT) + ':/repo:ro', '-w', '/harness',
                        'mcr.microsoft.com/dotnet/sdk:10.0', 'dotnet', 'run', '--project', 'Harness.csproj', '--', '/repo'], check=True)


if __name__ == '__main__':
    main()
