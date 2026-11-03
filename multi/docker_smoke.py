#!/usr/bin/env python3
"""Run real Docker/Compose mounts + automatic updater using an offline process fixture.
Requires the image built by multi/Dockerfile; never downloads the CS2 game.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = os.getenv('COMPOSE', 'docker compose').split()
IMAGE = os.getenv('SMOKE_IMAGE', 'cs2-multi-local:latest')


def run(args, check=True):
    return subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=check).stdout


def main():
    project = 'cs2-smoke-' + str(os.getpid())
    for n in range(1,4):
        p = ROOT/f'multi/private/server{n}.env'
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/'multi/server.env.example',p)
    config = json.loads(run(COMPOSE+['-f',str(ROOT/'multi/compose.yaml'),'config','--format','json']))
    config['name'] = project
    for name, value in config['volumes'].items(): value['name'] = project+'_'+name
    for name, value in config.get('networks',{}).items(): value['name'] = project+'_'+name
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp); p.chmod(0o755)
        fixture=p/'fixture'; fixture.mkdir(); fixture.chmod(0o755)
        shutil.copyfile(ROOT/'multi/fixtures/steamcmd.py',fixture/'steamcmd.py')
        (fixture/'steamcmd.py').chmod(0o755)
        (fixture/'linux64').mkdir(); (fixture/'linux64/steamclient.so').write_text('offline-fixture')
        version=fixture/'build'; version.write_text('1')
        empty=p/'empty'; empty.mkdir()
        for name, svc in config['services'].items():
            svc.pop('ports',None); svc.pop('build',None); svc['restart']='no'
            svc['image'] = IMAGE
            if name != 'updater':
                # Exercise the default bind layout in disposable host directories.
                state = p/name; state.mkdir(); state.chmod(0o755)
                svc['volumes'] = [v for v in svc['volumes'] if v['target'] != '/instance']
                svc['volumes'].append({'type':'bind','source':str(state),'target':'/instance'})
                # Do not pass any operator secrets into the fixture.
                svc['environment']={'INSTANCE_ID':name}
        up=config['services']['updater']
        up['environment']={'STEAMCMD':'/fixture/steamcmd.py','FIXTURE_BUILD':'/fixture/build',
                           'CHECK_INTERVAL':'5','UPDATE_POLICY':'force',
                           'INSTANCE_IDS':'server1 server2 server3'}
        up['volumes']=[v for v in up['volumes'] if v['target'] in ('/base','/control')]
        up['volumes'] += [{'type':'bind','source':str(fixture),'target':'/fixture','read_only':True},
                          {'type':'bind','source':str(empty),'target':'/mods','read_only':True},
                          {'type':'bind','source':str(empty),'target':'/custom','read_only':True}]
        configfile=p/'compose.json'; configfile.write_text(json.dumps(config))
        cmd=COMPOSE+['-p',project,'-f',str(configfile)]
        def check(code, service='server1'):
            result=subprocess.run(cmd+['exec','-T',service,'python3','-c',code],capture_output=True,text=True)
            return result.returncode==0
        def wait(code, service='server1'):
            end=time.monotonic()+45
            while time.monotonic()<end:
                if check(code,service): return
                time.sleep(.3)
            raise RuntimeError('Fixture transition timed out: '+code)
        try:
            print(run(cmd+['up','-d','--no-build']))
            for n in range(1,4):
                wait("from pathlib import Path; assert Path('/instance/running').exists(); assert Path('/instance/ro-verified').exists()", f'server{n}')
            for name in ('server1','server2','server3'):
                run(cmd+['exec','-T','--user','10001',name,'python3','-c',
                    "from pathlib import Path; import os; c=Path('/instance/cfg/operator.cfg'); c.write_text(os.environ['INSTANCE_ID']); a=Path('/instance/addons/counterstrikesharp/configs'); a.mkdir(parents=True,exist_ok=True); (a/'admins.json').write_text('{}')"])
                assert (p/name/'cfg/operator.cfg').read_text() == name
                assert (p/name/'cfg').is_symlink() and not (p/name/'cfg').readlink().is_absolute()
                assert not (p/name/'addons/counterstrikesharp/configs/admins.json').is_symlink()
            assert (p/'server1/cfg/operator.cfg').stat().st_ino != (p/'server2/cfg/operator.cfg').stat().st_ino
            print('PASS: three container processes started; all verified /base is read-only')
            print('PASS: host bind shortcuts resolve; cfg/admin JSONs are independent regular files')
            version.write_text('2')
            wait("from pathlib import Path; assert Path('/base/game/csgo/fixture.vpk').read_text() == '2'; assert Path('/instance/running').exists()")
            print('PASS: sidecar automatically detected and installed build 2; supervisors resumed')
            version.write_text('999')
            wait("from pathlib import Path; assert Path('/control/updating').exists(); assert not Path('/instance/running').exists()")
            time.sleep(1)
            for n in range(1,4):
                assert check("from pathlib import Path; assert not Path('/instance/running').exists()", f'server{n}')
            print('PASS: injected Steam installation failure keeps all three games stopped')
            version.write_text('3')
            for n in range(1,4):
                wait("from pathlib import Path; assert Path('/base/game/csgo/fixture.vpk').read_text() == '3'; assert Path('/instance/running').exists(); assert not Path('/control/updating').exists()", f'server{n}')
            for name in ('server1','server2','server3'):
                assert (p/name/'cfg/operator.cfg').read_text() == name
            print('PASS: automatic retry installed build 3 and resumed all three instances; private cfg preserved')
            print(run(cmd+['logs','--no-color','updater']))
        finally:
            print(run(cmd+['down','--volumes','--remove-orphans']))
            # Runtime UID owns the bind trees; restore caller ownership for scratch cleanup.
            for name in ('server1','server2','server3'):
                run(['docker','run','--rm','--entrypoint','chown','-v',str(p/name)+':/cleanup',
                     IMAGE,'-hR',f'{os.getuid()}:{os.getgid()}','/cleanup'])

if __name__=='__main__': main()
