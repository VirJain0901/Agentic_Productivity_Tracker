import asyncio #func defined as async should run in coroutine 
from datetime import timedelta, datetime # to get the difference between two datetimes
import psutil # process utilization to get the active processes
import pywinctl # to get the active window
import getpass # get the system log in username
import os, logging #  logging for info errors warnings in tracker.log os to store the file
import django # to import the models
from asgiref.sync import sync_to_async #(asynchronous server gateway) db operations are sync by default so need to convert it to async
from django.utils import timezone
import time
from collections import defaultdict
import sys
sys.stdout.reconfigure(encoding='utf-8')
from django.conf import settings
import requests
import platform
import ctypes
import argparse
import re
import winreg
from urllib.parse import urlparse
from django.db.models import F
import pyautogui
from logging.handlers import RotatingFileHandler
import glob
from django.db import transaction
import json
import hashlib

# ------------------- Django setup -------------------
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'employee_tracker.settings') 
django.setup()

from monitoring.models import Employee, IdleTime, ProductiveAppUsage, Session, ActivityLog, BlockedWebsiteAttempt, ScreenshotLog

# ------------------- Log File Setup -------------------

log_file = os.path.join(
    settings.BASE_DIR,
    'tracker.log'
)

# Rotating log handler
handler = RotatingFileHandler(
    log_file,
    maxBytes=5 * 1024 * 1024,  # 5 MB max per log file
    backupCount=3,             # Keep 3 backup logs, auto deletes oldest log when max size is reached
    encoding='utf-8'
)

# Log format
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)

handler.setFormatter(formatter)

# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# constants
CHECK_INTERVAL = 2  # seconds between checks
IDLE_THRESHOLD = 600  # 10 minutes (600 seconds)
SCREENSHOT_RETENTION_DAYS = 7
CURRENT_BLOCKLIST = []
SERVER_ONLINE = True
PRODUCTIVE_APPS = {
    "chrome.exe", "code.exe", "excel.exe", "word.exe", "google-drive.exe", "mongod.exe", "mongo.exe", "kubectl.exe",
    "python.exe", "zoom.exe", "unity.exe", "teams.exe", "mongodb.exe", "mysql.exe", "postgres.exe",
    "apache.exe", "outlook.exe", "powerpnt.exe", "postman.exe", "figma.exe",
    "visualstudio.exe", "npm.exe", "powerbi.exe", "eclipse.exe", "intellij.exe", "pycharm.exe",
    "docker.exe", "netbeans.exe", "firefox.exe", "msedge.exe", "discord.exe",
    "git.exe", "github.exe","ms-teams.exe"
}
BUFFER_SAVE_INTERVAL = 60 # after every 60 seconds save the app usage buffer to DB
ACTIVITY_LOG_BUFFER = []
BLOCKED_ATTEMPT_BUFFER = []
DB_BATCH_SIZE = 20
BLOCKED_SITE_COOLDOWN = 300 # 5 miin cooldown
last_blocked_log_time = {}

BLOCKLIST_API = os.getenv("EMPLOYEE_TRACKER_BLOCKLIST_URL", "http://127.0.0.1:8000/api/blocklist/")
HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts" if platform.system() == "Windows" else "/etc/hosts"
REDIRECT_IP = "127.0.0.1"

DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
SCREENSHOT_DIR = os.path.join(
    settings.BASE_DIR,
    "screenshots"
)
OFFLINE_QUEUE_FILE = "offline_queue.json"
os.makedirs(
    SCREENSHOT_DIR,
    exist_ok=True
)

def is_admin():
    """Check if the script is running with admin/root rights."""
    if platform.system() == "Windows":
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    else:
        return os.geteuid() == 0  # On Linux/Mac

def set_browser_policy(
    registry_path,
    policy_name,
    value
):

    try:

        key = winreg.CreateKey(
            winreg.HKEY_LOCAL_MACHINE,
            registry_path
        )

        winreg.SetValueEx(
            key,
            policy_name,
            0,
            winreg.REG_DWORD,
            value
        )

        winreg.CloseKey(key)

        logging.info(
            "%s updated successfully",
            policy_name
        )

    except Exception as e:

        logging.error(
            "Policy update failed: %s",
            str(e)
        )

