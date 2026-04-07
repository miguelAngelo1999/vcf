# VCF Processor Fast - Technical Summary

## Overview

VCF Processor Fast is a Windows desktop application that processes WhatsApp contact export files (.vcf) and text-based contact lists, deduplicates them against a history log, and exports the results to Excel (.xlsx). It is built with Python, Flask, and pywebview (Edge WebView2).

---

## Architecture

```
app.py (Flask + pywebview)
├── vcf_extractor.py     - Core processing logic
├── updater.py           - Auto-update via Google Drive
├── updater_launcher.py  - Independent update installer process
├── templates/
│   └── index_pt-br.html - Single-page UI (vanilla JS state machine)
└── static/
    └── styles.css
```

### Stack
- **Backend**: Python 3.13, Flask, pywebview (Edge WebView2)
- **Frontend**: Vanilla JS (no framework), single HTML file
- **Build**: PyInstaller (onedir), WinRAR SFX installer
- **Updates**: Google Drive (version.txt + installer file)

---

## Core Processing Flow

### 1. Input Sources
The app accepts contacts from two sources:

**VCF Files** - Standard vCard format exported from WhatsApp. Supports single or batch (multiple files concatenated into one temp file before processing).

**Text Paste** - Two text formats supported:
- `[OK] Nome +55... foi adicionado com sucesso [OK]`
- `Name: Nome... Number (1): +55...`

### 2. Contact Extraction (`vcf_extractor.py`)
- Reads VCF with multiple encoding fallbacks (utf-8, utf-8-sig, iso-8859-1, cp1252, latin1)
- Extracts `FN:`, `N:`, `NICKNAME:` for name; `TEL:`, `waid=` for phone number
- Cleans phone numbers (digits only)
- Cleans names: converts to ASCII (unidecode), removes special chars, strips configured title words (Dr, Prof, etc.), keeps first word only, title-cased

### 3. Deduplication
Contacts are compared against `NAO_APAGAR.log` - a plain text file with one phone number per line representing all previously processed contacts.

- **Unique**: number NOT in log → goes to output
- **Duplicate**: number IS in log → shown to user for selection

If duplicates exist within the same source file (same number appears multiple times), the contact with the longest name is kept.

### 4. User Decision (Duplicate Selector)
When duplicates are found, the UI shows a scrollable checklist. The user can:
- Select individual duplicates to reprocess (removes from log, adds to output)
- "Selecionar todos" to select all (uses a `Set` tracked in JS state, not DOM checkboxes)
- Click "Pular" to skip all duplicates and only process unique contacts

### 5. Output
Exports to Excel (.xlsx) in two formats:

**Padrão (Standard)**:
| Number | Name |
|--------|------|
| 5584999... | João |

**Novo Programa (4-column)**:
| Primeiro nome | Sobrenome | Telefone | Etiquetas |
|---------------|-----------|----------|-----------|
| João | [Quem Enviou] | 5584999... | [Quem Enviou] |

Output file is saved in the same directory as the input VCF file (or Documents for text/batch).

---

## History Log (`NAO_APAGAR.log`)

The log file tracks all processed phone numbers to prevent reprocessing. Location priority:
1. App install directory (`%LOCALAPPDATA%\VCF_Processor_Fast\`)
2. `~/Documents/VCF_Processor_logs/`
3. `%PROGRAMDATA%\VCF_Processor\`
4. `%LOCALAPPDATA%\VCF_Processor\`
5. Temp directory (fallback)

The log is a plain text file, one number per line (digits only, no +).

---

## Configuration (`config.ini`)

Stored in `%LOCALAPPDATA%\VCF_PROCESSOR\config.ini`.

```ini
[Settings]
light_mode = follow        # 'follow' (mouse tracking) or 'static'
excel_format = standard    # 'standard' or 'novo_programa'
sender_indicator = Contato Recebido

[Titles]
titles_to_remove = [
    "Dr", "Prof", "Sr", ...
]
```

---

## Auto-Update System

### Flow
1. User clicks "Verificar Atualizações" in settings panel
2. `updater.py` fetches `version.txt` from Google Drive (file ID: `1MdfgUQCU_iVcJb83QOdPe8c3N1dw1ypi`)
3. Compares with hardcoded `APP_VERSION` in `app.py`
4. If newer: shows "Baixar e Instalar" button
5. User clicks → `updater.py` downloads installer from Google Drive (file ID: `1_qbGHNQWXUhlobUbAl5t3YdD03NDrmoc`) to temp dir
6. Copies `updater_launcher.exe` to temp dir with unique name
7. Launches launcher as detached process with `[installer_path, parent_PID]`
8. App calls `os._exit(0)` to shut down
9. Launcher waits for parent PID to disappear → waits 10 seconds → runs installer
10. WinRAR SFX installer extracts to `%LOCALAPPDATA%\VCF_Processor_Fast\`, runs VBScript to create shortcuts, then launches the new exe

### Publishing a New Release
```cmd
python create_release.py 2.9.XX
```
This builds the app, creates the WinRAR installer, uploads it to Google Drive, and updates `version.txt`.

---

## Build System

### `build_release.py`
1. Patches `APP_VERSION` in `app.py`
2. Builds `updater_launcher.exe` (PyInstaller onefile)
3. Builds main app (PyInstaller onedir via `build_improved.spec`)
4. Copies launcher into app dist folder
5. Creates WinRAR SFX installer

### `create_release.py`
Calls `build_release.py` then:
6. Uploads installer to Google Drive (replaces existing file, same ID)
7. Updates `version.txt` on Google Drive with new version number

### Key Files
| File | Purpose |
|------|---------|
| `build_improved.spec` | PyInstaller spec for main app |
| `build_release.py` | Build pipeline |
| `create_release.py` | Full release pipeline (build + publish) |
| `updater.py` | Update checker + downloader |
| `updater_launcher.py` | Independent installer runner |
| `pyi_rth_no_pyarrow.py` | PyInstaller runtime hook (pyarrow mock) |
| `credentials.json` | Google OAuth credentials for Drive API |
| `gdrive_token.pickle` | Cached Google OAuth token |

---

## UI Architecture (Frontend)

Single-page app with a vanilla JS state machine pattern:

```js
let state = {
    isLoading, isProcessing, showAdvanced,
    vcfPath, duplicates, filteredTitles,
    logMessages, selectedDuplicates, error
}

function setState(newState) { ... render(state) }
function render(state) { /* updates DOM based on state */ }
```

Key design decisions:
- `selectedDuplicates` is a `Set` preserved across `setState` calls explicitly (JS spread loses Set references)
- Duplicates list only re-renders when count changes (prevents checkbox state loss on log messages)
- Settings panel slides in from the right via CSS class toggle
- Window is frameless; drag/resize handled via JS + pywebview API calls
