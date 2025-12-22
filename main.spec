# -*- mode: python ; coding: utf-8 -*-
version_file = 'F:/PyCharmProjects/oldAssistant_v2/version.txt'

a = Analysis(
    ['main.py'],
    pathex=['F:/PyCharmProjects/oldAssistant_v2'],
    binaries=[
        (r'F:\PyCharmProjects\oldAssistant_v2\venv\Lib\site-packages\vosk\libvosk.dll', 'vosk'),
        (r'F:\PyCharmProjects\oldAssistant_v2\venv\Lib\site-packages\vgamepad\win\vigem\client\x64\ViGEmClient.dll',
        'vgamepad/win/vigem/client/x64')
    ],
    datas=[
        ('F:/PyCharmProjects/oldAssistant_v2/app.manifest', '.'),
        ('F:/PyCharmProjects/oldAssistant_v2/version.txt', '.'),
        ('F:/PyCharmProjects/oldAssistant_v2/icon_assist.ico', '.'),
        ('F:/PyCharmProjects/oldAssistant_v2/logging_config.py', '.'),
        ('F:/PyCharmProjects/oldAssistant_v2/owl.svg', '.'),
        ('F:/PyCharmProjects/oldAssistant_v2/user_settings', 'user_settings'),
        ('F:/PyCharmProjects/oldAssistant_v2/bin', 'bin'),
        ('F:/PyCharmProjects/oldAssistant_v2/config.ini', '.'),
        ('F:/PyCharmProjects/oldAssistant_v2/path_builder.py', '.'),
        ('F:/PyCharmProjects/oldAssistant_v2/Update.exe', '.'),
        ('F:/PyCharmProjects/oldAssistant_v2/swap-updater.exe', '.'),
        ('F:/PyCharmProjects/oldAssistant_v2/README.md', '.'),
        ('F:/PyCharmProjects/oldAssistant_v2/LICENSE.md', '.'),
        ('F:/PyCharmProjects/oldAssistant_v2/THIRD-PARTY-LICENSES.md', '.'),
    ],
    hiddenimports=['vosk', 'pyaudio'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Assistant',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon_assist.ico'],
    manifest="F:/PyCharmProjects/oldAssistant_v2/app.manifest",
    uac_admin=True,
    version=version_file,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Assistant',
)
