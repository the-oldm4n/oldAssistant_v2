# -*- mode: python ; coding: utf-8 -*-
version_file = 'G:/PycharmProjects/oldAssistant_v2/version.txt'

a = Analysis(
    ['main.py'],
    pathex=['G:/PycharmProjects/oldAssistant_v2'],
    binaries=[
        (r'G:\PycharmProjects\oldAssistant_v2\venv\Lib\site-packages\vosk\libvosk.dll', 'vosk'),
        (r'G:\PycharmProjects\oldAssistant_v2\venv\Lib\site-packages\vgamepad\win\vigem\client\x64\ViGEmClient.dll',
        'vgamepad/win/vigem/client/x64')
    ],
    datas=[
        ('G:/PycharmProjects/oldAssistant_v2/app.manifest', '.'),
        ('G:/PycharmProjects/oldAssistant_v2/version.txt', '.'),
        ('G:/PycharmProjects/oldAssistant_v2/icon_assist.ico', '.'),
        ('G:/PycharmProjects/oldAssistant_v2/logging_config.py', '.'),
        ('G:/PycharmProjects/oldAssistant_v2/owl.svg', '.'),
        ('G:/PycharmProjects/oldAssistant_v2/user_settings', 'user_settings'),
        ('G:/PycharmProjects/oldAssistant_v2/bin', 'bin'),
        ('G:/PycharmProjects/oldAssistant_v2/config.ini', '.'),
        ('G:/PycharmProjects/oldAssistant_v2/path_builder.py', '.'),
        ('G:/PycharmProjects/oldAssistant_v2/Update.exe', '.'),
        ('G:/PycharmProjects/oldAssistant_v2/swap-updater.exe', '.'),
        ('G:/PycharmProjects/oldAssistant_v2/README.md', '.'),
        ('G:/PycharmProjects/oldAssistant_v2/LICENSE.md', '.'),
        ('G:/PycharmProjects/oldAssistant_v2/THIRD-PARTY-LICENSES.md', '.'),
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
    manifest="G:/PycharmProjects/oldAssistant_v2/app.manifest",
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
