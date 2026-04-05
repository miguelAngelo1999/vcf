# TODO: Organize Project Files and Update Commit Script

## Tasks
- [ ] Update commit_simple.py to include maintainer files (add installer scripts, updater_launcher.py, README.md, build_installer.spec, commit_simple.bat, commit.sh)
- [ ] Remove other commit scripts from staging (commit_to_github.py, commit.bat) and move them to mess
- [ ] Create "mess" folder
- [ ] Move obsolete files to "mess":
  - Executables: VCF_Processor_Fast_dummy.exe, VCF_Processor_Fast_Installer.exe, VCF_Processor_Fast_WinRAR_Installer.exe, VCF_Processor_Installer.exe
  - Batch/PowerShell: build_7z.bat, build_7z.ps1, build_winrar.bat, build_winrar.ps1, commit.bat
  - Logs: vcf_debug.log, error.txt
  - Test dirs: test_extract/, test_extraction/
  - Release dir: VCF_Processor_Release_v2.5.0/
  - Other: Extrator de VCF.lnk, 7z.sfx, 7zS2.sfx, 7zS2con.sfx, 7zSD.sfx, ../../../Untitled-1, configurarPip.txt, contatos-2.txt, README_WINRAR_INSTALLER.md, README_7Z_INSTALLER.md, build_fixed.spec, commit_to_github.py
- [ ] Test updated commit_simple.py
- [ ] Verify moves to "mess"
- [ ] Update .gitignore for "mess" if needed
