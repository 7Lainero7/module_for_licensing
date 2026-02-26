# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files
import os
import glob

block_cipher = None

# 1. Собираем данные treepoem
treepoem_datas = collect_data_files('treepoem')

# 2. Настройки Ghostscript (твой старый код)
GS_PATHS = [
    r"C:\Program Files\gs\gs10.06.0",
    r"C:\Program Files\gs\gs10.03.1", 
    r"C:\Program Files\gs\gs10.02.1",
]

binaries = []
datas = []

# Добавляем Ghostscript
for gs_path in GS_PATHS:
    if os.path.exists(gs_path):
        print(f"Found Ghostscript at: {gs_path}")
        bin_dir = os.path.join(gs_path, "bin")
        if os.path.exists(bin_dir):
            for exe in ['gswin64c.exe', 'gswin32c.exe', 'gswin64.exe', 'gswin32.exe']:
                exe_path = os.path.join(bin_dir, exe)
                if os.path.exists(exe_path):
                    binaries.append((exe_path, '.'))
        
        for dll_file in glob.glob(os.path.join(bin_dir, "*.dll")):
            binaries.append((dll_file, '.'))
        
        for data_dir in ["Resource", "lib", "fonts"]:
            data_path = os.path.join(gs_path, data_dir)
            if os.path.exists(data_path):
                for root, dirs, files in os.walk(data_path):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, gs_path)
                        datas.append((full_path, os.path.dirname(rel_path)))
        break

# 3. ВАЖНО: Добавляем .env внутрь EXE
datas.append(('.env', '.'))

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=treepoem_datas + datas,
    hiddenimports=['treepoem', 'license_manager'], # Добавил license_manager
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas, # Важно: все данные запаковываются внутрь
    [],
    name='PrinterCheck',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # True - если хочешь видеть черное окно для отладки
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)