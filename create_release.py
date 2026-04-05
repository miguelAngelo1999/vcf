"""
create_release.py - Build installer and publish update to Google Drive.

Usage:
    python create_release.py 2.9.33
"""
import ssl
import urllib3
import os
import sys
import warnings
import httplib2

# SSL bypass + proxy
os.environ.update({
    'PYTHONHTTPSVERIFY': '0',
    'CURL_CA_BUNDLE': '',
    'REQUESTS_CA_BUNDLE': '',
    'HTTP_PROXY': 'http://127.0.0.1:1090',
    'HTTPS_PROXY': 'http://127.0.0.1:1090',
})
ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings()

import requests
_orig_request = requests.Session.request
def _patched_request(self, method, url, **kwargs):
    kwargs['verify'] = False
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return _orig_request(self, method, url, **kwargs)
requests.Session.request = _patched_request

_orig_init = httplib2.Http.__init__
def _patched_init(self, *args, **kwargs):
    kwargs['disable_ssl_certificate_validation'] = True
    if 'proxy_info' not in kwargs or kwargs['proxy_info'] is None:
        kwargs['proxy_info'] = httplib2.ProxyInfo(
            httplib2.socks.PROXY_TYPE_HTTP, '127.0.0.1', 1090
        )
    _orig_init(self, *args, **kwargs)
httplib2.Http.__init__ = _patched_init

from build_release import build_release

# Google Drive file IDs
VERSION_FILE_ID = "1MdfgUQCU_iVcJb83QOdPe8c3N1dw1ypi"
INSTALLER_FILE_ID = "1_qbGHNQWXUhlobUbAl5t3YdD03NDrmoc"
INSTALLER_PATH = os.path.join("dist_new", "VCF_Processor_Installer.exe")


def gdrive_update_file(file_id, file_path):
    """Update existing file on Google Drive."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    import pickle

    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = None
    token_path = 'gdrive_token.pickle'

    if os.path.exists(token_path):
        with open(token_path, 'rb') as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'wb') as f:
            pickle.dump(creds, f)

    service = build('drive', 'v3', credentials=creds)
    media = MediaFileUpload(file_path, resumable=True)
    service.files().update(fileId=file_id, media_body=media).execute()
    return True


def upload_installer(file_path):
    """Upload installer to Google Drive (replace existing)."""
    print(f"-> Uploading {file_path}...")
    gdrive_update_file(INSTALLER_FILE_ID, file_path)
    print(f"+ Installer uploaded to Google Drive")
    return True


def update_version(version):
    """Update version.txt on Google Drive."""
    tmp = '_version_tmp.txt'
    with open(tmp, 'w') as f:
        f.write(version)
    print(f"-> Updating version to {version}...")
    gdrive_update_file(VERSION_FILE_ID, tmp)
    os.remove(tmp)
    print(f"+ Version updated to {version} on Google Drive")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("X ERROR: Provide a version number.")
        print("  Example: python create_release.py 2.9.33")
        sys.exit(1)

    version = sys.argv[1]
    print(f"\n=== Creating Release v{version} ===\n")

    # Step 1: Build
    if not build_release(version):
        print("\nBuild failed.")
        sys.exit(1)

    # Step 2: Upload installer to Google Drive
    print("\n--- 6. Uploading installer to Google Drive ---")
    if not upload_installer(INSTALLER_PATH):
        print("X ERROR: Installer upload failed.")
        sys.exit(1)

    # Step 3: Update version.txt on Google Drive
    print("\n--- 7. Updating version on Google Drive ---")
    if not update_version(version):
        print("X ERROR: Version update failed.")
        sys.exit(1)

    print(f"\n\nRelease v{version} published successfully!")
