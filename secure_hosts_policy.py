# secure_hosts_policy.py
import os
import sys
import re
import logging

logger = logging.getLogger("PolicyEnforcement")

# Clear block markers to prevent overlapping edits
START_MARKER = "# === AXONDESK MANAGED POLICY START ==="
END_MARKER   = "# === AXONDESK MANAGED POLICY END ==="

# Regex to strictly validate that input strings are valid domain names
DOMAIN_REGEX = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$")

def get_hosts_path():
    """Retrieves the target OS-specific absolute path to the system hosts file."""
    if sys.platform.startswith("win"):
        return os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32\\drivers\\etc\\hosts")
    return "/etc/hosts"

def validate_domain(domain: str) -> bool:
    """Validates that a string is a properly formatted domain name."""
    cleaned = domain.strip().lower()
    return bool(DOMAIN_REGEX.match(cleaned))

def enforce_blocklist(domains, hosts_path=None):
    """Safely synchronizes a list of domains inside a managed block context."""
    if hosts_path is None:
        hosts_path = get_hosts_path()

    if not os.path.exists(hosts_path):
        logger.error(f"Target hosts file not found at: {hosts_path}")
        return False

    # Structural check for administrative write privileges
    if not os.access(hosts_path, os.W_OK):
        logger.error("Insufficient write permissions. Please execute with administrator/root privileges.")
        return False

    try:
        with open(hosts_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except IOError as e:
        logger.error(f"Error reading hosts file: {e}")
        return False

    # Extract all unmanaged lines, stripping out the old managed block completely
    cleaned_lines = []
    inside_block = False
    for line in lines:
        if START_MARKER in line:
            inside_block = True
            continue
        if END_MARKER in line:
            inside_block = False
            continue
        if not inside_block:
            cleaned_lines.append(line)

    # Build the fresh managed block content with validation checks
    new_block = [f"{START_MARKER}\n"]
    for domain in domains:
        domain = domain.strip().lower()
        if validate_domain(domain):
            new_block.append(f"127.0.0.1    {domain}\n")
        else:
            logger.warning(f"Skipping malformed domain payload element: {domain}")
    new_block.append(f"{END_MARKER}\n")

    # Ensure trailing line spacing matches conventions
    if cleaned_lines and not cleaned_lines[-1].endswith("\n"):
        cleaned_lines[-1] += "\n"

    try:
        with open(hosts_path, "w", encoding="utf-8", newline="") as f:
            f.writelines(cleaned_lines + new_block)
        logger.info("Hosts-file policies written cleanly within managed markers.")
        return True
    except IOError as e:
        logger.error(f"Failed to commit hosts changes: {e}")
        return False