def disable_all_private_browsing():

    set_browser_policy(
        r"SOFTWARE\Policies\Google\Chrome",
        "IncognitoModeAvailability",
        1
    )

    set_browser_policy(
        r"SOFTWARE\Policies\Microsoft\Edge",
        "InPrivateModeAvailability",
        1
    )

    set_browser_policy(
        r"SOFTWARE\Policies\Opera Software\Opera",
        "PrivateModeAvailability",
        1
    )

def enable_all_private_browsing():

    set_browser_policy(
        r"SOFTWARE\Policies\Google\Chrome",
        "IncognitoModeAvailability",
        0
    )

    set_browser_policy(
        r"SOFTWARE\Policies\Microsoft\Edge",
        "InPrivateModeAvailability",
        0
    )

    set_browser_policy(
        r"SOFTWARE\Policies\Opera Software\Opera",
        "PrivateModeAvailability",
        0
    )

# ---------------- FIREFOX PRIVATE BROWSING CONTROL ----------------

def disable_firefox_private():

    try:

        firefox_policy_dir = (
            r"C:\Program Files\Mozilla Firefox\distribution"
        )

        os.makedirs(
            firefox_policy_dir,
            exist_ok=True
        )

        policy_path = os.path.join(
            firefox_policy_dir,
            "policies.json"
        )

        policy_data = """
{
    "policies": {
        "DisablePrivateBrowsing": true
    }
}
"""

        with open(
            policy_path,
            "w"
        ) as file:

            file.write(policy_data)

        logging.info(
            "Firefox Private Browsing disabled"
        )

    except Exception as e:

        logging.error(
            "Firefox private browsing block failed: %s",
            str(e)
        )


def enable_firefox_private():

    try:

        policy_path = (
            r"C:\Program Files\Mozilla Firefox\distribution\policies.json"
        )

        if os.path.exists(policy_path):

            os.remove(policy_path)

            logging.info(
                "Firefox Private Browsing enabled"
            )

    except Exception as e:

        logging.error(
            "Firefox private browsing enable failed: %s",
            str(e)
        )

def get_blocklist():

    global SERVER_ONLINE

    try:
        headers = {}
        token = os.getenv("AGENT_AUTH_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        res = requests.get(BLOCKLIST_API, headers=headers, timeout=5)
        res.raise_for_status()
        SERVER_ONLINE = True
        return res.json().get("blocklist", [])
        
    except Exception as e:

        SERVER_ONLINE = False

        logging.error(
            "Backend connection failed: %s",
            str(e)
        )

        return CURRENT_BLOCKLIST


def normalize_blocklist(blocklist):
    """
    Convert blocklist entries into clean hostnames.
    Handles:
      - full URLs (extracts hostname via urlparse)
      - bare domains
      - adds both www and non-www versions
    """
    normalized = set()

    for site in blocklist:
        site = site.strip().lower()

        # If entry looks like a URL → extract hostname
        if "://" in site:
            parsed = urlparse(site)
            host = parsed.hostname or site
        else:
            host = site

        host = host.strip(".")
        if not DOMAIN_RE.match(host):
            continue

        # normalize
        if host.startswith("www."):
            normalized.add(host)
            normalized.add(host[4:])
        else:
            normalized.add(host)
            normalized.add("www." + host)

    return normalized


def update_hosts(blocklist):
    """Update hosts file with normalized blocklist."""
    normalized = normalize_blocklist(blocklist)

    # backup hosts before editing
    if not os.path.exists(HOSTS_PATH + ".bak"):
        import shutil
        shutil.copy(HOSTS_PATH, HOSTS_PATH + ".bak")

    # read existing hosts file
    with open(HOSTS_PATH, "r") as file:
        lines = file.readlines()

    # keep only non-managed lines
    new_lines = [line for line in lines if "#BLOCKED" not in line]
    
    # add updated blocklist
    for site in sorted(normalized):
        new_lines.append(f"{REDIRECT_IP} {site} #BLOCKED\n")

    # write back to hosts
    try:
        with open(HOSTS_PATH, "w") as file:
            file.writelines(new_lines)

    except PermissionError:
        logging.error(
            "Permission denied while updating hosts file"
        )

    except Exception as e:
        logging.error(
            "Hosts file update failed: %s",
            str(e)
        )

    print(f"✅ Hosts file synced with {len(normalized)} entries from Django blocklist")

async def sync_blocklist(): # # Async background task for periodic blocklist synchronization, runs independently without blocking tracker
    while True: # Continuously sync blocklist from backend API
        global CURRENT_BLOCKLIST
        try: # Prevent tracker failure during sync errors
            CURRENT_BLOCKLIST = get_blocklist() # Fetch blocklist from Django API
            update_hosts(CURRENT_BLOCKLIST) # Update hosts file with new blocklist

            if SERVER_ONLINE:
                logging.info(
                    "Backend connected successfully"
                )

            else:

                logging.warning(
                    "Running in offline mode"
                )

        except Exception as e:
            logging.error(
                "Blocklist sync failed: %s",
                str(e)
            )

        await asyncio.sleep(300)

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.c_uint),
        ('dwTime', ctypes.c_uint),
    ]


