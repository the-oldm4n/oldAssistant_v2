# -*- mode: python ; coding: utf-8 -*-
version_file = 'F:/PyCharmProjects/voxodium/version.txt'


block_cipher = None

main_script = 'main.py'
additional_files = [
    ('F:/PyCharmProjects/voxodium/app.manifest', '.'),
    ('F:/PyCharmProjects/voxodium/version.txt', '.'),
    ('F:/PyCharmProjects/voxodium/icon.ico', '.'),
    ('F:/PyCharmProjects/voxodium/log_config.py', '.'),
    ('F:/PyCharmProjects/voxodium/config.py', '.'),
    ('F:/PyCharmProjects/voxodium/widgets', 'widgets'),
    ('F:/PyCharmProjects/voxodium/bin', 'bin'),
    ('F:/PyCharmProjects/voxodium/config.ini', 'config.ini'),
    ('F:/PyCharmProjects/voxodium/path_builder.py', '.'),
    ('F:/PyCharmProjects/voxodium/updater.exe', '.'),
    ('F:/PyCharmProjects/voxodium/README.md', '.'),
    ('F:/PyCharmProjects/voxodium/LICENSE.md', '.'),
    ('F:/PyCharmProjects/voxodium/THIRD-PARTY-LICENSES.md', '.'),
    ('F:/PyCharmProjects/voxodium/user_data', 'user_data'),
    ('F:/PyCharmProjects/voxodium/data/OHM', 'data/OHM'),
    ('F:/PyCharmProjects/voxodium/data/model_ru', 'data/model_ru'),
    ('F:/PyCharmProjects/voxodium/data/script-icons', 'data/script-icons'),
]

a = Analysis(
    [main_script],
    pathex=[],
    binaries=[
        (r'F:/PyCharmProjects/voxodium/venv/Lib/site-packages/vosk/libvosk.dll', 'vosk'),
        (r'F:/PyCharmProjects/voxodium/venv\Lib/site-packages/vgamepad\win/vigem/client/x64/ViGEmClient.dll', 'vgamepad/win/vigem/client/x64')],
    datas=additional_files,
    hiddenimports=['mygui'],
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
    name='Voxodium',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    uac_admin=True,
    icon='F:/PyCharmProjects/voxodium/icon.ico',
    version=version_file,
)
