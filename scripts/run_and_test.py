import subprocess
import time
import sys
import os
import urllib.request

PYTHON_EXE = os.path.abspath("backend/venv/Scripts/python.exe")

def kill_port_8000():
    try:
        out = subprocess.check_output('netstat -aon | findstr :8000 | findstr LISTENING', shell=True).decode()
        for line in out.strip().splitlines():
            parts = line.split()
            if len(parts) >= 5:
                pid = parts[-1]
                print(f"[CLEANUP] Killing lingering process PID {pid} on port 8000...")
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
    except Exception:
        pass

def main():
    kill_port_8000()
    time.sleep(1)

    print("[1/3] Starting Uvicorn server on http://127.0.0.1:8000...")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(".")
    proc = subprocess.Popen(
        [PYTHON_EXE, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        env=env
    )

    # Wait for server to respond
    server_ready = False
    for i in range(20):
        time.sleep(0.5)
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2) as resp:
                if resp.status == 200:
                    server_ready = True
                    break
        except Exception:
            pass

    if not server_ready:
        print("[ERROR] Server failed to start within 10 seconds.")
        proc.kill()
        stdout, stderr = proc.communicate()
        print("STDOUT:", stdout.decode(errors="replace"))
        print("STDERR:", stderr.decode(errors="replace"))
        sys.exit(1)

    print("[2/3] Server is live and healthy. Executing automated test suite...")
    
    # Run test script
    test_result = subprocess.run(
        [PYTHON_EXE, "scripts/test_live_server.py"],
        capture_output=True,
        text=True
    )
    print(test_result.stdout)
    if test_result.stderr:
        print("STDERR:", test_result.stderr)

    print("[3/3] Shutting down test server...")
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()

    if test_result.returncode != 0:
        print("[FAILURE] Some tests failed!")
        sys.exit(1)
    else:
        print("[SUCCESS] All system verifications succeeded cleanly!")

if __name__ == "__main__":
    main()
