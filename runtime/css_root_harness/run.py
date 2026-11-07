#!/usr/bin/env python3
"""Check where managed CounterStrikeSharp resolves its root in a materialized instance.

Managed CSS takes plugins/, shared/, configs/ and the admin files from the parent of
api/CounterStrikeSharp.API.dll's Location. The .NET host resolves symlinks on that path,
so it matters whether materialize() links or copies api/. This builds a stand-in API
assembly, lays out a shared base and an instance with the real materialize(), loads it
through the hostfxr sequence CSS uses, and requires the root to be inside the instance.
A control instance with a linked api/ (the v0.1.3 layout) must resolve into the base,
which shows the probe can detect the defect. Requires Docker, the pinned SDK image and cc.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
CSS = Path('game/csgo/addons/counterstrikesharp')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


# Same pinned SDK image as the rotation harness, so CI pulls one toolchain.
IMAGE = load('rotation_harness', HERE.parent / 'rotation_harness/run.py').IMAGE


def runtime():
    return load('fleet_runtime', HERE.parent / 'runtime.py')


def docker(work, *command):
    return subprocess.run(['docker', 'run', '--rm', '--pull=never', '--network=none', '--platform=linux/amd64',
                           '--user', f'{os.getuid()}:{os.getgid()}', '-e', 'HOME=' + str(work),
                           '-e', 'DOTNET_CLI_HOME=' + str(work), '-e', 'DOTNET_CLI_TELEMETRY_OPTOUT=1',
                           '-e', 'DOTNET_NOLOGO=1', '-v', f'{work}:{work}', '-w', str(work), IMAGE, *command],
                          check=True, text=True, capture_output=True).stdout


def main():
    m = runtime()
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp).resolve()
        (work / 'src').mkdir()
        for name in ('Probe.cs', 'Probe.csproj'):
            (work / 'src' / name).write_bytes((HERE / name).read_bytes())
        (work / 'src/NuGet.Config').write_text('<configuration><packageSources><clear /></packageSources></configuration>')
        css = work / 'base' / CSS
        (css / 'dotnet').mkdir(parents=True)
        docker(work, 'sh', '-c', f'dotnet build -c Release -o {css}/api src/Probe.csproj >build.log 2>&1 || '
                                 f'{{ cat build.log; exit 1; }}; cp -a /usr/share/dotnet/host /usr/share/dotnet/shared {css}/dotnet/')
        subprocess.run(['cc', '-O1', '-o', str(work / 'host'), str(HERE / 'host.c'), '-ldl'], check=True)
        fxr, = [p.name for p in (css / 'dotnet/host/fxr').iterdir()]

        def probe(instance):
            out = docker(work, str(work / 'host'), str(instance / CSS), fxr)
            return Path(next(l for l in out.splitlines() if l.startswith('CONTENT_ROOT=')).split('=', 1)[1])

        fixed = work / 'instances/fixed'
        m.materialize(work / 'base', fixed)
        legacy = work / 'instances/legacy'
        m.materialize(work / 'base', legacy)
        for path in sorted((legacy / CSS / 'api').iterdir()):
            path.unlink(); path.symlink_to(work / 'base' / CSS / 'api' / path.name)
        roots = {'fixed': probe(fixed), 'legacy': probe(legacy)}
        print('materialized instance root:', roots['fixed'])
        print('linked api/ (v0.1.3) root: ', roots['legacy'])
        assert roots['legacy'] == work / 'base' / CSS, 'control did not reproduce the shared-root defect'
        assert roots['fixed'] == fixed / CSS, 'managed CSS root escaped the instance'
        print('PASS: managed CounterStrikeSharp resolves its root inside the instance')


if __name__ == '__main__':
    main()
