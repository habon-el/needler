"""Run legacy workspace acceptance on disposable artwork, never customer data.

Run: PYTHONPATH=src:work/deps python3 tests/browser_workspace_isolated.py
Requires Chromium and the locally installed stitch engine. No mocked playback.
"""
import runpy
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from PIL import Image, ImageDraw
from werkzeug.serving import make_server
from embroiderly.web import create_app


def main(scripts=('browser_workspace.py', 'browser_workspace_states.py')):
    # Never attach the shared CDP helper to an unrelated browser session.
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', 9229)) == 0:
            raise RuntimeError('Test browser port 9229 is busy; close the other test browser first.')
    for script in scripts:
        if '127.0.0.1:5050' in Path(__file__).with_name(script).read_text():
            raise RuntimeError('Workspace tests must not navigate to the customer application.')
    with tempfile.TemporaryDirectory(prefix='workspace-release-') as directory:
        root = Path(directory)
        app = create_app(root)
        source = root / 'work/uploads/workspace.png'
        image = Image.new('RGBA', (600, 500))
        draw = ImageDraw.Draw(image)
        draw.rectangle((100, 80, 450, 390), fill=(30, 70, 140, 255))
        image.save(source)
        server = make_server('127.0.0.1', 0, app, threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        browser = subprocess.Popen([
            'chromium', '--headless', '--no-sandbox', '--disable-gpu',
            '--remote-debugging-port=9229', '--remote-allow-origins=*',
            '--user-data-dir=' + str(root / 'browser'), 'about:blank',
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(2)
            Path('outputs').mkdir(exist_ok=True)
            context = {'WORKSPACE_URL': f'http://127.0.0.1:{server.server_port}/artwork/workspace.png'}
            for script in scripts:
                runpy.run_path(str(Path(__file__).with_name(script)), init_globals=context)
        finally:
            browser.terminate()
            browser.wait(timeout=15)
            server.shutdown()


if __name__ == '__main__':
    main()
