import os
import sys
import time
import logging
import re
import requests
from urllib.parse import urlparse
import socket
import shutil
import os

print("=" * 60)
print("AGENT STARTED")
print("PID:", os.getpid())
print("PPID:", os.getppid())
print("=" * 60)
# 1. System Logging Configuration
logging.basicConfig(
    filename='system_agent.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("AxonDeskAgent")

# 2. Configuration
BACKEND_URL = os.getenv("EMPLOYEE_TRACKER_POLICY_URL", "http://127.0.0.1:8000/api/monitoring/policies/")
BASE_URL = os.getenv("EMPLOYEE_TRACKER_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
HEARTBEAT_URL = f"{BASE_URL}/api/monitoring/heartbeat/"

POLLING_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "60"))
REDIRECT_IP = "127.0.0.1"

MARKER_START = "# --- SYSTEM MANAGED BLOCKLIST START ---\n"
MARKER_END = "# --- SYSTEM MANAGED BLOCKLIST END ---\n"

DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")

CURRENT_POLICY_VERSION = "0.0.0"

TOKEN_CACHE = {"access": None}

if os.name == 'nt':
    HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
else:
    HOSTS_PATH = "/etc/hosts"


# ---------------- AUTH ---------------- #

def get_new_token():
    try:
        response = requests.post(f"{BASE_URL}/api/token/", json={
            "username": os.getenv("AGENT_USERNAME"),
            "password": os.getenv("AGENT_PASSWORD")
        }, timeout=5)

        print(response.status_code)
        print(response.text)

        if response.status_code == 200:
            data = response.json()
            TOKEN_CACHE["access"] = data["access"]
            logger.info("JWT token fetched successfully")
            return data["access"]

        logger.error(f"Login failed: {response.text}")
        return None

    except Exception as e:
        logger.error(f"Token fetch error: {e}")
        return None


def get_auth_token():
    if TOKEN_CACHE["access"]:
        return TOKEN_CACHE["access"]
    return get_new_token()


# ---------------- UTILS ---------------- #

def env_bool(name, default=True):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def normalize_domain(value):
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    if "://" in raw:
        raw = urlparse(raw).hostname or ""
    raw = raw.strip(".")
    if raw.startswith("www."):
        raw = raw[4:]
    if not DOMAIN_RE.match(raw):
        return None
    return raw


def check_system_permissions():
    try:
        with open(HOSTS_PATH, 'r+'):
            pass
        logger.info("Permission check passed")
        
    except PermissionError:
        logger.critical("Run as Administrator/Root required")
        sys.exit(1)


# ---------------- HEARTBEAT ---------------- #

def send_heartbeat():
    token = get_auth_token()
    if not token:
        logger.warning("No token available for heartbeat")
        return

    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "hostname": socket.gethostname(),
        "policy_version": CURRENT_POLICY_VERSION,
        "agent_version": "1.0.0",
        "status": "healthy"
    }

    try:
        res = requests.post(HEARTBEAT_URL, json=payload, headers=headers, timeout=5)

        if res.status_code == 401:
            logger.warning("Heartbeat token expired, refreshing...")
            get_new_token()
            headers["Authorization"] = f"Bearer {TOKEN_CACHE['access']}"
            requests.post(HEARTBEAT_URL, json=payload, headers=headers, timeout=5)
            return

        res.raise_for_status()
        logger.info("Heartbeat sent successfully")

    except Exception as e:
        logger.error(f"Heartbeat failed: {e}")


# ---------------- POLICIES ---------------- #

def fetch_blocked_policies():
    global CURRENT_POLICY_VERSION

    token = get_auth_token()
    if not token:
        logger.error("No auth token available")
        return None

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(BACKEND_URL, headers=headers, timeout=(5, 10))

        if response.status_code == 401:
            logger.warning("Token expired during policy fetch, refreshing...")
            get_new_token()
            headers["Authorization"] = f"Bearer {TOKEN_CACHE['access']}"
            response = requests.get(BACKEND_URL, headers=headers, timeout=(5, 10))

        if response.status_code == 200:
            data = response.json()
            print("Server RESPONSE:", data)
            
            CURRENT_POLICY_VERSION = data.get("policy_version", "0.0.0")
            return data.get("blocked_domains") or data.get("blocklist") or []

        logger.warning(f"Policy fetch failed: {response.status_code}")
        return None

    except Exception as e:
        logger.error(f"Policy fetch error: {e}")
        return None


# ---------------- HOSTS ENFORCEMENT ---------------- #

def enforce_hosts_blocking(blocked_sites):
    if blocked_sites is None:
        return

    backup = HOSTS_PATH + ".bak"

    try:
        if os.path.exists(HOSTS_PATH):
            shutil.copy2(HOSTS_PATH, backup)
            with open(HOSTS_PATH, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        else:
            lines = []

        cleaned = []
        inside = False

        for line in lines:
            if line == MARKER_START:
                inside = True
                continue
            if line == MARKER_END:
                inside = False
                continue
            if not inside:
                cleaned.append(line)

        valid = set()

        for site in blocked_sites:
            norm = normalize_domain(site)
            if norm:
                valid.add(norm)

        block = [MARKER_START]

        for site in sorted(valid):
            block.append(f"{REDIRECT_IP} {site}\n")
            block.append(f"{REDIRECT_IP} www.{site}\n")

        block.append(MARKER_END)

        with open(HOSTS_PATH, 'w', encoding='utf-8') as f:
            f.writelines(cleaned + block)

        logger.info(f"Applied {len(valid)} block rules")

    except Exception as e:
        logger.error(f"Hosts update failed: {e}")
        if os.path.exists(backup):
            shutil.copy2(backup, HOSTS_PATH)


# ---------------- MAIN LOOP ---------------- #

def main():
   # check_system_permissions()
    print("ENTERED MAIN LOOP") 
    logger.info("Agent started")

    while True:
        try:
            sites = fetch_blocked_policies()
            print("BLOCKED SITES:", sites)
            if sites:
                enforce_hosts_blocking(sites)

            send_heartbeat()

        except Exception as e:
            logger.error(f"Main loop error: {e}")

        time.sleep(5)


if __name__ == "__main__":
   
    main()