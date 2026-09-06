"""Start local services and reliably terminate all children on Ctrl+C."""
import os
import signal
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
processes = []
try:
    for directory, command in [
        ("backend", ["uv", "run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]),
        ("backend", ["uv", "run", "python", "-m", "app.worker"]),
        ("frontend", ["npm", "run", "dev", "--", "--port", "5173", "--strictPort"]),
    ]:
        processes.append(subprocess.Popen(command, cwd=root / directory, start_new_session=True))
    print("RailShield: http://localhost:5173 | API: http://localhost:8000/docs", flush=True)
    while all(p.poll() is None for p in processes):
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    for process in processes:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
