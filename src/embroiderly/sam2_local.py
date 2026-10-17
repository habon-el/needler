"""Optional isolated SAM2 bridge. Existing app Python/dependencies stay unchanged."""
import atexit
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import select
import subprocess
import threading
import time

import numpy as np
from PIL import Image

RUNTIME = Path(__file__).resolve().parents[2] / 'work/sam2-runtime'
_lock = threading.Lock()
_process = None


def available():
    return (os.environ.get('EMBROIDERLY_SAM2_LOCAL', '1') != '0'
            and (RUNTIME/'venv/bin/python').is_file()
            and (RUNTIME/'sam2.1_hiera_tiny.pt').is_file())


def close():
    global _process
    if _process is not None:
        if _process.poll() is None:
            _process.terminate()
            try: _process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                _process.kill(); _process.wait(timeout=3)
        for stream in (_process.stdin, _process.stdout):
            stream.close()
        _process = None


atexit.register(close)


def request(data):
    """Serialized bounded IPC; never pass the server's API key to the worker."""
    global _process
    with _lock:
        if _process is None or _process.poll() is not None:
            close()
            if not available(): raise RuntimeError('Local SAM2 runtime is not installed.')
            _process = subprocess.Popen([
                str(RUNTIME/'venv/bin/python'), '-I', '-u',
                str(Path(__file__).with_name('sam2_worker.py')),
                str(RUNTIME/'sam2.1_hiera_tiny.pt')],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'OMP_NUM_THREADS': '4'},
                cwd=str(RUNTIME), bufsize=0)
        try:
            deadline = time.monotonic()+120
            pending = memoryview((json.dumps(data, allow_nan=False)+'\n').encode())
            fd = _process.stdin.fileno()
            os.set_blocking(fd, False)
            while pending:
                remaining = deadline-time.monotonic()
                if remaining <= 0 or not select.select([], [fd], [], remaining)[1]:
                    raise TimeoutError('Local SAM2 took too long; use manual selection or retry.')
                try: written = os.write(fd, pending[:65536])
                except BlockingIOError: continue
                if not written: raise RuntimeError('Local SAM2 stopped; retry.')
                pending = pending[written:]
            chunks = bytearray()
            while not chunks.endswith(b'\n'):
                remaining = deadline-time.monotonic()
                if remaining <= 0 or not select.select([_process.stdout], [], [], remaining)[0]:
                    raise TimeoutError('Local SAM2 took too long; use manual selection or retry.')
                chunk = os.read(_process.stdout.fileno(), 65536)
                if not chunk: raise RuntimeError('Local SAM2 stopped; use manual selection or retry.')
                chunks.extend(chunk)
                if len(chunks)>32_000_000: raise RuntimeError('Local SAM2 response was too large.')
            result = json.loads(chunks)
            if 'error' in result: raise RuntimeError(result['error'])
            return result
        except Exception:
            close()
            raise


class Predictor:
    """Small predictor-compatible proxy, keeping one model outside Flask."""
    def set_image(self, rgb):
        stream = io.BytesIO(); Image.fromarray(rgb).save(stream, format='PNG')
        self.encoded = base64.b64encode(stream.getvalue()).decode('ascii')
        self.key = hashlib.sha256(stream.getvalue()).hexdigest()
        request({'op':'encode', 'key':self.key, 'image':self.encoded})

    def predict(self, **args):
        # Idempotent encode also recovers embeddings after a worker failure.
        request({'op':'encode', 'key':self.key, 'image':self.encoded})
        result = request({'op':'predict', 'key':self.key,
                          'args':{k:v.tolist() if isinstance(v,np.ndarray) else v for k,v in args.items()}})
        shape = result['shape']
        masks = np.unpackbits(np.frombuffer(base64.b64decode(result['masks']), dtype=np.uint8),
                              count=int(np.prod(shape))).reshape(shape).astype(bool)
        return masks, np.asarray(result['scores']), None
