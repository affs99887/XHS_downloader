"""Offline checks of the complete runtime, without reading account cookies."""
from __future__ import annotations

import importlib.metadata as metadata
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def check_python():
    if sys.version_info[:2] != (3, 11) or struct.calcsize('P') != 8:
        raise RuntimeError('Python 3.11 x64 is required for the locked environment')
    print(f'  Python {sys.version.split()[0]} x64')


def check_dependencies():
    for line in (ROOT / 'requirements-lock.txt').read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        requirement, _, marker = line.partition(';')
        if marker and sys.platform != 'win32':
            continue
        name, version = requirement.strip().split('==')
        if metadata.version(name) != version:
            raise RuntimeError(f'{name} must be {version}; rerun Setup.bat')
    subprocess.run([sys.executable, '-m', 'pip', 'check'], check=True, cwd=ROOT)


def check_node():
    node = shutil.which('node')
    if not node:
        raise RuntimeError('Node is missing')
    version = subprocess.check_output([node, '--version'], text=True).strip()
    if not re.match(r'^v(?:22|24)\.', version):
        raise RuntimeError(f'Unsupported Node {version}; rerun Setup.bat')
    subprocess.run([node, '-e', "for(const name of ['crypto-js','jsdom','qrcode-terminal']) require(name);"], cwd=ROOT, check=True)
    from xhs_utils.xhs_util import generate_xs_xs_common, generate_xray_traceid
    result = generate_xs_xs_common('0' * 52, '/api/sns/web/v1/user/selfinfo', {}, 'GET')
    if len(result) != 3 or not result[0] or not generate_xray_traceid():
        raise RuntimeError('Xiaohongshu local signature check failed')
    print(f'  Node {version}; JavaScript modules and signatures OK')


def check_entrypoints():
    for module in ('spider.downloader', 'spider.xhs_downloader', 'spider.douyin_downloader', 'spider.weibo_downloader'):
        subprocess.run([sys.executable, '-B', '-m', module, '--help'], cwd=ROOT,
                       stdout=subprocess.DEVNULL, check=True)
    for module, upstream in [('douyin', 'core.api_client'), ('weibo', 'weibo')]:
        code = f'from spider.{module}_downloader import activate_vendor; activate_vendor(); import {upstream}'
        subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT, check=True)
    import cv2
    import imageio_ffmpeg
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-version'], stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE, check=True)


def check_browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        with playwright.chromium.launch(headless=True) as browser:
            page = browser.new_page()
            page.set_content('<title>Downloader environment check</title>')
            if page.title() != 'Downloader environment check':
                raise RuntimeError('Chromium offline page check failed')


def check_files():
    for name in ('.env.example', 'douyin_config.example.yml', 'weibo_config.example.json'):
        if not (ROOT / name).is_file():
            raise RuntimeError(f'Missing config template: {name}')
    with tempfile.TemporaryFile(dir=ROOT):
        pass


def main():
    failures = []
    for name, check in [('Python', check_python), ('locked dependencies', check_dependencies),
                        ('Node and local signatures', check_node), ('downloader imports and FFmpeg', check_entrypoints),
                        ('Chromium offline launch', check_browser), ('templates and write permission', check_files)]:
        try:
            check()
            print(f'[OK] {name}', flush=True)
        except Exception as error:
            failures.append(name)
            print(f'[FAIL] {name}: {error}', flush=True)
    print('Environment ready.' if not failures else 'Environment incomplete. Rerun Setup.bat.', flush=True)
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
