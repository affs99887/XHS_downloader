"""Share project-local Node and browser selection across Windows entry points."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def runtime_environment(root=ROOT):
    environment = os.environ.copy()
    runtime_file = root / '.runtime' / 'windows-runtime.json'
    if not runtime_file.is_file():
        raise RuntimeError('Run Setup.bat first to prepare the project runtime.')
    node = Path(json.loads(runtime_file.read_text(encoding='utf-8'))['node'])
    if not node.is_absolute():
        node = root / node
    if not node.is_file():
        raise RuntimeError('Node runtime is missing or the project was moved. Rerun Setup.bat.')
    environment['PATH'] = str(node.parent) + os.pathsep + environment.get('PATH', '')
    environment['PLAYWRIGHT_BROWSERS_PATH'] = str(root / '.runtime' / 'browsers')
    environment['PYTHONUTF8'] = '1'
    environment['PYTHONIOENCODING'] = 'utf-8'
    environment['XHS_QR_FULL_BLOCK'] = '1'
    return environment


def main(arguments=None):
    arguments = sys.argv[1:] if arguments is None else arguments
    try:
        environment = runtime_environment()
        if arguments == ['--doctor']:
            command = [sys.executable, '-B', str(ROOT / 'scripts' / 'check_environment.py')]
        elif arguments:
            command = [sys.executable, '-m', arguments[0], *arguments[1:]]
        else:
            raise RuntimeError('A downloader module is required')
        return subprocess.run(command, cwd=ROOT, env=environment, check=False).returncode
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
