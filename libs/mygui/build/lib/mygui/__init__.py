"""MyGUI - Библиотека кастомных виджетов на PySide6"""

from .core.apply_color import ApplyColor, main_apply_colors
from .core.signals import ColorSignal, UpdatePresetsSignal, SidebarAnimatedSignal, color_signal, update_presets_signal, sidebar_animated_signal

from .widgets.custom_svg import CustomSvgWidget, GradientColorizeEffect
from .widgets.animated_sidebar import AnimatedSidebar, GlowFrame
from .widgets.custom_toggle import CustomToggle
from .widgets.version_label import VersionLabel
from .widgets.custom_label import CustomLabel
from .widgets.custom_spinbox import CustomDoubleSpinBox
from .widgets.custom_progressbar import CustomProgressBar, SVGProgressBar
from .widgets.modern_progress import ModernProgressBar, ProgressType

from .dialogs.color_settings import ColorSettingsWindow
from .dialogs.save_preset import SavePresetDialog
from .dialogs.color_picker import SimpleColorPicker

from .preview.gradient_preview import GradientPreview

__version__ = "1.0.0"

__all__ = [
    'ApplyColor',
    'main_apply_colors',
    'ColorSignal',
    'UpdatePresetsSignal',
    'SidebarAnimatedSignal',
    'color_signal',
    'update_presets_signal',
    'sidebar_animated_signal',
    'CustomSvgWidget',
    'GradientColorizeEffect',
    'AnimatedSidebar',
    'GlowFrame',
    'CustomToggle',
    'VersionLabel',
    'CustomLabel',
    'CustomDoubleSpinBox',
    'SVGProgressBar',
    'CustomProgressBar',
    'ModernProgressBar',
    'ProgressType',
    'ColorSettingsWindow',
    'SavePresetDialog',
    'SimpleColorPicker',
    'GradientPreview',
    'config',
]