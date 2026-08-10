# -*- mode: python ; coding: utf-8 -*-
version_file = 'F:/PyCharmProjects/voxodium/update_app/version.txt'

block_cipher = None

main_script = 'update_app/update.py'
additional_files = [
    ('F:/PyCharmProjects/voxodium/update_app/bin', 'bin'),
    ('F:/PyCharmProjects/voxodium/update_app/colors.json', '.'),
    ('F:/PyCharmProjects/voxodium/update_app/config.py', '.'),
    ('F:/PyCharmProjects/voxodium/update_app/log_config.py', '.'),
    ('F:/PyCharmProjects/voxodium/update_app/icon.ico', '.'),
    ('F:/PyCharmProjects/voxodium/update_app/utils.py', '.'),
    ('F:/PyCharmProjects/voxodium/update_app/version.txt', '.'),
]

a = Analysis(
    [main_script],
    pathex=[],
    binaries=[],
    datas=additional_files,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='updater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    uac_admin=True,
    icon='F:/PyCharmProjects/voxodium/update_app/icon.ico',
    version=version_file,
)