"""Сигналы для обмена данными между компонентами"""
from PySide6.QtCore import QObject, Signal

class ColorSignal(QObject):
    """Сигналы для обновления цветов"""
    color_changed = Signal()

class UpdatePresetsSignal(QObject):
    """Сигналы для обновления пресетов"""
    presets_updated = Signal()

class SidebarAnimatedSignal(QObject):
    """Сигналы для анимации боковой панели"""
    is_animating = Signal(bool)
    request_unfreeze = Signal()
    update_delay = Signal(int)
    update_overlay = Signal()


# Глобальные экземпляры сигналов
color_signal = ColorSignal()
update_presets_signal = UpdatePresetsSignal()
sidebar_animated_signal = SidebarAnimatedSignal()