def get_idle_seconds():
    last_input_info = LASTINPUTINFO()

    last_input_info.cbSize = ctypes.sizeof(
        LASTINPUTINFO
    )

    ctypes.windll.user32.GetLastInputInfo(
        ctypes.byref(last_input_info)
    )

    millis = (
        ctypes.windll.kernel32.GetTickCount()
        - last_input_info.dwTime
    )

    return millis / 1000.0

def get_active_app():
    try:
        window = pywinctl.getActiveWindow()
        if not window:
            return "Unknown", "Unknown Window"
        pid = window.getPID()
        try:
            process = psutil.Process(pid) # get the process using the PID of the active window
            app_name = process.name()
            window_title = window.title if window.title else "Unknown Title" 
            # Log the detected active app
            return app_name, window_title
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return "Unknown", "Unknown Window"
    except Exception as e:
        logging.error("Error getting active app: %s", e)
        return "Unknown", "Unknown Window"

@sync_to_async
def get_employee():
    username = getpass.getuser()
    try:
        return Employee.objects.get(system_username=username)
    except Employee.DoesNotExist:
        logging.error("No employee found with username %s", username)
        exit(1)

@sync_to_async
def create_idle_time(employee, idle_start, now):
    return IdleTime.objects.create(
        employee=employee,
        start_time=idle_start,
        end_time=now,
        total_idle_sec=int((now - idle_start).total_seconds())
    )

@sync_to_async
def increment_app_usage(employee, app_name, date, duration):
    record, _ = ProductiveAppUsage.objects.get_or_create(
        employee=employee,
        app_name=app_name,
        date=date,
        defaults={'total_time_sec': 0}
    )
    ProductiveAppUsage.objects.filter(pk=record.pk).update(
        total_time_sec=F("total_time_sec") + int(duration)
    )

@sync_to_async
def bulk_save_activity_logs(logs):

    if not logs:
        return 
    try:
        with transaction.atomic():
            ActivityLog.objects.bulk_create(logs)
        logs.clear()
    except Exception as e:
        logging.error(
            "Bulk save of activity logs failed: %s",
            str(e)
        )
        offline_records=[]
        for log in logs:
            offline_records.append({
                "employee_id": log.employee_id,
                "app_name": log.app_name,
                "window_title": log.window_title,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None # prevents crash if timestamp is missing
            })
        save_to_offline_queue(offline_records)
        logs.clear()

async def sync_offline_queue():

    while True:

        try:

            if os.path.exists(OFFLINE_QUEUE_FILE):

                with open(OFFLINE_QUEUE_FILE, "r") as f:
                    queue = json.load(f)

                if queue:

                    logging.info(
                        "Syncing offline activity logs..."
                    )

                    logs_to_save = []

                    for item in queue:

                        logs_to_save.append(
                            ActivityLog(
                                employee_id=item["employee_id"],
                                app_name=item["app_name"],
                                window_title=item["window_title"],
                                timestamp=item["timestamp"]
                            )
                        )

                    await bulk_save_activity_logs(
                        logs_to_save
                    )

                    # clear file after success
                    open(
                        OFFLINE_QUEUE_FILE,
                        "w"
                    ).write("[]")

                    logging.info(
                        "Offline logs synced successfully."
                    )

        except Exception as e:

            logging.error(
                "Offline sync failed: %s",
                str(e)
            )

        await asyncio.sleep(60)

