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
    """Automatically updates the APP_VERSION in app.py."""
    print(f"-> Patching app.py with new version: {version}")
    try:
        with open("app.py", "r+", encoding="utf-8") as f:
            content = f.read()
            pattern = r"(APP_VERSION\s*=\s*['\"])(.*?)(['\"])"
            def replace_version(match): return f'{match.group(1)}{version}{match.group(3)}'
            new_content, count = re.subn(pattern, replace_version, content)
            if count == 0:
                print("X ERROR: Could not find a line matching 'APP_VERSION = \"...\"' in app.py.")
                return False
            f.seek(0)
            f.write(new_content)
            f.truncate()
        print("+ app.py patched successfully.")
        return True
    except Exception as e:
        print(f"X ERROR: Failed to patch app.py: {e}")
        return False

def generate_post_install_script(output_path, app_name, main_executable):
    """Generates a VBScript whose ONLY job is to reliably create shortcuts."""
    install_dir_name = app_name.replace(" ", "_")
    vb_script = f'''
Set WshShell = WScript.CreateObject("WScript.Shell")
strLocalAppData = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%")
strDesktopPath = WshShell.SpecialFolders("Desktop")
strStartMenuPath = WshShell.SpecialFolders("Programs")
strAppName = "{app_name}"
strExeName = "{main_executable}"
strInstallDir = strLocalAppData & "\\{install_dir_name}"
strTargetPath = strInstallDir & "\\" & strExeName
On Error Resume Next
Set oShellLink = WshShell.CreateShortcut(strDesktopPath & "\\" & strAppName & ".lnk")
oShellLink.TargetPath = strTargetPath
oShellLink.IconLocation = strTargetPath & ", 0"
oShellLink.WorkingDirectory = strInstallDir
oShellLink.Save
Set oShellLink = WshShell.CreateShortcut(strStartMenuPath & "\\" & strAppName & ".lnk")
oShellLink.TargetPath = strTargetPath
oShellLink.IconLocation = strTargetPath & ", 0"
oShellLink.WorkingDirectory = strInstallDir
oShellLink.Save
Set oShellLink = Nothing
Set WshShell = Nothing
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
Path=%LOCALAPPDATA%\\{install_dir_name}
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
    # --- THIS IS THE CORRECTED COMMAND ---
    # We explicitly tell the launcher's build about its own dependency on psutil.
    launcher_build_cmd = "pyinstaller --onefile --windowed --name updater_launcher --hidden-import psutil updater_launcher.py --clean --distpath=dist_new --workpath=build_new"
    if not run_command(launcher_build_cmd, "Launcher Build"): return False
    staged_launcher_path = os.path.join('dist_new', 'updater_launcher.exe')
    if not os.path.exists(staged_launcher_path): return False, "Failed to build updater_launcher.exe."
    
    print("\n--- 3. Building Main Application ---")
    # --- THE VERSION BUG FIX ---
    # Add --clean here as well for the same reason.
    if not run_command("pyinstaller build_improved.spec --clean --distpath=dist_new --workpath=build_new", "Main App Build"): return False
    
    app_source_dir = next((os.path.join('dist_new', d) for d in os.listdir('dist_new') if os.path.isdir(os.path.join('dist_new', d))), None)
    if not app_source_dir: return False, "Could not find PyInstaller output directory."
    
    shutil.copy(staged_launcher_path, app_source_dir)
    print("+ Updater launcher has been packaged with the main application.")

    app_name = "VCF Processor Fast"
    app_main_exe = "VCF_Processor_Fast.exe"
    installer_output_file = os.path.join("dist_new", "VCF_Processor_Installer.exe")
    
    if not create_winrar_installer(app_name, app_source_dir, app_main_exe, installer_output_file): return False
    
    print("\n--- 5. Skipping GitHub (using Google Drive only) ---")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("X ERROR: You must provide a version number to build.")
        print("   Example: python build_release.py 2.8.5")
        sys.exit(1)
    
    new_version = sys.argv[1]
    if build_release(new_version):
        print("\n\nBuild process completed successfully!")
    else:
        print("\n\nBuild failed.")