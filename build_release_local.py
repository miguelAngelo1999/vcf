import os
import subprocess
import shutil
import sys
import re

# ==============================================================================
# --- Main Configuration ---
# ==============================================================================
INSTALLER_PASSWORD = "123" 
# ==============================================================================

def run_command(cmd, step_name=""):
    print(f"-> Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='latin-1')
    if result.returncode != 0:
        print(f"X ERROR during '{step_name}':")
        print(f"  STDERR: {result.stderr.strip()}")
        print(f"  STDOUT: {result.stdout.strip()}")
        return False
    return True

def find_winrar_executable():
    winrar_exe = shutil.which("WinRAR.exe")
    if winrar_exe: return winrar_exe
    search_dirs = [os.path.expandvars(r'%ProgramFiles%\WinRAR'), os.path.expandvars(r'%ProgramFiles(x86)%\WinRAR')]
    for directory in search_dirs:
        path = os.path.join(directory, "WinRAR.exe")
        if os.path.exists(path): return path
    print("X Error: WinRAR.exe not found.")
    return None

def update_app_version(version):
    """Updates the version in app.py"""
    app_py_path = "app.py"
    if not os.path.exists(app_py_path):
        print(f"X Error: {app_py_path} not found!")
        return False
    
    try:
        with open(app_py_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update APP_VERSION
        content = re.sub(r'APP_VERSION = ["\'].*?["\']', f'APP_VERSION = "{version}"', content)
        
        with open(app_py_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"+ app.py patched with new version: {version}")
        return True
    except Exception as e:
        print(f"X Error patching app.py: {e}")
        return False

def generate_post_install_script(output_path, app_name, main_executable):
    """Generates the VBScript for post-install actions."""
    vb_script = f'''
Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

desktopPath = objShell.SpecialFolders("Desktop")
shortcutPath = desktopPath & "\\{app_name}.lnk"
targetPath = objShell.CurrentDirectory & "\\{main_executable}"

Set shortcut = objShell.CreateShortcut(shortcutPath)
shortcut.TargetPath = targetPath
shortcut.Save

objShell.Run chr(34) & targetPath & chr(34), 1, False
'''
    with open(output_path, "w", encoding="utf-8") as f: f.write(vb_script)
    return True

def create_winrar_installer(app_name, source_folder, main_executable, output_installer_path):
    """Creates a WinRAR SFX that uses its native commands correctly."""
    print("\n--- 4. Building WinRAR self-extracting installer ---")
    winrar_exe = find_winrar_executable()
    if not winrar_exe: return False

    post_install_script_name = "post_install.vbs"
    post_install_script_path = os.path.join(source_folder, post_install_script_name)
    if not generate_post_install_script(post_install_script_path, app_name, main_executable): return False

    install_dir_name = app_name.replace(" ", "_")
    full_install_path = os.path.join(os.path.expandvars(r'%LOCALAPPDATA%'), install_dir_name)
    sfx_config_temp_name = "sfx_config_winrar.txt"

    # --- THE FIX IS HERE: Use %LOCALAPPDATA% environment variable ---
    sfx_config = f""";
Title={app_name} Installer
Path=%LOCALAPPDATA%\{install_dir_name}
SavePath
Silent=1
Overwrite=1
Setup=wscript.exe "{post_install_script_name}"
Setup={main_executable}
"""
    try:
        with open(sfx_config_temp_name, "w", encoding="utf-8") as f: f.write(sfx_config)
        source_path_contents = os.path.join(source_folder, '*')
        cmd = [
            f'"{winrar_exe}"', "a", "-ep1", "-sfx", "-r", f"-hp{INSTALLER_PASSWORD}",
            f'-z"{sfx_config_temp_name}"', f'"{output_installer_path}"', f'"{source_path_contents}"'
        ]
        if not run_command(" ".join(cmd), "WinRAR SFX Creation"): return False
        print("+ Successfully created installer with overwrite, shortcuts, and resurrection.")
    finally:
        if os.path.exists(sfx_config_temp_name): os.remove(sfx_config_temp_name)
        if os.path.exists(post_install_script_path): os.remove(post_install_script_path)
    return True

def build_release(version):
    """The main, all-in-one build process."""
    print(f"Building VCF Processor Release v{version}")
    print("=" * 40)
    
    for dir_name in ["dist_new", "build_new"]:
        if os.path.exists(dir_name): 
            try:
                shutil.rmtree(dir_name)
            except PermissionError:
                print(f"Warning: Could not remove {dir_name} due to permission error. Continuing...")
    
    print("\n--- 1. Patching application version ---")
    if not update_app_version(version): return False
    
    print("\n--- 2. Building Updater Launcher Helper ---")
    # --- THE VERSION BUG FIX ---
    # Add --clean to force PyInstaller to ignore caches and use our patched app.py
     # Add --clean to force PyInstaller to ignore caches and use our patched app.py
    launcher_build_cmd = "pyinstaller --onefile --windowed --name updater_launcher --hidden-import psutil updater_launcher.py --clean --distpath=dist_new --workpath=build_new"
    if not run_command(launcher_build_cmd, "Launcher Build"): return False
    staged_launcher_path = os.path.join('dist_new', 'updater_launcher.exe')
    if not os.path.exists(staged_launcher_path): return False, "Failed to build updater_launcher.exe."
    
    print("\n--- 3. Building Main Application ---")
    # --- THE VERSION BUG FIX ---
    # Add --clean here as well for same reason.
    if not run_command("pyinstaller build_improved.spec --clean --distpath=dist_new --workpath=build_new", "Main App Build"): return False
    
    app_source_dir = next((os.path.join('dist_new', d) for d in os.listdir('dist_new') if os.path.isdir(os.path.join('dist_new', d))), None)
    if not app_source_dir: return False, "Could not find PyInstaller output directory."
    
    shutil.copy(staged_launcher_path, app_source_dir)
    print("+ Updater launcher has been packaged with main application.")

    app_name = "VCF Processor Fast"
    app_main_exe = "VCF_Processor_Fast.exe"
    installer_output_file = os.path.join("dist_new", "VCF_Processor_Installer.exe")
    
    if not create_winrar_installer(app_name, app_source_dir, app_main_exe, installer_output_file): return False
    
    print("\n--- 5. Uploading to Google Drive ---")
    print("🌐 Uploading installer to Google Drive with proxy...")
    
    # Import upload function
    import nuclear_ssl_bypass
    import pickle
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    
    # Set proxy
    os.environ['HTTP_PROXY'] = 'http://127.0.0.1:1090'
    os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:1090'
    
    SCOPES = ['https://www.googleapis.com/auth/drive']
    FOLDER_ID = '1z5_OOJAvmhSfq3CUsgDFKKYGWEg0iLDV'  # VCF Processor Updates folder
    
    def get_credentials():
        creds = None
        token_path = 'token_drive.pickle'
        
        if os.path.exists(token_path):
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    print("ERROR: credentials.json not found!")
                    return None
                
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        return creds
    
    try:
        creds = get_credentials()
        if creds:
            service = build('drive', 'v3', credentials=creds)
            
            # Check if file exists and update it
            results = service.files().list(
                q=f"name='VCF_Processor_Installer.exe' and '{FOLDER_ID}' in parents and trashed=false",
                fields="files(id, name)"
            ).execute()
            
            existing_files = results.get('files', [])
            
            if existing_files:
                # Update existing file
                file_id = existing_files[0]['id']
                print(f"🔄 Updating existing installer (ID: {file_id})")
                
                file_metadata = {'description': f'VCF Processor Installer v{version}'}
                media = MediaFileUpload(installer_output_file, resumable=True)
                file = service.files().update(
                    fileId=file_id,
                    body=file_metadata,
                    media_body=media,
                    fields='id, webViewLink'
                ).execute()
            else:
                # Create new file
                print("📤 Creating new installer upload")
                file_metadata = {
                    'name': 'VCF_Processor_Installer.exe',
                    'parents': [FOLDER_ID],
                    'description': f'VCF Processor Installer v{version}'
                }
                media = MediaFileUpload(installer_output_file, resumable=True)
                file = service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, webViewLink'
                ).execute()
            
            print(f"✅ Upload complete!")
            print(f"🔗 Link: {file.get('webViewLink')}")
            print(f"📁 Folder: https://drive.google.com/drive/folders/{FOLDER_ID}")
            
    except Exception as e:
        print(f"❌ Upload failed: {e}")
    
    print(f"\n✅ VCF Processor v{version} built and uploaded successfully!")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python build_release_local.py VERSION")
        print("\nExample: python build_release_local.py 2.7.1")
        sys.exit(1)
    
    version = sys.argv[1]
    if not build_release(version):
        print("\n❌ Build failed!")
        sys.exit(1)
    else:
        print(f"\n✅ VCF Processor v{version} built successfully!")