@sync_to_async
def bulk_save_blocked_attempts(attempts):

    if attempts:
        with transaction.atomic():

            BlockedWebsiteAttempt.objects.bulk_create(attempts)

        attempts.clear()

@sync_to_async
def create_session(employee, start_time):
    return Session.objects.create(
        employee=employee,
        start_time=start_time,
        end_time=None,
        total_time_sec=0
    )

@sync_to_async
def update_session(session, end_time):
    session.end_time = end_time
    session.total_time_sec = int((end_time - session.start_time).total_seconds())
    session.save()

# Async db function to create screenshot log entry
@sync_to_async
def create_screenshot_log(employee,file_path,file_hash):
    return ScreenshotLog.objects.create(
        employee=employee,
        file_path=file_path,
        metadata_hash=file_hash 
    )

#  Save app usage  
async def save_app_usage(employee, app_usage):  # save the app usage every BUFFER_SAVE_INTERVAL
    if not app_usage:  # if the dictionary {app:time} is empty then return
        return

    today = timezone.now().date()
    saved_count = 0

    for app_name, duration in app_usage.items():
        if duration < 1:  # ignore app usage less than 1 sec
            continue

        await increment_app_usage(employee, app_name, today, duration)
        saved_count += 1

    app_usage.clear()  # clear buffer after saving
    logging.info("Saved app usage: %d records", saved_count)

def send_activity_data(activity_dict):
    logging.info(
        "Activity Data Sent: %s",
        activity_dict
    )


def send_idle_data(idle_dict):
    logging.info(
        "Idle Data Sent: %s",
        idle_dict
    )


def send_screenshot_metadata(meta_dict):
    logging.info(
        "Screenshot Metadata Sent: %s",
        meta_dict
    )

# Async background task for periodic screenshot capture
async def capture_screenshots(employee):
    while True:
        print("Screenshot task is running...")
        try:
            now = datetime.now()
            print("Capturing screenshot...")

            # Create Date and Hour folder structure
            date_folder = now.strftime("%Y-%m-%d")
            hour_folder = now.strftime("%H")
            target_dir = os.path.join(SCREENSHOT_DIR, date_folder, hour_folder)
            os.makedirs(target_dir, exist_ok=True)

            # Hash metadata for a compressed, unique filename
            # Combining username and precise timestamp to guarantee uniqueness
            raw_meta = f"{employee.system_username}_{now.timestamp()}"
            file_hash = hashlib.md5(raw_meta.encode()).hexdigest()
            
            file_name = f"{file_hash}.png"
            file_path = os.path.join(target_dir, file_name)

            # Capture and save (using optimize=True for slight compression)
            screenshot = pyautogui.screenshot()
            screenshot.save(file_path, optimize=True)           
            await create_screenshot_log(
                employee,
                file_path,
                file_hash
            )

            # 4. Screenshot metadata with hash
            screenshot_metadata = {
                "hash_id": file_hash,
                "timestamp": now.isoformat(),
                "file_path": file_path
            }        
            send_screenshot_metadata(screenshot_metadata)        
            logging.info("Screenshot captured and hashed: %s",file_path)
        except Exception as e:
            logging.error("Screenshot capture failed: %s",str(e))
        await asyncio.sleep(30)    # Wait 30 seconds before next screenshot


