# -*- mode: python ; coding: utf-8 -*-
version_file = 'F:/PyCharmProjects/oldAssistant_v2/update_app/version.txt'

block_cipher = None

# Главные файлы проекта (сборка в один файл)
main_script = 'update_app/update.py'
additional_files = [
    ('F:/PyCharmProjects/oldAssistant_v2/update_app/color.json', '.'),
    ('F:/PyCharmProjects/oldAssistant_v2/update_app/logo.svg', '.'),
    ('F:/PyCharmProjects/oldAssistant_v2/update_app/icon.ico', '.'),
    ('F:/PyCharmProjects/oldAssistant_v2/update_app/check_and_download.py', '.'),
    ('F:/PyCharmProjects/oldAssistant_v2/update_app/utils.py', '.'),
    ('F:/PyCharmProjects/oldAssistant_v2/update_app/version.txt', '.'),
]

a = Analysis(
    [main_script],
    pathex=[],
    binaries=[],
    datas=additional_files,
    hiddenimports=[
        'requests',
        'json',
        'os',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False  # Важно для onefile!
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Update',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    uac_admin=True,
    icon='F:/PyCharmProjects/oldAssistant_v2/update_app/icon.ico',
    version=version_file,
)