# -*- mode: python ; coding: utf-8 -*-
# GhostAI PyInstaller Build Spec — Optimised (strips torch/sklearn/cv2)

block_cipher = None

from PyInstaller.utils.hooks import collect_data_files

datas = []
datas += collect_data_files('speech_recognition')
datas += collect_data_files('soundcard')

hidden_imports = [
    'sounddevice',
    'soundcard',
    'soundcard.mediafoundation',
    'speech_recognition',
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'numpy',
    'requests',
    'keyboard',
    'ctypes',
    'ctypes.wintypes',
    'wave',
    'io',
    'queue',
    'threading',
    'json',
    'google.generativeai',
    'google.auth',
    'google.api_core',
    'grpc',
    'grpc._cython.cygrpc',
]

# Exclude every large package that GhostAI does NOT need
big_excludes = [
    'torch', 'torchvision', 'torchaudio',
    'sklearn', 'scikit_learn', 'scipy',
    'cv2', 'opencv',
    'pandas', 'matplotlib',
    'PIL', 'Pillow',
    'IPython', 'jupyter', 'notebook',
    'numba', 'llvmlite',
    'sympy',
    'tensorflow', 'keras',
    'transformers', 'tokenizers', 'datasets',
    'accelerate', 'diffusers',
    'pyarrow', 'fsspec',
    'aiohttp', 'aiofiles',
    'sqlalchemy',
    'boto3', 'botocore', 's3transfer',
    'google.cloud',
    'tkinter', '_tkinter',
    'wx',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=big_excludes,
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
    a.datas,
    [],
    name='GhostAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # No black terminal window on launch
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
    version_file=None,
    uac_admin=False,
    onefile=True,           # Single .exe — no folder needed
)
