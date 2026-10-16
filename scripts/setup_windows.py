"""Install an isolated Windows runtime without overwriting login configuration."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import urllib.request
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NODE_VERSION = '24.22.0'
TEMPLATES = {'.env.example': '.env', 'douyin_config.example.yml': 'douyin_config.yml',
             'weibo_config.example.json': 'weibo_config.json'}


def run(command, *, env=None):
    subprocess.run([str(value) for value in command], cwd=ROOT, env=env, check=True)


def supported_node(node):
    if not node or not Path(node).is_file():
        return False
    result = subprocess.run([str(node), '--version'], capture_output=True, text=True)
    return result.returncode == 0 and result.stdout.strip().split('.')[0] in {'v22', 'v24'}


def npm_cli(node):
    return Path(node).resolve().parent / 'node_modules' / 'npm' / 'bin' / 'npm-cli.js'


def download(url, destination):
    print(f'Downloading {url}', flush=True)
    partial = destination.with_suffix(destination.suffix + '.partial')
    with urllib.request.urlopen(url, timeout=90) as response, partial.open('wb') as output:
        shutil.copyfileobj(response, output)
    partial.replace(destination)


def install_node():
    local_node = ROOT / '.runtime' / 'node' / 'node.exe'
    for candidate in (local_node, shutil.which('node')):
        if supported_node(candidate) and npm_cli(candidate).is_file():
            return Path(candidate).resolve()
    cache = ROOT / '.runtime' / 'downloads'
    cache.mkdir(parents=True, exist_ok=True)
    filename = f'node-v{NODE_VERSION}-win-x64.zip'
    base_url = f'https://nodejs.org/dist/v{NODE_VERSION}/'
    checksums = cache / f'node-v{NODE_VERSION}-SHASUMS256.txt'
    download(base_url + 'SHASUMS256.txt', checksums)
    expected = next((line.split()[0] for line in checksums.read_text().splitlines()
                     if line.strip() and line.split()[-1] == filename), None)
    if not expected:
        raise RuntimeError('Node archive is missing from the official checksum manifest')
    archive = cache / filename
    if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        download(base_url + filename, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise RuntimeError('Node SHA-256 verification failed; archive was not extracted')
    with zipfile.ZipFile(archive) as package:
        staging = cache / f'node-v{NODE_VERSION}-win-x64'
        for member in package.infolist():
            if not (cache / member.filename).resolve().is_relative_to(cache.resolve()):
                raise RuntimeError('Invalid Node archive path')
        package.extractall(cache)
    local_node.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(staging, local_node.parent, dirs_exist_ok=True)
    if not supported_node(local_node) or not npm_cli(local_node).is_file():
        raise RuntimeError('Project-local Node installation is incomplete')
    return local_node


def initialize_configs(root=ROOT):
    for template, destination in TEMPLATES.items():
        target = root / destination
        if not target.exists():
            shutil.copyfile(root / template, target)
            print(f'Created {destination}', flush=True)


def main():
    if sys.platform != 'win32' or sys.version_info[:2] != (3, 11) or struct.calcsize('P') != 8:
        raise RuntimeError('Use Setup.bat with Python 3.11 x64 on Windows')
    if not os.access(ROOT, os.W_OK):
        raise RuntimeError('Project directory is not writable; move it to a user-owned folder')
    runtime_root = ROOT / '.runtime'
    for name in ('pip-cache', 'npm-cache', 'tmp'):
        (runtime_root / name).mkdir(parents=True, exist_ok=True)
    os.environ['PIP_CACHE_DIR'] = str(runtime_root / 'pip-cache')
    os.environ['npm_config_cache'] = str(runtime_root / 'npm-cache')
    os.environ['TEMP'] = os.environ['TMP'] = str(runtime_root / 'tmp')
    os.environ['PYTHONUNBUFFERED'] = '1'
    python = ROOT / '.venv' / 'Scripts' / 'python.exe'
    if python.exists():
        result = subprocess.run([str(python), '-c', 'import sys; print(sys.version_info[:2] == (3, 11))'],
                                capture_output=True, text=True)
        if result.returncode != 0 or result.stdout.strip() != 'True':
            raise RuntimeError('Existing .venv is incompatible. Rename .venv and rerun Setup.bat; keep your config files.')
    print('[1/5] Creating/updating .venv', flush=True)
    venv.EnvBuilder(with_pip=True).create(ROOT / '.venv')
    print('[2/5] Installing locked Python dependencies', flush=True)
    run([python, '-m', 'pip', 'install', '--disable-pip-version-check', '-r', 'requirements-lock.txt'])
    run([python, '-m', 'pip', 'check'])
    print('[3/5] Preparing Node and installing locked JavaScript dependencies', flush=True)
    node = install_node()
    environment = os.environ.copy()
    environment['PATH'] = str(node.parent) + os.pathsep + environment.get('PATH', '')
    environment['PYTHONUTF8'] = '1'
    environment['PYTHONIOENCODING'] = 'utf-8'
    environment['PLAYWRIGHT_BROWSERS_PATH'] = str(ROOT / '.runtime' / 'browsers')
    run([node, npm_cli(node), 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], env=environment)
    runtime = ROOT / '.runtime' / 'windows-runtime.json'
    runtime.parent.mkdir(parents=True, exist_ok=True)
    node_reference = str(node.relative_to(ROOT)) if node.is_relative_to(ROOT) else str(node)
    runtime.write_text(json.dumps({'node': node_reference}, indent=2) + '\n', encoding='utf-8')
    print('[4/5] Installing project-local Chromium and preparing config files', flush=True)
    run([python, '-m', 'playwright', 'install', 'chromium'], env=environment)
    initialize_configs()
    print('[5/5] Running environment checks (no account login or downloads)', flush=True)
    run([python, '-B', 'scripts/launch_windows.py', '--doctor'], env=environment)
    print('\nSetup complete. Double-click Downloader.bat to start.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'\nSetup failed: {error}\nFix this step and rerun Setup.bat. Existing cookies/configs are preserved.', file=sys.stderr)
        raise SystemExit(1)
