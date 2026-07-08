import os
import time
import psutil
import subprocess
import logging
import sys

print("=" * 60)
print("WATCHDOG STARTED")
print("PID:", os.getpid())
print("=" * 60)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = os.path.join(PROJECT_DIR, "venv", "Scripts", "python.exe")
AGENT = os.path.join(PROJECT_DIR, "agent.py")

CHECK_INTERVAL = 10
LOCK_FILE = os.path.join(PROJECT_DIR, "watchdog.lock")
LOG_FILE = os.path.join(PROJECT_DIR, "watchdog.log")


# ---------------- LOGGING ----------------
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# ---------------- SINGLE INSTANCE ----------------
def ensure_single_instance():
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                pid = int(f.read().strip())

            if psutil.pid_exists(pid):
                print("Watchdog already running.")
                sys.exit(0)
        except:
            pass

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))


# ---------------- AGENT DETECTION (FIXED) ----------------
def find_agent():
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = proc.info["cmdline"]
            if not cmdline:
                continue

            cmd_str = " ".join(cmdline).lower()

            # stronger + safer check
            if "agent.py" in cmd_str and PROJECT_DIR.lower() in cmd_str:
                return proc

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return None


# ---------------- START AGENT ----------------
def start_agent():
    logging.info("Starting agent process")

    subprocess.Popen(
        [PYTHON, "-u", AGENT],
        cwd=PROJECT_DIR,
        shell=False,
        creationflags=subprocess.CREATE_NO_WINDOW
    )


# ---------------- MAIN LOOP ----------------
def main():
    ensure_single_instance()
    logging.info("Watchdog initialized")

    while True:
        agent = find_agent()

        if agent is None:
            logging.warning("Agent not found → restarting")
            start_agent()
        else:
            logging.info(f"Agent OK (PID={agent.pid})")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()