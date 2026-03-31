#!/usr/bin/env python3
"""
Deploy script for Telegram Reminder Bot

Uploads files to server via SSH/SFTP and restarts the bot.
"""
import os
import sys
import stat
from pathlib import Path
from io import StringIO

try:
    import paramiko
except ImportError:
    print("Installing paramiko...")
    os.system(f"{sys.executable} -m pip install paramiko")
    import paramiko

# Server configuration
SERVER_HOST = "84.54.30.233"
SERVER_PORT = 2089
SERVER_USER = "root"
SERVER_PATH = "/root/telegram_reminder_bot"
KEY_FILE = Path(__file__).parent / "deploy_key"
KEY_PASSPHRASE = "zxcvbita2014"

# Files and directories to upload
UPLOAD_ITEMS = [
    "bot.py",
    "config.py",
    "requirements.txt",
    "crypto/",
    "handlers/",
    "middleware/",
    "storage/",
    "utils/",
    "webapp/",
    "p2p/",
]

# Files to exclude
EXCLUDE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    ".git",
    ".env",
    "data/",
    "deploy_key",
    "deploy.py",
    "node_modules",
    ".vscode",
]


def should_exclude(path: str) -> bool:
    """Check if path should be excluded"""
    path_lower = path.lower()
    for pattern in EXCLUDE_PATTERNS:
        if pattern.startswith("*"):
            if path_lower.endswith(pattern[1:]):
                return True
        elif pattern in path_lower:
            return True
    return False


def upload_file(sftp, local_path: Path, remote_path: str):
    """Upload single file"""
    if should_exclude(str(local_path)):
        return False

    try:
        sftp.put(str(local_path), remote_path)
        print(f"  + {local_path.name}")
        return True
    except Exception as e:
        print(f"  ! Error uploading {local_path}: {e}")
        return False


def upload_directory(sftp, local_dir: Path, remote_dir: str):
    """Upload directory recursively"""
    if should_exclude(str(local_dir)):
        return 0

    # Create remote directory
    try:
        sftp.mkdir(remote_dir)
    except IOError:
        pass  # Directory exists

    uploaded = 0
    for item in local_dir.iterdir():
        if should_exclude(str(item)):
            continue

        remote_path = f"{remote_dir}/{item.name}"

        if item.is_file():
            if upload_file(sftp, item, remote_path):
                uploaded += 1
        elif item.is_dir():
            uploaded += upload_directory(sftp, item, remote_path)

    return uploaded


def main():
    print("=" * 50)
    print("Telegram Reminder Bot - Deploy")
    print("=" * 50)
    print(f"Server: {SERVER_USER}@{SERVER_HOST}:{SERVER_PORT}")
    print(f"Path: {SERVER_PATH}")
    print()

    # Check key file
    if not KEY_FILE.exists():
        print(f"ERROR: SSH key not found: {KEY_FILE}")
        print("Create deploy_key file with your SSH private key")
        sys.exit(1)

    # Load private key
    print("Loading SSH key...")
    try:
        key = paramiko.Ed25519Key.from_private_key_file(
            str(KEY_FILE),
            password=KEY_PASSPHRASE
        )
    except Exception as e:
        print(f"ERROR loading key: {e}")
        sys.exit(1)

    # Connect to server
    print(f"Connecting to {SERVER_HOST}:{SERVER_PORT}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            hostname=SERVER_HOST,
            port=SERVER_PORT,
            username=SERVER_USER,
            pkey=key,
            look_for_keys=False,
            allow_agent=False
        )
        print("Connected!")
    except Exception as e:
        print(f"ERROR connecting: {e}")
        sys.exit(1)

    # Open SFTP
    sftp = ssh.open_sftp()

    # Ensure remote directory exists
    try:
        sftp.mkdir(SERVER_PATH)
    except IOError:
        pass

    # Upload files
    print()
    print("Uploading files...")
    print("-" * 30)

    base_dir = Path(__file__).parent
    total_uploaded = 0

    for item_name in UPLOAD_ITEMS:
        local_path = base_dir / item_name
        remote_path = f"{SERVER_PATH}/{item_name.rstrip('/')}"

        if not local_path.exists():
            print(f"  ? Skipping {item_name} (not found)")
            continue

        if local_path.is_file():
            if upload_file(sftp, local_path, remote_path):
                total_uploaded += 1
        elif local_path.is_dir():
            print(f"  [{item_name}]")
            total_uploaded += upload_directory(sftp, local_path, remote_path)

    print("-" * 30)
    print(f"Uploaded: {total_uploaded} files")
    print()

    # Close SFTP
    sftp.close()

    # Restart bot
    print("Restarting bot...")
    stdin, stdout, stderr = ssh.exec_command(
        f"cd {SERVER_PATH} && chmod +x restart_all.sh && ./restart_all.sh"
    )

    # Wait and print output
    exit_status = stdout.channel.recv_exit_status()
    output = stdout.read().decode('utf-8', errors='replace')
    errors = stderr.read().decode('utf-8', errors='replace')

    if output:
        # Handle Windows console encoding issues
        try:
            print(output)
        except UnicodeEncodeError:
            print(output.encode('ascii', errors='replace').decode())
    if errors:
        try:
            print(f"Stderr: {errors}")
        except UnicodeEncodeError:
            print(f"Stderr: {errors.encode('ascii', errors='replace').decode()}")

    if exit_status == 0:
        print("Bot restarted successfully!")
    else:
        print(f"Restart exit code: {exit_status}")

    # Close SSH
    ssh.close()

    print()
    print("=" * 50)
    print("Deploy completed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
