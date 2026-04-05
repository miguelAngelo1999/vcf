# GitHub Commit Scripts for VCF Processor

## Quick Start

### Windows
```cmd
commit.bat
```

### macOS/Linux
```bash
./commit.sh
```

## What This Does

1. **Stages all relevant files** automatically:
   - Python files (.py)
   - Web files (.html, .css, .js)
   - Configuration files
   - Documentation
   - Build files

2. **Excludes irrelevant files**:
   - Build directories
   - Cache files
   - System files

3. **Interactive menu** with options:
   - Quick commit with auto message
   - Custom commit message
   - Show changes before committing
   - Push to GitHub

## Simple Usage

Just run the appropriate script for your system and follow the prompts!

## Manual Usage

```bash
# Quick commit with auto-generated message
python commit_to_github.py --quick

# Custom message
python commit_to_github.py "Add new features"

# Interactive mode
python commit_to_github.py
```

## Files Created

- `commit_to_github.py` - Main Python script
- `commit.bat` - Windows batch file
- `commit.sh` - macOS/Linux shell script
