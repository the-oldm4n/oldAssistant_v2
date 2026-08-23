from PySide6.QtCore import QObject, Signal, QDateTime


class ColorChangeSignal(QObject):
    color_changed = Signal()

color_signal = ColorChangeSignal()

class GuiSignals(QObject):
    open_widget_signal = Signal()
    close_widget_signal = Signal()

gui_signals = GuiSignals()


class CommandsChangeSignal(QObject):
    commands_updated = Signal()
    commands_reloaded = Signal()

commands_signal = CommandsChangeSignal()


class WidgetButtonsSignal(QObject):
    buttons_updated = Signal()

widget_btns_signal = WidgetButtonsSignal()

class UpdatePresetsSignal(QObject):
    presets_updated = Signal()

update_presets_signal = UpdatePresetsSignal()


class ToolWidgetSignal(QObject):
    open_settings = Signal()
    open_main_window = Signal()
    trigger_capture_area = Signal()
    trigger_open_shortcuts = Signal()
    run_command = Signal(str, str, str)
    add_reminder = Signal(str, QDateTime)
    show_reminders = Signal()

tool_widget_signal = ToolWidgetSignal()


class ResizeSignal(QObject):
    is_resizing = Signal()

resize_signal = ResizeSignal()


class CensorSignal(QObject):
    update_count = Signal(str)

censor_signal = CensorSignal()