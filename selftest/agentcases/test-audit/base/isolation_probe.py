# isolation_probe.py
import pathlib
import subprocess
import sys

state = pathlib.Path("state.txt")
state.unlink(missing_ok=True)
a = subprocess.Popen([sys.executable, "-c", "import pathlib; pathlib.Path('state.txt').write_text('worker-a')"])
b = subprocess.Popen([sys.executable, "-c", "import pathlib, time; time.sleep(0.2); pathlib.Path('state.txt').write_text('worker-b')"])
a.wait()
b.wait()
seen = state.read_text()
state.unlink(missing_ok=True)
if seen != "worker-a":
    print(f"worker a sees {seen!r} in state.txt: workers share state.txt")
    sys.exit(1)
print("isolated")
