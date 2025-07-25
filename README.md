
# Голосовой помощник Assistant

Голосовой помощник для систем на базе Windows 10 x64.
Голосовое управление ярлыками и папками, например открытие или закрытие.
Вы можете указать собственные ярлыки/папки и настроить команду для работы на определенным ярлыком.


Готовые сборки можно найти [на сайте](owl-app.ru/install)

## Сборка проекта

### 1. Клонирование репозитория
```bash
git clone https://github.com/the-oldm4n/oldAssistant_v2
cd oldAssistant_v2
```
### 2. Установка зависимостей
```bash
pip install -r requirements.txt
```
### 3. Запуск
```bash
python main.py
```

## 📜 Лицензия

Этот проект распространяется под **GNU GPL v3**.  
Полный текст лицензии: [LICENSE](LICENSE) или [на сайте GNU](https://www.gnu.org/licenses/gpl-3.0.html).

### Ключевые требования:
- 🔍 Вы имеете право изучать, изменять и распространять код
- 📦 При распространении должны предоставляться исходные тексты
- 🚫 Запрещается делать проприетарные производные версии

## Сторонние компоненты

### OpenHardwareMonitor
- Используется оригинальный бинарный файл (`OpenHardwareMonitor.exe`)
- Лицензия: MPL 2.0
- Исходный код: [openhardwaremonitor.org](https://openhardwaremonitor.org)

### Другие зависимости
Полный список: [THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md)

---

## 📦 Распространение
При распространении программы вы должны:
1. Включить файл `LICENSE` (GPL v3)
2. Сохранить папку `/bin/OHM/` с оригинальным OpenHardwareMonitor
3. Предоставить полный исходный код проекта по запросу
