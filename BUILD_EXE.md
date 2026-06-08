# Building an Executable with PyInstaller

This guide explains how to package the Eye-State-Detector application as a standalone Windows executable (.exe) for easy deployment to other machines.

## Prerequisites

### 1. Install PyInstaller

```powershell
pip install pyinstaller
```

### 2. Install VLC (Required Runtime Dependency)

The application uses python-vlc, which requires the VLC runtime to be present on the target machine.

**Option A: Require VLC Installation (Recommended for simplicity)**
- Have users install VLC from https://www.videolan.org/vlc/ on target machines before running the executable.
- This is the simplest approach and reduces the .exe size.

**Option B: Bundle VLC DLLs (Advanced)**
- Install VLC on your build machine to extract DLLs.
- Manually copy required VLC DLLs to the packaged application directory.
- This approach makes the executable fully standalone but increases size significantly.

## Building the Executable

### Basic Build (Recommended)

From the Eye-State-Detector directory, run:

```powershell
$pyiArgs = '--noconfirm', '--windowed', '--onedir',
           '--name', 'Blinker',
           '--distpath', '..\Blinker-dist',
           '--workpath', '..\Blinker-build',
           '--specpath', '..\Blinker-build',
           '--collect-all', 'mediapipe',
           "--add-data", "$PWD\face_landmarker.task;.",
           "--add-data", "$PWD\trivia_general_knowledge.json;.",
           'launcher.py'
.\eye-env\Scripts\pyinstaller.exe @pyiArgs
```

**Options Explained:**
- `--noconfirm`: Skip confirmation prompts
- `--windowed`: Hide console window (GUI only)
- `--onedir`: Bundle all files in a single directory (easier distribution)
- `--name`: Custom name for the executable
- `--distpath`: Where to place the final packaged app (outside source tree)
- `--workpath`: Where intermediate build files go (outside source tree)
- `--specpath`: Where to write the `.spec` config file (outside source tree)
- `launcher.py`: Entry point script

> **Why redirect output paths?** Without these flags, PyInstaller creates `build/` and `dist/`
> inside your source directory, which would clutter your git repo. Placing them one level up
> keeps the development directory clean.

### One-File Build (Advanced)

To create a single .exe file instead of a directory:

```powershell
$pyiArgs = '--noconfirm', '--windowed', '--onefile',
           '--name', 'Blinker',
           '--distpath', '..\Blinker-dist',
           '--workpath', '..\Blinker-build',
           '--specpath', '..\Blinker-build',           '--collect-all', 'mediapipe',           "--add-data", "$PWD\face_landmarker.task;.",
           "--add-data", "$PWD\trivia_general_knowledge.json;.",
           'launcher.py'
pyinstaller @pyiArgs
```

**Note:** One-file builds are slower to start and harder to debug. Recommended only if single-file distribution is critical.

## Output Structure (--onedir mode)

All output is placed **outside** the source directory:

```
C:\git\
  Eye-State-Detector\        ← source code (unchanged, nothing added)
  Blinker-dist\
    Blinker\
      Blinker.exe            (Main executable — distribute this folder)
      base_library.zip
      python*.dll
      vcruntime140.dll
      _tkinter.pyd
      (... other runtime libraries ...)
  Blinker-build\             (Intermediate files — safe to delete after build)
    launcher.spec            (PyInstaller config file; can be reused)
    launcher\
      (... intermediate build files ...)
```

## Distribution to Another Machine

### For --onedir Build:

1. **Copy the entire `Blinker-dist\Blinker\` folder** to the target machine (e.g., `C:\Program Files\Blinker\`).
2. **Install VLC on the target machine** (if not using bundled DLLs):
   - Download from https://www.videolan.org/vlc/
   - Install to default location (PyInstaller will find it)
3. **Run the executable**:
   - Double-click `Blinker\Blinker.exe`
   - Or add a shortcut to Desktop/Start Menu

### For --onefile Build:

1. **Copy the single `Blinker-dist\Blinker.exe`** to target machine.
2. **Install VLC** (same as above).
3. **Run the .exe directly**.

## Troubleshooting

### "ModuleNotFoundError: No module named 'vlc'"

**Cause:** python-vlc is installed but VLC runtime is missing.

**Solution:**
- Install VLC from https://www.videolan.org/vlc/ on the target machine.
- Or rebuild with `--collect-all vlc` if available in your python-vlc version.

### Application won't start / Console appears then closes

- Check `Blinker-dist\Blinker\launcher.log` for error messages (if created).
- Try running from Command Prompt instead of double-clicking to see error output.

### Missing DLL errors (e.g., `api-ms-win-crt-*.dll`)

**Cause:** Visual C++ Runtime is missing on target machine.

**Solution:**
- Install **Visual C++ Redistributable** (vcredist) from Microsoft.
- Choose the version matching your Python environment (usually x64 for modern systems).

## Advanced: Custom Data & Assets

If your app references external files (images, config files, etc.), add them:

```powershell
pyinstaller --noconfirm --windowed --onedir `
  --add-data "path/to/asset:asset" `
  --add-data "trivia_general_knowledge.json:." `
  launcher.py
```

This copies `trivia_general_knowledge.json` to the root of the bundled directory.

## Rebuilding After Code Changes

### Option 1: Clean Rebuild (Recommended)

```powershell
# Remove old build artifacts (outside the repo)
Remove-Item -Recurse -Force "..\Blinker-dist", "..\Blinker-build"

# Rebuild
$pyiArgs = '--noconfirm', '--windowed', '--onedir',
           '--name', 'Blinker',
           '--distpath', '..\Blinker-dist',
           '--workpath', '..\Blinker-build',
           '--specpath', '..\Blinker-build',
           '--collect-all', 'mediapipe',
           "--add-data", "$PWD\face_landmarker.task;.",
           "--add-data", "$PWD\trivia_general_knowledge.json;.",
           'launcher.py'
.\eye-env\Scripts\pyinstaller.exe @pyiArgs
```

### Option 2: Reuse Spec File

```powershell
# Modify ..\Blinker-build\launcher.spec if needed, then rebuild
pyinstaller --noconfirm "..\Blinker-build\launcher.spec"
```

## Testing Checklist

Before distributing, test the packaged app:

- [ ] Executable starts without console window
- [ ] Main launcher window opens and displays correctly
- [ ] Can set participant name and load config
- [ ] Can open "Setup" dialog and select task files
- [ ] Can preview eye tracker
- [ ] Can run a reading task (story downloads and displays)
- [ ] Can run video task (VLC plays video)
- [ ] Can run interactive questionnaire task
- [ ] Responses are saved to CSV files in the designated directory
- [ ] App handles task completion and returns to main window

## File Size Reference

- **--onedir build (with VLC dependencies):** ~150–200 MB
- **--onedir build (without bundled VLC):** ~80–100 MB
- **--onefile build:** Similar sizes but in a single .exe

## Further Reading

- [PyInstaller Documentation](https://pyinstaller.org/)
- [VLC Python Bindings](https://www.olivieraubert.net/vlc/python-ctypes/)
