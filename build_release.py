#!/usr/bin/env python3
import os
import subprocess
import shutil
import zipfile
import glob

# ==============================================================================
# --- Main Configuration ---
# ==============================================================================
# The password for the installer's contents.
# This helps prevent antivirus false positives by encrypting the files.
INSTALLER_PASSWORD = "your-strong-password-here" 
# ==============================================================================

def run_command(cmd):
    """Runs a command and prints its status."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='latin-1')
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        print(f"Output: {result.stdout}")
        return False
    return True

def find_winrar_executable():
    """Finds the path to WinRAR.exe."""
    winrar_exe = shutil.which("WinRAR.exe")
    if winrar_exe:
        print(f"✓ WinRAR executable found in PATH: {winrar_exe}")
        return winrar_exe
    search_dirs = [os.path.expandvars(r'%ProgramFiles%\WinRAR'), os.path.expandvars(r'%ProgramFiles(x86)%\WinRAR')]
    for directory in search_dirs:
        path = os.path.join(directory, "WinRAR.exe")
        if os.path.exists(path):
            print(f"✓ WinRAR executable found at: {path}")
            return path
    print("✗ Error: WinRAR.exe not found. Please install WinRAR and add it to your PATH.")
    return None

def create_winrar_installer(app_name, source_folder, main_executable, output_installer_path):
    """Creates a password-protected WinRAR SFX installer."""
    print("\n2. Building WinRAR self-extracting installer...")
    winrar_exe = find_winrar_executable()
    if not winrar_exe: return False

    if not os.path.isdir(source_folder):
        print(f"✗ Fatal Error: The application source folder was not found at '{source_folder}'")
        return False

    install_base_dir = os.path.expandvars(r'%LOCALAPPDATA%')
    install_dir = os.path.join(install_base_dir, app_name.replace(" ", "_"))
    sfx_config_temp_name = "sfx_config_winrar.txt"

    sfx_config = f"""; The comment below contains SFX script commands
Path={install_dir}
SavePath
Title={app_name} Installer
Text
{{
This will install {app_name}.
The files will be extracted to the following folder:

{install_dir}
}}
Setup={main_executable}
Overwrite=1
"""
    try:
        with open(sfx_config_temp_name, "w", encoding="utf-8") as f:
            f.write(sfx_config)
        
        original_dir = os.getcwd()
        os.chdir(source_folder)

        cmd = [
            f'"{winrar_exe}"', "a", "-ep1", "-sfx",
            f"-p{INSTALLER_PASSWORD}",
            f'-z"{os.path.join(original_dir, sfx_config_temp_name)}"',
            f'"{os.path.join(original_dir, output_installer_path)}"',
            "*.*"
        ]

        if not run_command(" ".join(cmd)):
            os.chdir(original_dir)
            return False
        
        os.chdir(original_dir)
        print(f"✓ Successfully created installer: {output_installer_path}")
        
    except Exception as e:
        print(f"An unexpected error occurred during installer creation: {e}")
        return False
    finally:
        if os.path.exists(sfx_config_temp_name):
            os.remove(sfx_config_temp_name)
    
    return True

def build_release():
    print("Building VCF Processor Release")
    print("=" * 40)
    
    if os.path.exists("dist"): shutil.rmtree("dist")
    if os.path.exists("build"): shutil.rmtree("build")
    
    # 1. Build main app
    print("\n1. Building main application with PyInstaller...")
    if not run_command("pyinstaller build_improved.spec"):
        return False
    print("✓ PyInstaller build complete.")

    app_source_dir = None
    try:
        subdirs = [d for d in os.listdir('dist') if os.path.isdir(os.path.join('dist', d))]
        if not subdirs:
            print("✗ Fatal Error: No application folder was created by PyInstaller in 'dist'.")
            return False
        app_source_dir = os.path.join('dist', subdirs[0])
        print(f"✓ Located application folder: '{app_source_dir}'")
    except FileNotFoundError:
        print("✗ Fatal Error: 'dist' directory not found after PyInstaller build.")
        return False

    # 2. Build the WinRAR installer
    app_name = "VCF Processor Fast"
    app_main_exe = "VCF_Processor_Fast.exe"
    installer_output_file = "dist/VCF_Processor_Installer.exe"
    
    if not create_winrar_installer(app_name, app_source_dir, app_main_exe, installer_output_file):
        print("✗ Failed to create WinRAR installer.")
        return False
    
    # 3. Create release zip
    print("\n3. Creating final release package...")
    version = "unknown"
    try:
        with open("app.py", "r") as f:
            for line in f:
                if 'APP_VERSION = ' in line:
                    version = line.split('"')[1]
                    break
    except Exception: pass
    
    zip_name = f"VCF_Processor_Release_v{version}.zip"
    
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # ======================================================================
        # --- THIS IS THE CORRECTED SECTION ---
        # ======================================================================
        for root, dirs, files in os.walk(app_source_dir):
            # The missing inner loop is now added:
            for file in files:
                file_path = os.path.join(root, file)
                arc_name = os.path.relpath(file_path, "dist")
                zipf.write(file_path, arc_name)
        # ======================================================================
        
        # This part was already correct
        zipf.write(installer_output_file, os.path.basename(installer_output_file))
    
    print(f"\n✓ Release package created: {zip_name}")
    print(f"  Size: {os.path.getsize(zip_name) / 1024 / 1024:.1f} MB")
    
# 4. Publish to GitHub
    print("\n4. Publishing to GitHub...")
    release_notes = f"VCF Processor v{version} - Complete installer package with auto-install, shortcuts, and file associations."
    
    if not run_command(f'gh release create v{version} --title "VCF Processor v{version}" --notes "{release_notes}"'):
        print("Warning: Failed to create GitHub release")
    else:
        if not run_command(f'gh release upload v{version} "{zip_name}"'):
            print("Warning: Failed to upload release file")
        else:
            print(f"\n✓ Published to GitHub: https://github.com/conim1989/vcf/releases/tag/v{version}")
    
    print(f"\nUsers can:")
    print(f"1. Download {zip_name} from GitHub")
    print(f"2. Extract and run VCF_Processor_Installer.exe for auto-install")
    print(f"3. Or run '{app_name}/{app_main_exe}' directly for a portable experience")
    
    return True

if __name__ == "__main__":
    if build_release():
        print("\nBuild process completed successfully!")
        input("\nPress Enter to exit...")
    else:
        print("\nBuild failed.")
        input("\nPress Enter to exit...")