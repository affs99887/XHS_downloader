import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


setup = load_script('setup_windows')
launcher = load_script('launch_windows')


class WindowsDeploymentTest(unittest.TestCase):
    def test_setup_creates_missing_configs_and_preserves_existing_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for template in setup.TEMPLATES:
                (root / template).write_text('template', encoding='utf-8')
            cookie = b"COOKIES='private-local-cookie'\r\n"
            (root / '.env').write_bytes(cookie)
            setup.initialize_configs(root)
            self.assertEqual((root / '.env').read_bytes(), cookie)
            self.assertEqual((root / 'weibo_config.json').read_text(), 'template')
            (root / 'douyin_config.yml').write_bytes(b'existing-custom-config')
            setup.initialize_configs(root)
            self.assertEqual((root / 'douyin_config.yml').read_bytes(), b'existing-custom-config')

    def test_launcher_resolves_runtime_in_chinese_path_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='Windows 部署 ') as directory:
            root = Path(directory)
            node = root / '.runtime' / 'node' / 'node.exe'
            node.parent.mkdir(parents=True)
            node.touch()
            (root / '.runtime' / 'windows-runtime.json').write_text(json.dumps({'node': '.runtime/node/node.exe'}))
            environment = launcher.runtime_environment(root)
            self.assertEqual(environment['PATH'].split(os.pathsep)[0], str(node.parent))
            self.assertEqual(environment['PLAYWRIGHT_BROWSERS_PATH'], str(root / '.runtime' / 'browsers'))

    def test_launcher_reports_missing_setup_or_moved_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(RuntimeError, 'Setup.bat'):
                launcher.runtime_environment(root)
            (root / '.runtime').mkdir()
            (root / '.runtime' / 'windows-runtime.json').write_text(json.dumps({'node': 'missing/node.exe'}))
            with self.assertRaisesRegex(RuntimeError, 'moved'):
                launcher.runtime_environment(root)

    def test_unverified_node_archive_is_not_extracted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def fake_download(url, destination):
                if url.endswith('SHASUMS256.txt'):
                    destination.write_text('0' * 64 + f'  node-v{setup.NODE_VERSION}-win-x64.zip\n')
                else:
                    destination.write_bytes(b'corrupted-archive')
            with patch.object(setup, 'ROOT', root), patch.object(setup, 'supported_node', return_value=False), patch.object(setup, 'download', side_effect=fake_download):
                with self.assertRaisesRegex(RuntimeError, 'SHA-256'):
                    setup.install_node()
            self.assertFalse((root / '.runtime' / 'node').exists())


if __name__ == '__main__':
    unittest.main()
