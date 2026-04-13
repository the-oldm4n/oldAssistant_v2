"""Спинбокс для рейтинга с поддержкой модификаторов"""
from PySide6.QtWidgets import QDoubleSpinBox, QApplication
from PySide6.QtCore import Qt

class CustomDoubleSpinBox(QDoubleSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0.0, 10.0)
        self.setSingleStep(1.0)  # обычный шаг
        self.setDecimals(1)
        self.setSuffix("/10")
    
    def stepBy(self, steps):
        modifiers = QApplication.keyboardModifiers()
        
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            effective_step = 0.1
        elif modifiers & Qt.KeyboardModifier.ControlModifier:
            effective_step = 2.0
        else:
            effective_step = self.singleStep()

        new_value = self.value() + (steps * effective_step)
        new_value = round(new_value, 1)
        self.setValue(max(self.minimum(), min(self.maximum(), new_value)))
    
    def keyPressEvent(self, event):
        super().keyPressEvent(event)