from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QGraphicsColorizeEffect
from PySide6.QtGui import QColor, Qt
from PySide6.QtCore import Property


class CustomSvgWidget(QSvgWidget):
    """
    Кастомный SVG виджет для встраивания в кнопки
    Автоматически синхронизируется с родительской кнопкой
    """

    def __init__(self, svg_path, parent_button=None):
        """
        :param svg_path: путь к SVG файлу
        :param parent_button: родительская кнопка (QPushButton)
        """
        super().__init__(parent_button)  # Передаем кнопку как родителя
        self._parent_button = parent_button
        self._color_effect = None
        self._current_color = QColor("#000000")
        self._current_strength = 1.0

        # Загружаем SVG
        if svg_path:
            self.load(svg_path)

        # Настройки для встраивания в кнопку
        self.setStyleSheet("background: transparent; border: none;")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def applyColorEffect(self, color, strength=1.0):
        """
        Применяет цветовой эффект
        """
        try:
            self._current_color = color
            self._current_strength = strength

            # Удаляем старый эффект
            if self._color_effect:
                self._color_effect.deleteLater()

            # Создаем и применяем эффект
            self._color_effect = QGraphicsColorizeEffect(self)
            self._color_effect.setColor(color)
            self._color_effect.setStrength(strength)
            self.setGraphicsEffect(self._color_effect)

            self._forceUpdate()
            return True

        except Exception as e:
            print(f"❌ Ошибка применения цвета: {e}")
            return False

    def _forceUpdate(self):
        """Принудительное обновление"""
        self.update()
        self.repaint()
        if self._parent_button:
            self._parent_button.update()

    # Свойства
    def getEffectColor(self):
        return self._current_color

    def setEffectColor(self, color):
        self.applyColorEffect(color, self._current_strength)

    effectColor = Property(QColor, getEffectColor, setEffectColor)