import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
import random
import uuid
from pathlib import Path

import requests
import qrcode
from loguru import logger

from apis.xhs_pc_apis import XHS_Apis
from xhs_utils.http_util import REQUEST_TIMEOUT
from xhs_utils.xhs_util import generate_headers, generate_xs_xs_common, splice_str
from xhs_utils.common_util import generate_a1, generate_web_id


class XHSLoginApi:
    def __init__(self):
        self.base_url = "https://edith.xiaohongshu.com"
        self.as_url = "https://as.xiaohongshu.com"
        self.home_url = 'https://www.xiaohongshu.com/explore'

    @staticmethod
    def _get_sec_headers():
        return {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9',
            'content-type': 'application/json;charset=UTF-8',
            'sec-ch-ua': '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'origin': 'https://www.xiaohongshu.com',
            'referer': 'https://www.xiaohongshu.com/',
        }

    def _fetch_sec_cookies(self, cookies):
        api = '/api/sec/v1/scripting'
        data = {"callFrom": "web", "callback": "", "type": "ds", "appId": "xhs-pc-web"}

        xs, xt, xs_common = generate_xs_xs_common(cookies['a1'], api, data)
        headers = self._get_sec_headers()
        headers['x-s'] = xs
        headers['x-t'] = str(xt)
        headers['x-s-common'] = xs_common

        data_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        try:
            resp = requests.post(
                self.as_url + api,
                headers=headers, cookies=cookies,
                data=data_str.encode('utf-8'),
                timeout=REQUEST_TIMEOUT
            )
            res = resp.json()
            return res.get('data', {}).get('secPoisonId')
        except Exception as e:
            logger.debug(f'fetch sec_poison_id failed: {e}')
            return None

    def _fetch_gid(self, cookies):
        api = '/api/sec/v1/shield/webprofile'
        data = {"platform": "Windows", "sdkVersion": "4.3.5", "svn": "2", "profileData": ""}

        xs, xt, xs_common = generate_xs_xs_common(cookies['a1'], api, data)
        headers = self._get_sec_headers()
        headers['x-s'] = xs
        headers['x-t'] = str(xt)
        headers['x-s-common'] = xs_common

        data_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        try:
            resp = requests.post(
                self.as_url + api,
                headers=headers, cookies=cookies,
                data=data_str.encode('utf-8'),
                timeout=REQUEST_TIMEOUT
            )
            for key, value in resp.cookies.items():
                cookies[key] = value
            return cookies.get('gid')
        except Exception as e:
            logger.debug(f'fetch gid failed: {e}')
            return None

    def generate_init_cookies(self):
        ts = int(time.time() * 1000)
        a1 = generate_a1()
        web_id = generate_web_id(a1)
        cookies = {
            'abRequestId': str(uuid.uuid4()),
            'ets': str(ts),
            'webBuild': '6.7.4',
            'xsecappid': 'xhs-pc-web',
            'loadts': str(ts + random.randint(50, 200)),
            'a1': a1,
            'webId': web_id,
        }

        sec_poison_id = self._fetch_sec_cookies(cookies)
        if sec_poison_id:
            cookies['sec_poison_id'] = sec_poison_id

        gid = self._fetch_gid(cookies)
        if gid:
            cookies['gid'] = gid

        return cookies

    def generate_qrcode(self, cookies):
        api = '/api/sns/web/v1/login/qrcode/create'
        data = {"qr_type": 1}

        headers, data = generate_headers(cookies['a1'], api, data)
        resp = requests.post(
            self.base_url + api,
            headers=headers, cookies=cookies, data=data,
            timeout=REQUEST_TIMEOUT
        )
        for key, value in resp.cookies.items():
            cookies[key] = value

        res = resp.json()
        if not res.get('success'):
            return False, res.get('msg', '未知错误'), None
        data = res.get('data') or {}
        if not all(key in data for key in ('qr_id', 'code', 'url')):
            return False, res.get('msg', '二维码响应缺少必要字段'), {'cookies': cookies, 'res_json': res}

        return True, '成功', {
            'cookies': cookies,
            'qr_id': data['qr_id'],
            'code': data['code'],
            'qr_url': data['url'],
        }

    def check_qrcode_status(self, qr_id, code, cookies):
        api = '/api/qrcode/userinfo'
        data = {"qrId": qr_id, "code": code}

        headers, data = generate_headers(cookies['a1'], api, data)
        resp = requests.post(
            self.base_url + api,
            headers=headers, cookies=cookies, data=data,
            timeout=REQUEST_TIMEOUT
        )
        for key, value in resp.cookies.items():
            cookies[key] = value

        res = resp.json()
        status = (res.get('data') or {}).get('codeStatus')
        if status is None:
            return False, res.get('msg', '二维码状态响应缺少 codeStatus'), cookies

        if status == 2:
            cookies = self._login_by_qrcode_status(qr_id, code, cookies)

        status_map = {
            0: (False, '请扫描二维码'),
            1: (False, '请确认登录'),
            2: (True, '验证成功'),
            3: (False, '二维码已过期'),
        }
        success, msg = status_map.get(status, (False, f'未知状态: {status}'))
        return success, msg, cookies

    def _login_by_qrcode_status(self, qr_id, code, cookies):
        api = '/api/sns/web/v1/login/qrcode/status'
        params = {"qr_id": qr_id, "code": code}
        splice_api = splice_str(api, params)

        headers, _ = generate_headers(cookies['a1'], splice_api, method='GET')
        resp = requests.get(
            self.base_url + splice_api,
            headers=headers, cookies=cookies,
            timeout=REQUEST_TIMEOUT
        )
        for key, value in resp.cookies.items():
            cookies[key] = value

        res = resp.json()
        if res.get('success') and 'login_info' in res.get('data', {}):
            login_info = res['data']['login_info']
            if 'session' in login_info and 'web_session' not in cookies:
                cookies['web_session'] = login_info['session']

        return cookies

    def get_user_info(self, cookies):
        api = '/api/sns/web/v2/user/me'

        headers, _ = generate_headers(cookies['a1'], api)
        resp = requests.get(
            self.base_url + api,
            headers=headers, cookies=cookies,
            timeout=REQUEST_TIMEOUT
        )
        for key, value in resp.cookies.items():
            cookies[key] = value

        res = resp.json()
        return res.get('success', False), res.get('data', {}), cookies

    def send_phone_code(self, phone, cookies, zone='86'):
        api = '/api/sns/web/v2/login/send_code'
        params = {"phone": phone, "zone": zone, "type": "login"}
        splice_api = splice_str(api, params)

        headers, _ = generate_headers(cookies['a1'], splice_api)
        resp = requests.get(
            self.base_url + splice_api,
            headers=headers, cookies=cookies,
            timeout=REQUEST_TIMEOUT
        )
        res = resp.json()
        return res.get('success', False), res.get('msg', ''), res

    def login_by_phone(self, phone, code, cookies, zone='86'):
        check_api = '/api/sns/web/v1/login/check_code'
        params = {"phone": phone, "zone": zone, "code": code}
        splice_api = splice_str(check_api, params)

        headers, _ = generate_headers(cookies['a1'], splice_api)
        resp = requests.get(
            self.base_url + splice_api,
            headers=headers, cookies=cookies,
            timeout=REQUEST_TIMEOUT
        )
        res = resp.json()
        if not res.get('success'):
            return False, res.get('msg', '验证码验证失败'), {'cookies': cookies}
        mobile_token = (res.get('data') or {}).get('mobile_token')
        if not mobile_token:
            return False, res.get('msg', '验证码响应缺少 mobile_token'), {'cookies': cookies, 'res_json': res}

        login_api = '/api/sns/web/v2/login/code'
        data = {"mobile_token": mobile_token, "zone": zone, "phone": phone}
        headers, data = generate_headers(cookies['a1'], login_api, data)
        resp = requests.post(
            self.base_url + login_api,
            headers=headers, cookies=cookies, data=data,
            timeout=REQUEST_TIMEOUT
        )
        for key, value in resp.cookies.items():
            cookies[key] = value

        res = resp.json()
        if not res.get('success'):
            return False, res.get('msg', '登录失败'), {'cookies': cookies}
        session = (res.get('data') or {}).get('session')
        if not session:
            return False, res.get('msg', '登录响应缺少 session'), {'cookies': cookies, 'res_json': res}
        cookies['web_session'] = session
        return True, '成功', {
            'cookies': cookies,
            'res_json': res,
        }

    @staticmethod
    def cookies_to_str(cookies):
        return '; '.join(f'{k}={v}' for k, v in cookies.items())

    @staticmethod
    def _ensure_terminal_unicode():
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    @staticmethod
    def _get_terminal_qr_matrix(url, border=1):
        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            border=border,
        )
        qr.add_data(url)
        qr.make(fit=True)
        return qr.get_matrix()

    @staticmethod
    def _shrink_windows_console_font(handle, height=8):
        class COORD(ctypes.Structure):
            _fields_ = [('X', ctypes.c_short), ('Y', ctypes.c_short)]

        class CONSOLE_FONT_INFOEX(ctypes.Structure):
            _fields_ = [
                ('cbSize', ctypes.c_ulong),
                ('nFont', ctypes.c_ulong),
                ('dwFontSize', COORD),
                ('FontFamily', ctypes.c_uint),
                ('FontWeight', ctypes.c_uint),
                ('FaceName', ctypes.c_wchar * 32),
            ]

        kernel32 = ctypes.windll.kernel32
        original = CONSOLE_FONT_INFOEX()
        original.cbSize = ctypes.sizeof(CONSOLE_FONT_INFOEX)
        if not kernel32.GetCurrentConsoleFontEx(handle, False, ctypes.byref(original)):
            return None

        updated = CONSOLE_FONT_INFOEX()
        ctypes.memmove(ctypes.byref(updated), ctypes.byref(original), ctypes.sizeof(CONSOLE_FONT_INFOEX))
        updated.cbSize = ctypes.sizeof(CONSOLE_FONT_INFOEX)
        updated.dwFontSize.X = 0
        updated.dwFontSize.Y = height
        kernel32.SetCurrentConsoleFontEx(handle, False, ctypes.byref(updated))

        def restore():
            try:
                kernel32.SetCurrentConsoleFontEx(handle, False, ctypes.byref(original))
            except Exception:
                pass

        return restore

    @staticmethod
    def show_qrcode_terminal_with_win32_blocks(url):
        if not sys.platform.startswith('win'):
            return False, None

        class COORD(ctypes.Structure):
            _fields_ = [('X', ctypes.c_short), ('Y', ctypes.c_short)]

        class SMALL_RECT(ctypes.Structure):
            _fields_ = [
                ('Left', ctypes.c_short),
                ('Top', ctypes.c_short),
                ('Right', ctypes.c_short),
                ('Bottom', ctypes.c_short),
            ]

        class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
            _fields_ = [
                ('dwSize', COORD),
                ('dwCursorPosition', COORD),
                ('wAttributes', ctypes.c_ushort),
                ('srWindow', SMALL_RECT),
                ('dwMaximumWindowSize', COORD),
            ]

        def set_console_window(kernel32, handle, width, height):
            # Shrink window before buffer when needed, then grow buffer before window.
            tiny = SMALL_RECT(0, 0, 0, 0)
            kernel32.SetConsoleWindowInfo(handle, True, ctypes.byref(tiny))
            kernel32.SetConsoleScreenBufferSize(handle, COORD(width, height))
            rect = SMALL_RECT(0, 0, width - 1, height - 1)
            return bool(kernel32.SetConsoleWindowInfo(handle, True, ctypes.byref(rect)))

        try:
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)
            if handle in (0, -1):
                return False, None

            info = CONSOLE_SCREEN_BUFFER_INFO()
            if not kernel32.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
                return False, None

            original_size = COORD(info.dwSize.X, info.dwSize.Y)
            original_window = SMALL_RECT(
                info.srWindow.Left,
                info.srWindow.Top,
                info.srWindow.Right,
                info.srWindow.Bottom,
            )
            restore_font = None
            matrix = XHSLoginApi._get_terminal_qr_matrix(url, border=1)
            full_block_mode = os.getenv('XHS_QR_FULL_BLOCK', '').strip() == '1'
            width = len(matrix[0]) * 2 if full_block_mode else len(matrix[0]) if matrix else 0
            height = len(matrix) if full_block_mode else (len(matrix) + 1) // 2
            window_width = info.srWindow.Right - info.srWindow.Left + 1
            window_height = info.srWindow.Bottom - info.srWindow.Top + 1
            if width > window_width:
                logger.warning(
                    f'当前终端宽度 {window_width} 列，二维码需要 {width} 列，'
                    '请把窗口拉宽或缩小字体后扫码。'
                )
            if height + 2 > window_height:
                logger.warning(
                    f'当前终端高度 {window_height} 行，二维码需要 {height + 2} 行，'
                    '请把窗口拉高后扫码。'
                )

            target_width = max(window_width, width + 2)
            target_height = max(window_height, height + 4)
            max_width = info.dwMaximumWindowSize.X
            max_height = info.dwMaximumWindowSize.Y
            target_width = min(target_width, max_width)
            target_height = min(target_height, max_height)
            window_changed = False
            if target_width > window_width or target_height > window_height:
                window_changed = set_console_window(kernel32, handle, target_width, target_height)
                if window_changed:
                    info = CONSOLE_SCREEN_BUFFER_INFO()
                    kernel32.GetConsoleScreenBufferInfo(handle, ctypes.byref(info))
                else:
                    logger.warning('自动调整终端窗口大小失败，请手动拉宽/拉高后扫码。')

            def restore_window():
                if not window_changed:
                    return
                try:
                    set_console_window(kernel32, handle, original_size.X, original_size.Y)
                    kernel32.SetConsoleWindowInfo(handle, True, ctypes.byref(original_window))
                except Exception:
                    pass

            original_attr = info.wAttributes
            black = 0x0
            white = 0xF
            upper_half = '▀'

            def write_console(text, attr):
                written = ctypes.c_ulong(0)
                kernel32.SetConsoleTextAttribute(handle, attr)
                kernel32.WriteConsoleW(
                    handle,
                    ctypes.c_wchar_p(text),
                    len(text),
                    ctypes.byref(written),
                    None,
                )

            write_console('\n', original_attr)
            if full_block_mode:
                for row in matrix:
                    current_attr = None
                    segment = []
                    for module in row:
                        attr = (black if module else white) << 4
                        if current_attr is None:
                            current_attr = attr
                        if attr != current_attr:
                            write_console(''.join(segment), current_attr)
                            segment = []
                            current_attr = attr
                        segment.append('  ')
                    if segment:
                        write_console(''.join(segment), current_attr)
                    write_console('\n', original_attr)
            else:
                for row_index in range(0, len(matrix), 2):
                    top_row = matrix[row_index]
                    bottom_row = matrix[row_index + 1] if row_index + 1 < len(matrix) else [False] * len(top_row)
                    current_attr = None
                    segment = []
                    for top, bottom in zip(top_row, bottom_row):
                        fg = black if top else white
                        bg = black if bottom else white
                        attr = fg | (bg << 4)
                        if current_attr is None:
                            current_attr = attr
                        if attr != current_attr:
                            write_console(''.join(segment), current_attr)
                            segment = []
                            current_attr = attr
                        segment.append(upper_half)
                    if segment:
                        write_console(''.join(segment), current_attr)
                    write_console('\n', original_attr)
            write_console('\n', original_attr)
            kernel32.SetConsoleTextAttribute(handle, original_attr)
            return True, restore_window
        except Exception as e:
            logger.debug(f'Win32 控制台二维码绘制失败，回退字符渲染: {e}')
            return False, None

    @staticmethod
    def show_qrcode_terminal_with_node(url):
        XHSLoginApi._ensure_terminal_unicode()
        project_root = Path(__file__).resolve().parent.parent
        script = (
            "const qr=require('qrcode-terminal');"
            "qr.setErrorLevel('M');"
            "qr.generate(process.argv[1], {small:true});"
        )
        try:
            result = subprocess.run(
                ['node', '-e', script, url],
                cwd=project_root,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=10,
                check=False,
            )
        except Exception as e:
            logger.debug(f'qrcode-terminal 调用失败，回退 Python 渲染: {e}')
            return False

        output = (result.stdout or '').rstrip()
        if result.returncode != 0 or not output:
            stderr = (result.stderr or '').strip()
            logger.debug(f'qrcode-terminal 输出失败，回退 Python 渲染: {stderr}')
            return False

        print()
        print(output)
        print()
        return True

    @staticmethod
    def show_qrcode_terminal(url):
        XHSLoginApi._ensure_terminal_unicode()
        success, restore = XHSLoginApi.show_qrcode_terminal_with_win32_blocks(url)
        if success:
            return restore

        if XHSLoginApi.show_qrcode_terminal_with_node(url):
            return None

        matrix = XHSLoginApi._get_terminal_qr_matrix(url, border=1)
        width = len(matrix[0]) if matrix else 0
        terminal_width = shutil.get_terminal_size(fallback=(120, 40)).columns
        encoding = sys.stdout.encoding or 'utf-8'
        try:
            '█▀▄'.encode(encoding)
            use_half_block = True
        except UnicodeEncodeError:
            use_half_block = False

        required_width = width if use_half_block else width * 2

        if required_width > terminal_width:
            logger.warning(
                f'当前终端宽度 {terminal_width} 列，二维码需要 {required_width} 列，'
                '终端内可能会换行导致无法扫码。'
            )

        print()
        if use_half_block:
            for row_index in range(0, len(matrix), 2):
                top_row = matrix[row_index]
                bottom_row = matrix[row_index + 1] if row_index + 1 < len(matrix) else [False] * width
                line = []
                for top, bottom in zip(top_row, bottom_row):
                    if top and bottom:
                        line.append(' ')
                    elif top and not bottom:
                        line.append('▄')
                    elif not top and bottom:
                        line.append('▀')
                    else:
                        line.append('█')
                print(''.join(line))
        else:
            for row in matrix:
                line = []
                for module in row:
                    line.append('  ' if module else '██')
                print(''.join(line))
        print()
        return None

    @staticmethod
    def save_qrcode_image(url, output_path=None):
        try:
            qr = qrcode.QRCode(box_size=10, border=4)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            if output_path is None:
                output_path = Path.cwd() / 'download_files' / 'login_qrcode.png'
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path)
            return output_path
        except Exception as e:
            logger.warning(f'备用二维码图片保存失败，继续使用终端二维码: {e}')
            return None

    def qrcode_login(self, show_in_terminal=True, log_cookies=True):
        logger.info('[1/4] 正在生成初始cookies...')
        cookies = self.generate_init_cookies()
        logger.info(f'{cookies}')

        logger.info('[2/4] 正在获取二维码...')
        success, msg, qr_data = self.generate_qrcode(cookies)
        if not success:
            logger.error(f'获取二维码失败: {msg}')
            return None
        cookies = qr_data['cookies']

        logger.info('请使用小红书APP扫描以下二维码:')
        restore_terminal = None
        if show_in_terminal:
            restore_terminal = self.show_qrcode_terminal(qr_data['qr_url'])
            qr_path = self.save_qrcode_image(qr_data['qr_url'])
        else:
            qr_path = self.save_qrcode_image(qr_data['qr_url'])
            if qr_path:
                logger.info(f'二维码图片已生成: {qr_path}')
        if qr_path:
            logger.info(f'如果终端二维码无法识别，可打开图片文件扫码: {qr_path}')

        try:
            logger.info('[3/4] 等待扫码...')
            while True:
                success, msg, cookies = self.check_qrcode_status(
                    qr_data['qr_id'], qr_data['code'], cookies
                )
                if success:
                    logger.info(msg)
                    break
                if msg == '二维码已过期':
                    logger.error(msg)
                    return None
                time.sleep(2)

            logger.info('[4/4] 验证登录状态...')
            success, user_info, cookies = self.get_user_info(cookies)
            if success:
                logger.info(f'用户: {user_info.get("nickname", "未知")} (RedID: {user_info.get("red_id", "未知")})')
            else:
                logger.warning('获取用户信息失败，但cookies可能仍有效')

            cookies_str = self.cookies_to_str(cookies)
            if log_cookies:
                logger.success(f'登录成功!\ncookies:\n{cookies_str}')
            else:
                logger.success('登录成功，cookies 已获取')
            return cookies_str
        finally:
            if restore_terminal:
                restore_terminal()

    def phone_login(self):
        logger.info('[1/4] 正在生成初始cookies...')
        cookies = self.generate_init_cookies()
        logger.info(f'a1={cookies["a1"]}')

        phone = input('请输入手机号: ')
        logger.info('[2/4] 正在发送验证码...')
        success, msg, _ = self.send_phone_code(phone, cookies)
        if not success:
            logger.error(f'发送失败: {msg}')
            return None
        logger.info('验证码已发送')

        code = input('请输入验证码: ')
        logger.info('[3/4] 正在验证...')
        success, msg, result = self.login_by_phone(phone, code, cookies)
        if not success:
            logger.error(f'验证失败: {msg}')
            return None
        cookies = result['cookies']

        logger.info('[4/4] 验证登录状态...')
        success, user_info, cookies = self.get_user_info(cookies)
        if success:
            logger.info(f'用户: {user_info.get("nickname", "未知")} (RedID: {user_info.get("red_id", "未知")})')

        cookies_str = self.cookies_to_str(cookies)
        logger.success(f'登录成功!\ncookies:\n{cookies_str}')
        return cookies_str


if __name__ == '__main__':
    login_api = XHSLoginApi()
    # cookies_str = login_api.qrcode_login(show_in_terminal=True)
    cookies_str = login_api.phone_login()

    xhs_apis = XHS_Apis()
    # 获取用户信息
    user_url = 'https://www.xiaohongshu.com/user/profile/67a332a2000000000d008358?xsec_token=ABTf9yz4cLHhTycIlksF0jOi1yIZgfcaQ6IXNNGdKJ8xg=&xsec_source=pc_feed'
    success, msg, user_info = xhs_apis.search_note("888666", cookies_str)
    print(success, msg, user_info)



