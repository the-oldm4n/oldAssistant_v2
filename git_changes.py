# git_changes.py
import subprocess
import json
import os
from pathlib import Path
from typing import OrderedDict

from bin.utils import get_config_value

def get_changed_files():
    """Получает список измененных файлов в текущем коммите"""
    try:
        # Получаем хеш текущего коммита
        commit_hash = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], 
            text=True
        ).strip()
        
        # Получаем хеш предыдущего коммита
        prev_commit = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD~1'], 
            text=True
        ).strip()
        
        # Получаем измененные файлы между коммитами
        result = subprocess.check_output(
            ['git', 'diff', '--name-only', prev_commit, commit_hash],
            text=True
        )
        
        changed_files = [f.strip() for f in result.split('\n') if f.strip()]
        return changed_files
        
    except subprocess.CalledProcessError:
        # Если нет предыдущего коммита (первый коммит)
        return []

def get_staged_files():
    """Получает файлы, готовые к коммиту"""
    try:
        result = subprocess.check_output(
            ['git', 'diff', '--name-only', '--cached'],
            text=True
        )
        staged_files = [f.strip() for f in result.split('\n') if f.strip()]
        return staged_files
    except subprocess.CalledProcessError:
        return []

def get_modified_files():
    """Получает все измененные файлы (включая неподготовленные)"""
    try:
        result = subprocess.check_output(
            ['git', 'ls-files', '--modified'],
            text=True
        )
        modified_files = [f.strip() for f in result.split('\n') if f.strip()]
        return modified_files
    except subprocess.CalledProcessError:
        return []

def replace_main_with_exe(files):
    """Заменяет main.py на Assistant.exe в списке файлов"""
    processed_files = []
    for file in files:
        if file == 'main.py':
            processed_files.append('Assistant.exe')
        else:
            processed_files.append(file)
    return processed_files

def load_existing_manifest(manifest_path='changes_manifest.json'):
    """Загружает существующий манифест или создает новый"""
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest_data = json.load(f)
            
            # Используем OrderedDict для сохранения порядка
            ordered_manifest = OrderedDict()
            
            # Сортируем версии в обратном порядке (новые версии first)
            versions = sorted(manifest_data.keys(), reverse=True)
            for version in versions:
                ordered_manifest[version] = manifest_data[version]
                
            return ordered_manifest
    else:
        return OrderedDict()

def save_manifest(manifest, manifest_path='changes_manifest.json'):
    """Сохраняет манифест в файл с новыми версиями в начале"""
    
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

def main():
    # Получаем текущую версию из config.ini
    current_version = get_config_value("app", "version")
    if not current_version:
        print("❌ Не удалось получить версию из config.ini")
        return

    print(f"📦 Текущая версия: {current_version}")

    # Получаем измененные файлы
    changed_files = get_modified_files()
    
    if not changed_files:
        print("❌ Нет измененных файлов в staging area")
        print("   Используйте: git add . чтобы добавить файлы")
        return

    print(f"📁 Обнаружено изменений: {len(changed_files)} файлов")

    # Заменяем main.py на Assistant.exe
    processed_files = replace_main_with_exe(changed_files)
    
    if 'main.py' in changed_files:
        print("✅ main.py заменен на Assistant.exe")

    # Загружаем существующий манифест
    manifest = load_existing_manifest()

    # Проверяем, существует ли уже эта версия
    if current_version in manifest:
        print(f"⚠️  Версия {current_version} уже существует в манифесте")
        overwrite = input("Перезаписать? (y/n): ")
        if overwrite.lower() != 'y':
            return

    full_update_input = input("Установить full_update=True? (y/n): ")
    full_update = full_update_input.lower() == 'y'
    
    # Создаем новый OrderedDict с новой версией в начале
    new_manifest = OrderedDict()
    new_manifest[current_version] = {
        "full_update": full_update,
        "changed_files": processed_files
    }
    
    # Добавляем остальные версии (исключая текущую если она была)
    for version, data in manifest.items():
        if version != current_version:
            new_manifest[version] = data

    # Сохраняем обновленный манифест
    save_manifest(new_manifest)
    
    print(f"✅ Манифест обновлен для версии {current_version}")
    print("📋 Файлы для обновления:")
    for file in processed_files:
        print(f"   → {file}")
    
    print(f"\n📊 Всего версий в манифесте: {len(new_manifest)}")
    print("🔝 Новая версия добавлена в начало файла")

if __name__ == "__main__":
    main()