# Async background task for periodic cleanup of old screenshots
@sync_to_async
def cleanup_old_screenshots():
    # Make sure this matches the updated path!
    screenshot_dir = os.path.join(settings.BASE_DIR, "media", "screenshots")

    if not os.path.exists(screenshot_dir):
        return

    now = time.time()

    # Find all png screenshots recursively in subfolders
    screenshot_files = glob.glob(
        os.path.join(screenshot_dir, "**", "*.png"), 
        recursive=True
    )

    for file_path in screenshot_files:
        try:
            file_age = now - os.path.getmtime(file_path)

            if file_age > SCREENSHOT_RETENTION_DAYS * 86400:
                os.remove(file_path)
                logging.info(
                    "Deleted old screenshot: %s",
                    os.path.basename(file_path)
                )
                
                # Clean up empty hour/date directories to prevent clutter
                parent_dir = os.path.dirname(file_path)
                if not os.listdir(parent_dir):
                    os.rmdir(parent_dir)

        except Exception as e:
            logging.error("Screenshot cleanup failed: %s", str(e))



async def periodic_screenshot_cleanup():

    while True:

        try:

            await cleanup_old_screenshots()

            logging.info(
                "Periodic screenshot cleanup completed"
            )

        except Exception as e:

            logging.error(
                "Screenshot cleanup task failed: %s",
                str(e)
            )

        # Run cleanup every 6 hours
        await asyncio.sleep(21600)

def restore_hosts_file():

    backup_path = HOSTS_PATH + ".bak"

    if os.path.exists(backup_path):

        import shutil

        shutil.copy(
            backup_path,
            HOSTS_PATH
        )

        logging.info(
            "Hosts file restored successfully"
        )

@sync_to_async
def update_employee_status(
    employee,
    status
):

    employee.status = status
    employee.last_seen = timezone.now()

    employee.save()

def save_to_offline_queue(record):

    try:

        if os.path.exists(OFFLINE_QUEUE_FILE):

            with open(
                OFFLINE_QUEUE_FILE,
                "r"
            ) as f:

                queue = json.load(f)

        else:

            queue = []

        queue.append(record)

        with open(
            OFFLINE_QUEUE_FILE,
            "w"
        ) as f:

            json.dump(
                queue,
                f
            )

    except Exception as e:

        logging.error(
            "Offline queue save failed: %s",
            str(e)
        )

