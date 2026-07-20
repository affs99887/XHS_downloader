import os
import re
import time
import random
import hashlib
import binascii
import json
from pathlib import Path

import execjs
import requests
from loguru import logger
from dotenv import load_dotenv

from xhs_utils.http_util import REQUEST_TIMEOUT
from xhs_utils.xhs_creator_util import generate_xsc

_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static')
_WEBSECTIGA_ENV_PATH = os.path.join(_STATIC_DIR, 'xhs_websectiga_env.js')
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _PROJECT_ROOT / '.env'

_A1_CHARSET = 'abcdefghijklmnopqrstuvwxyz1234567890'
_AS_URL = 'https://as.xiaohongshu.com'


def load_env():
    load_dotenv()
    if _ENV_PATH.exists():
        load_dotenv(dotenv_path=_ENV_PATH, override=False)
    cookies_str = (os.getenv('COOKIES') or '').strip()
    return cookies_str


def _quote_env_value(value):
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"


def save_cookies_to_env(cookies_str, env_path=_ENV_PATH):
    cookies_str = (cookies_str or '').strip()
    if not cookies_str:
        raise ValueError('cookies_str 不能为空')

    env_path = Path(env_path)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    cookies_line = f'COOKIES={_quote_env_value(cookies_str)}'

    if env_path.exists():
        lines = env_path.read_text(encoding='utf-8-sig').splitlines(keepends=True)
    else:
        lines = []

    replaced = False
    for index, line in enumerate(lines):
        if re.match(r'^\s*COOKIES\s*=', line):
            newline = '\n' if line.endswith('\n') else ''
            lines[index] = cookies_line + newline
            replaced = True
            break

    if not replaced:
        if lines and not lines[-1].endswith('\n'):
            lines[-1] = lines[-1] + '\n'
        lines.append(cookies_line + '\n')

    env_path.write_text(''.join(lines), encoding='utf-8')
    os.environ['COOKIES'] = cookies_str
    return str(env_path)


def _is_login_expired_msg(msg):
    msg = str(msg or '')
    expired_markers = ('登录已过期', '请先登录', '未登录', 'login expired', 'not login')
    return any(marker in msg for marker in expired_markers)


def login_and_save_cookies(show_qrcode_in_terminal=True, persist=True, reason=''):
    if reason:
        logger.info(reason)
    else:
        logger.info('开始小红书 PC 端扫码登录...')
    from apis.xhs_pc_login_apis import XHSLoginApi

    cookies_str = XHSLoginApi().qrcode_login(
        show_in_terminal=show_qrcode_in_terminal,
        log_cookies=False,
    )
    if not cookies_str:
        raise RuntimeError('扫码登录失败，未获取到 COOKIES')

    if persist:
        env_path = save_cookies_to_env(cookies_str)
        logger.info(f'已将登录 cookies 写入 {env_path}')
    else:
        os.environ['COOKIES'] = cookies_str

    return cookies_str


def validate_pc_cookies(cookies_str):
    from apis.xhs_pc_apis import XHS_Apis

    success, msg, _ = XHS_Apis().get_user_self_info2(cookies_str)
    return success, msg


def load_or_login_cookies(show_qrcode_in_terminal=True, persist=True, validate=False):
    cookies_str = load_env()
    if not cookies_str:
        return login_and_save_cookies(
            show_qrcode_in_terminal=show_qrcode_in_terminal,
            persist=persist,
            reason='未检测到 COOKIES，开始小红书 PC 端扫码登录...',
        )

    if validate:
        success, msg = validate_pc_cookies(cookies_str)
        if success:
            return cookies_str
        if _is_login_expired_msg(msg):
            return login_and_save_cookies(
                show_qrcode_in_terminal=show_qrcode_in_terminal,
                persist=persist,
                reason=f'当前 COOKIES 已失效（{msg}），开始重新扫码登录...',
            )
        raise RuntimeError(f'COOKIES 校验失败: {msg}')

    return cookies_str


def init():
    media_base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../datas/media_datas'))
    excel_base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../datas/excel_datas'))
    for base_path in [media_base_path, excel_base_path]:
        if not os.path.exists(base_path):
            os.makedirs(base_path)
            logger.info(f'创建目录 {base_path}')
    cookies_str = load_or_login_cookies(validate=True)
    base_path = {
        'media': media_base_path,
        'excel': excel_base_path,
    }
    return cookies_str, base_path


def generate_a1():
    ts_hex = hex(int(time.time() * 1000))[2:]
    random_str = ''.join(random.choices(_A1_CHARSET, k=30))
    a_part = ts_hex + random_str + '5' + '0' + '000'
    crc = binascii.crc32(a_part.encode()) & 0xFFFFFFFF
    return (a_part + str(crc))[:52]


def generate_web_id(a1):
    return hashlib.md5(a1.encode()).hexdigest()


def _load_websectiga_env():
    try:
        return open(_WEBSECTIGA_ENV_PATH, 'r', encoding='utf-8').read()
    except FileNotFoundError:
        return None


def fetch_sec_cookies(cookies, headers):
    sec_poison_id = None
    websectiga = None

    api = '/api/sec/v1/scripting'
    data = {"callFrom": "web", "callback": "seccallback"}
    h = dict(headers)
    h['content-type'] = 'application/json;charset=UTF-8'
    sign_h = generate_xsc(cookies['a1'], api, data)
    h.update(sign_h)
    data_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
    try:
        resp = requests.post(
            _AS_URL + api,
            headers=h,
            cookies=cookies,
            data=data_str.encode('utf-8'),
            timeout=REQUEST_TIMEOUT
        )
        res = resp.json()
        sec_poison_id = res.get('data', {}).get('secPoisonId')
        jsvmp_code = res.get('data', {}).get('data', '')
        if jsvmp_code:
            env = _load_websectiga_env()
            if env:
                try:
                    js_code = env + '\n' + jsvmp_code + '\nvar __result = _websectiga_result;'
                    ctx = execjs.compile(js_code)
                    websectiga = ctx.eval('__result') or None
                except Exception as e:
                    logger.debug(f'websectiga jsvmp execution failed: {e}')
    except Exception as e:
        logger.debug(f'fetch sec cookies failed: {e}')
    return sec_poison_id, websectiga


def fetch_gid(cookies, headers):
    api = '/api/sec/v1/shield/webprofile'
    data = {
        "platform": "Windows",
        "sdkVersion": "4.3.5",
        "svn": "2",
        "profileData": ""
    }
    h = dict(headers)
    h['content-type'] = 'application/json'
    sign_h = generate_xsc(cookies['a1'], api, data)
    h.update(sign_h)
    data_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
    try:
        resp = requests.post(
            _AS_URL + api,
            headers=h,
            cookies=cookies,
            data=data_str.encode('utf-8'),
            timeout=REQUEST_TIMEOUT
        )
        for key, value in resp.cookies.items():
            cookies[key] = value
        if 'gid' in cookies:
            return cookies['gid']
    except Exception as e:
        logger.debug(f'fetch gid failed: {e}')
    return None


