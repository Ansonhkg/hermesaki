#!/usr/bin/env python3
"""Reinstall an existing Hermesaki deployment from an encrypted consistent snapshot.

Preserves service versions, ports, credentials and all mail domains. This is an
operator recovery command, not a substitute for a clean setup wizard journey.
"""
import argparse
import hashlib
import io
import json
import os
import posixpath
from pathlib import Path
import subprocess
import tarfile
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AAD = b'hermesaki-reinstall-v1'


def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, **kwargs).stdout


def compose(path, *args):
    return run(['docker', 'compose', '-f', str(path), *args])


def snapshot(source, archive, keyfile, stop_source=False):
    if archive.exists():
        raise ValueError('archive already exists')
    config = json.loads(source.read_text())
    runtime = source.parent / '.runtime'
    if not runtime.is_dir():
        raise ValueError('expected existing .runtime directory')
    if sum(p.stat().st_size for p in runtime.rglob('*') if p.is_file()) > 1024**3:
        raise ValueError('use streaming backup for runtimes larger than 1 GiB')
    # Include every bind mount, including certificate stores outside .runtime.
    # Named volumes need an explicit volume-export workflow instead of omission.
    bindings = {}
    for service in config['services'].values():
        for volume in service.get('volumes', []):
            if not isinstance(volume, str) or ':' not in volume:
                raise ValueError('only explicit absolute bind mounts supported')
            origin = volume.split(':', 1)[0]
            path = Path(origin)
            if not path.is_absolute() or not path.exists():
                raise ValueError('bind source must exist and be absolute')
            if origin == str(runtime) or origin.startswith(str(runtime)+'/'):
                bindings[origin] = '.runtime' + origin[len(str(runtime)):]
            elif origin not in bindings:
                bindings[origin] = 'external/' + str(len(bindings))
    sources = [runtime] + [Path(k) for k,v in bindings.items() if v.startswith('external/')]
    if sum(p.stat().st_size for source_path in sources for p in
           (source_path.rglob('*') if source_path.is_dir() else [source_path]) if p.is_file()) > 1024**3:
        raise ValueError('use streaming backup for snapshots larger than 1 GiB')
    containers = compose(source, 'ps', '-q').decode().split()
    if not containers:
        raise ValueError('source is not running')
    if not keyfile.exists():
        keyfile.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with os.fdopen(os.open(keyfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as f:
            f.write(os.urandom(32))
    key = keyfile.read_bytes()
    paused = []
    stopped = False
    data = io.BytesIO()
    try:
        if stop_source:
            compose(source, 'stop'); stopped = True
        else:
            for container in containers:
                run(['docker', 'pause', container]); paused.append(container)
        os.sync()
        with tarfile.open(fileobj=data, mode='w:gz') as tar:
            tar.add(runtime, arcname='.runtime')
            for origin, target in bindings.items():
                if target.startswith('external/'):
                    tar.add(origin, arcname=target)
            payload=json.dumps({'version':2,'compose':config,'bindings':bindings}).encode()
            member=tarfile.TarInfo('manifest.json');member.size=len(payload);member.mode=0o600
            tar.addfile(member,io.BytesIO(payload))
        plain = data.getvalue()
    except Exception:
        if stopped:
            compose(source, 'start')
        raise
    finally:
        for container in reversed(paused):
            run(['docker', 'unpause', container])
    nonce = os.urandom(12)
    encrypted = nonce + AESGCM(key).encrypt(nonce, plain, AAD)
    assert AESGCM(key).decrypt(nonce, encrypted[12:], AAD) == plain
    archive.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as f:
        f.write(encrypted)
    # Composition and bind inventory are encrypted inside the archive.
    return {'encrypted_backup': True, 'decryption_verified': True,
            'sha256': hashlib.sha256(encrypted).hexdigest(), 'bytes': len(encrypted)}


def restore(archive, keyfile, destination, source_root):
    if destination.exists():
        raise ValueError('destination must not exist')
    blob = archive.read_bytes()
    plain = AESGCM(keyfile.read_bytes()).decrypt(blob[:12], blob[12:], AAD)
    with tarfile.open(fileobj=io.BytesIO(plain), mode='r:gz') as tar:
        members = tar.getmembers()
        modern = any(member.name == 'manifest.json' for member in members)
        for member in members:
            path = Path(member.name)
            if (not (member.isfile() or member.isdir() or member.issym()) or path.is_absolute()
                    or '..' in path.parts or not path.parts
                    or path.parts[0] not in (('.runtime','external','manifest.json') if modern else ('.runtime',))):
                raise ValueError('unsafe archive member')
            if member.issym():
                target = posixpath.normpath(posixpath.join(posixpath.dirname(member.name),member.linkname))
                if posixpath.isabs(member.linkname) or target.startswith('../') or target == '..':
                    raise ValueError('unsafe archive link')
        if modern:
            manifest=json.load(tar.extractfile('manifest.json'))
            if manifest.get('version') != 2:raise ValueError('unsupported snapshot version')
            config=manifest['compose'];bindings=manifest['bindings']
        else:
            config=json.loads(archive.with_suffix('.compose.json').read_text());bindings=None
        # Validate all restored mounts before extracting anything.
        for service in config['services'].values():
            volumes=[]
            for volume in service.get('volumes', []):
                if not isinstance(volume,str) or ':' not in volume:raise ValueError('invalid bind mount')
                origin,rest=volume.split(':',1)
                if bindings is None:
                    if not origin.startswith(str(source_root)+'/.runtime/'):
                        raise ValueError('external bind mount requires a separate backup')
                    target=origin[len(str(source_root))+1:]
                else:
                    target=bindings.get(origin,'')
                    parts=Path(target).parts
                    if not parts or Path(target).is_absolute() or '..' in parts or parts[0] not in ('.runtime','external'):
                        raise ValueError('unsafe restored bind')
                volumes.append(str(destination/target)+':'+rest)
            service['volumes']=volumes
        destination.mkdir(mode=0o700)
        tar.extractall(destination, filter='data')
        # Docker runtime UIDs must survive restoration, including private dirs.
        for member in members:
            path = destination / member.name
            if os.geteuid() == 0:
                os.chown(path, member.uid, member.gid, follow_symlinks=False)
            if not member.issym():os.chmod(path, member.mode)
    path = destination / 'compose.json'
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as f:
        json.dump(config, f, indent=2)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['snapshot', 'restore'])
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--key-file', type=Path, required=True)
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--stop-source', action='store_true', help='Keep source stopped after final snapshot for cutover')
    args = parser.parse_args()
    if args.action == 'snapshot':
        result = snapshot(args.source, args.archive, args.key_file, args.stop_source)
    else:
        if not args.destination:
            parser.error('--destination required')
        path = restore(args.archive, args.key_file, args.destination, args.source.parent)
        result = {'restored': True, 'compose': str(path), 'services_started': False}
    print(json.dumps(result))


if __name__ == '__main__':
    main()