#Tracker coroutine 
async def track_usage(employee):
    current_app = None
    previous_app = None
    last_logged_app = None
    last_logged_window = None
    prev_time = timezone.now()
    idle_start = None
    idle_logged = False
    app_usage = defaultdict(float)
    session = None
    last_save_time = time.time()

    # Create a new session
    session_start = timezone.now()
    session = await create_session(employee, session_start)

    try:
        while True:
            now = timezone.now()
            current_time = time.time()

            try:
                # ── Get active app ────────────────────────────────
                app_name, window_title = get_active_app()

                activity_data = {
                    "timestamp": now.isoformat(),
                    "app_name": app_name,
                    "window_title": window_title
                }
                send_activity_data(activity_data)

                # ── Buffer activity log if app/window changed ─────
                if (
                    app_name != last_logged_app
                    or window_title != last_logged_window
                ):
                    ACTIVITY_LOG_BUFFER.append(
                        ActivityLog(
                            employee=employee,
                            app_name=app_name,
                            window_title=window_title,
                            timestamp=now
                        )
                    )

                    if len(ACTIVITY_LOG_BUFFER) >= DB_BATCH_SIZE:
                        await bulk_save_activity_logs(ACTIVITY_LOG_BUFFER)

                    last_logged_app = app_name
                    last_logged_window = window_title

                app_name_lower = app_name.lower()

                # ── Detect blocked website attempts ───────────────
                for blocked_site in CURRENT_BLOCKLIST:

                    site_name = blocked_site.replace("www.", "").lower()

                    ignored_titles = [
                        "django",
                        "visual studio code",
                        "127.0.0.1",
                        "localhost",
                        "admin"
                    ]

                    if any(
                        ignored in window_title.lower()
                        for ignored in ignored_titles
                    ):
                        continue

                    if site_name in window_title.lower():
                        current_timestamp = time.time()
                        last_logged = last_blocked_log_time.get(site_name, 0)

                        if (current_timestamp - last_logged < BLOCKED_SITE_COOLDOWN):
                            break

                        BLOCKED_ATTEMPT_BUFFER.append(
                            BlockedWebsiteAttempt(
                                employee=employee,
                                website=blocked_site,
                                app_name=app_name,
                                window_title=window_title,
                                timestamp=now
                            )
                        )

                        if len(BLOCKED_ATTEMPT_BUFFER) >= DB_BATCH_SIZE:
                            await bulk_save_blocked_attempts(
                                BLOCKED_ATTEMPT_BUFFER
                            )

                        logging.warning(
                            "Blocked website attempt detected: %s",
                            blocked_site
                        )

                        last_blocked_log_time[site_name] = current_timestamp
                        break

                # ── Idle detection ────────────────────────────────
                idle_seconds = get_idle_seconds()

                logging.info("Idle seconds detected: %s", idle_seconds)

                if idle_seconds >= IDLE_THRESHOLD:
                    # User is idle
                    if idle_start is None:
                        idle_start = now - timedelta(seconds=idle_seconds)
                        idle_logged = False

                    await update_employee_status(employee, "Idle")

                    logging.info(
                        "User currently idle: %d sec",
                        int((now - idle_start).total_seconds())
                    )

                    # Don't count app usage during idle
                    prev_time = now
                    duration = 0

                else:
                    # User is active
                    await update_employee_status(employee, "Active")

                    if idle_start:
                        # Idle session just ended — save it
                        await create_idle_time(employee, idle_start, now)
                        logging.info(
                            "Idle recorded: %d sec",
                            int((now - idle_start).total_seconds())
                        )
                        idle_start = None
                        idle_logged = False

                    # Calculate active duration
                    duration = (now - prev_time).total_seconds()
                    prev_time = now

                    # Accumulate app usage
                    if current_app:
                        app_usage[current_app] += duration

                    # Check if productive app
                    is_productive = app_name_lower in PRODUCTIVE_APPS
                    if not is_productive:
                        app_name_lower = "Other"

                    # Log only if app changed
                    if app_name_lower != previous_app:
                        logging.info("Detected active app: %s", app_name)
                        previous_app = app_name_lower

                    current_app = app_name_lower

                # ── Periodic buffer save ──────────────────────────
                if current_time - last_save_time >= BUFFER_SAVE_INTERVAL:
                    await save_app_usage(employee, app_usage)
                    last_save_time = current_time
                    last_blocked_log_time.clear()
                    logging.info("Saved app usage buffer")

            except Exception as e:
                logging.error("Error in tracking loop: %s", str(e))

            await asyncio.sleep(CHECK_INTERVAL)

    except asyncio.CancelledError:
        # Clean shutdown — save everything
        await save_app_usage(employee, app_usage)

        if idle_start:
            await create_idle_time(employee, idle_start, timezone.now())

        session_end = timezone.now()
        await update_session(session, session_end)
        logging.info(
            "Session ended: Duration %d seconds",
            session.total_time_sec
        )

        await bulk_save_activity_logs(ACTIVITY_LOG_BUFFER)
        await bulk_save_blocked_attempts(BLOCKED_ATTEMPT_BUFFER)
        await update_employee_status(employee, "Offline")
        raise


async def run_activity_tracker():
    employee = await get_employee()
    await track_usage(employee)


def main():
    if not is_admin():
        print("Please run this script as Administrator.")
        sys.exit(1)

    print("Fetching employee...")

    disable_all_private_browsing()
    disable_firefox_private()

    async def run():
        employee = await get_employee()
        print("Employee found:", employee)
        try:
            await asyncio.gather(
                track_usage(employee),
                sync_blocklist(),
                capture_screenshots(employee),
                periodic_screenshot_cleanup(),
                sync_offline_queue()
            )
        finally:
            enable_all_private_browsing()
            enable_firefox_private()
            logging.info("Tracker stopped, private browsing re-enabled")

    try:
        asyncio.run(run())

    except KeyboardInterrupt:
        restore_hosts_file()
        logging.info("Tracker stopped manually by user.")
        print("\nTracker stopped safely.")
        logging.warning(
            "Remaining buffers not flushed — ORM migration pending"
        )

    except Exception as e:
        logging.error("Tracker error: %s", str(e))


if __name__ == "__main__":
    main()
