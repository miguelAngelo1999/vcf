"""VCF Processor updater - checks version and downloads updates from Google Drive"""
import sys
import os
import ssl
import urllib3
import warnings
import requests
import tempfile
import subprocess
import shutil
import time
from packaging.version import parse as parse_version

# SSL bypass + proxy
os.environ.update({
    'PYTHONHTTPSVERIFY': '0',
    'HTTP_PROXY': 'http://127.0.0.1:1090',
    'HTTPS_PROXY': 'http://127.0.0.1:1090',
})
ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings()
_orig_request = requests.Session.request
def _patched_request(self, method, url, **kwargs):
    kwargs['verify'] = False
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return _orig_request(self, method, url, **kwargs)
requests.Session.request = _patched_request

# --- Configuration ---
VERSION_FILE_ID = "1MdfgUQCU_iVcJb83QOdPe8c3N1dw1ypi"
INSTALLER_FILE_ID = "1_qbGHNQWXUhlobUbAl5t3YdD03NDrmoc"
INSTALLER_ASSET_NAME = "VCF_Processor_Installer.exe"
INSTALLER_PASSWORD = "123"


def get_launcher_path():
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, 'updater_launcher.exe')


def gdrive_download(file_id, destination):
    """Download file from Google Drive, handling large file confirmation."""
    import re
    session = requests.Session()
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    resp = session.get(url, stream=True, verify=False)

    # If we got the warning page, extract form action and params
    if 'text/html' in resp.headers.get('Content-Type', ''):
        html = resp.text
        action_match = re.search(r'action="([^"]+)"', html)
        if action_match:
            action = action_match.group(1).replace('&amp;', '&')
            inputs = re.findall(r'<input[^>]*name="([^"]*)"[^>]*value="([^"]*)"', html)
            params = {name: val for name, val in inputs}
            resp = session.get(action, params=params, stream=True, verify=False)

    with open(destination, 'wb') as f:
        for chunk in resp.iter_content(32768):
            if chunk:
                f.write(chunk)


def check_for_updates(current_version_str):
    """Check version.txt on Google Drive for latest version."""
    try:
        url = f"https://drive.google.com/uc?export=download&id={VERSION_FILE_ID}"
        resp = requests.get(url, timeout=10, verify=False)
        latest_version_str = resp.text.strip()

        current_v = parse_version(current_version_str)
        latest_v = parse_version(latest_version_str)

        if latest_v > current_v:
            return {
                "update_available": True,
                "latest_version": latest_version_str,
                "download_url": f"gdrive:{INSTALLER_FILE_ID}",
            }
        return {"update_available": False, "message": "You have the latest version"}
    except Exception as e:
        return {"update_available": False, "error": f"Update check failed: {e}"}


def download_and_run_installer(download_url, update_type='exe', password=''):
    """Download installer from Google Drive and launch updater_launcher."""
    try:
        if download_url.startswith('gdrive:'):
            file_id = download_url.replace('gdrive:', '')
        else:
            return {"success": False, "error": "Invalid download URL format"}

        temp_dir = tempfile.gettempdir()
        installer_path = os.path.join(temp_dir, INSTALLER_ASSET_NAME)
        gdrive_download(file_id, installer_path)

        if not os.path.exists(installer_path):
            return {"success": False, "error": "Failed to download installer"}

        original_launcher_path = get_launcher_path()
        if not os.path.exists(original_launcher_path):
            return {"success": False, "error": "updater_launcher.exe is missing."}

        temp_launcher_path = os.path.join(temp_dir, f"launcher_{int(time.time())}.exe")
        shutil.copy(original_launcher_path, temp_launcher_path)

        subprocess.Popen(
            [temp_launcher_path, installer_path, str(os.getpid())],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True
        )

        return {"success": True, "message": "Update process initiated. This app will now close."}
    except Exception as e:
        return {"success": False, "error": f"Failed to download or run installer: {e}"}
