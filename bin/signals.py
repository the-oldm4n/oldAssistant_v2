from PySide6.QtCore import QObject, Signal


class ColorChangeSignal(QObject):
    color_changed = Signal()

color_signal = ColorChangeSignal()

class GuiSignals(QObject):
    open_widget_signal = Signal()
    close_widget_signal = Signal()

gui_signals = GuiSignals()

class ProgressBarSignals(QObject):
    start_progress = Signal()
    stop_progress = Signal()

progress_signal = ProgressBarSignals()

class CommandsChangeSignal(QObject):
    commands_updated = Signal()

commands_signal = CommandsChangeSignal()


class WidgetButtonsSignal(QObject):
    buttons_updated = Signal()

widget_btns_signal = WidgetButtonsSignal()
