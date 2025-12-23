from PySide6.QtWidgets import QGraphicsColorizeEffect, QGraphicsEffect
from PySide6.QtGui import QColor, QPixmap, QPainter, QLinearGradient, QBrush, QRadialGradient, QConicalGradient
from PySide6.QtCore import Qt, Property
from PySide6.QtSvgWidgets import QSvgWidget

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
        self._gradient_effect = None  # Новый эффект для градиентов
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

            # Удаляем градиентный эффект если был
            if self._gradient_effect:
                self._gradient_effect.deleteLater()
                self._gradient_effect = None

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

    def applyGradientEffect(self, gradient_data, strength=1.0):
        """
        БЕЗОПАСНЫЙ метод для применения градиента
        """
        try:
            # print("applyGradientEffect вызван")
            # print(f"gradient_data: {gradient_data}")
            
            # Удаляем цветовой эффект если был
            if self._color_effect:
                # print("🗑️ Удаляем старый color effect")
                self._color_effect.deleteLater()
                self._color_effect = None

            # Удаляем старый градиентный эффект
            if self._gradient_effect:
                # print("🗑️ Удаляем старый gradient effect")
                self._gradient_effect.deleteLater()

            # Создаем и применяем градиентный эффект
            # print("Создаем GradientColorizeEffect")
            self._gradient_effect = GradientColorizeEffect(self)
            self._gradient_effect.setGradient(gradient_data)
            self._gradient_effect.setStrength(strength)
            self.setGraphicsEffect(self._gradient_effect)

            # print("Принудительное обновление")
            self._forceUpdate()
            return True

        except Exception as e:
            # print(f"❌ Ошибка применения градиента: {e}")
            # Fallback: пробуем применить первый цвет градиента как обычный цвет
            if gradient_data and gradient_data.get('colors'):
                first_color = gradient_data['colors'][0][1]
                # print(f"Fallback на цвет: {first_color}")
                return self.applyColorEffect(first_color, strength)
            return False

    def _forceUpdate(self):
        """Принудительное обновление (оригинальный метод - НЕ ТРОГАЕМ)"""
        self.update()
        self.repaint()
        if self._parent_button:
            self._parent_button.update()

    # Свойства (оригинальные - НЕ ТРОГАЕМ)
    def getEffectColor(self):
        return self._current_color

    def setEffectColor(self, color):
        self.applyColorEffect(color, self._current_strength)

    effectColor = Property(QColor, getEffectColor, setEffectColor)


class GradientColorizeEffect(QGraphicsEffect):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.gradient_data = None
        self.strength = 1.0

    def setGradient(self, gradient_data):
        self.gradient_data = gradient_data
        self.update()

    def setStrength(self, strength):
        self.strength = strength
        self.update()

    def draw(self, painter):
        if not self.gradient_data:
            self.drawSource(painter)
            return

        # Получаем pixmap источника (наш черный SVG)
        pixmap = self.sourcePixmap(Qt.DeviceCoordinates)
        if pixmap.isNull():
            return

        # Сохраняем состояние painter
        painter.save()
        painter.setOpacity(self.strength)

        # Создаем градиент
        rect = self.sourceBoundingRect()
        gradient = self._create_gradient(rect)

        # Создаем маску из черного SVG
        mask_pixmap = QPixmap(pixmap.size())
        mask_pixmap.fill(Qt.transparent)
        
        mask_painter = QPainter(mask_pixmap)
        mask_painter.setCompositionMode(QPainter.CompositionMode_Source)
        mask_painter.drawPixmap(0, 0, pixmap)
        mask_painter.end()

        # Рисуем градиент с маской
        gradient_pixmap = QPixmap(pixmap.size())
        gradient_pixmap.fill(Qt.transparent)
        
        gradient_painter = QPainter(gradient_pixmap)
        gradient_painter.fillRect(gradient_pixmap.rect(), QBrush(gradient))
        gradient_painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        gradient_painter.drawPixmap(0, 0, mask_pixmap)
        gradient_painter.end()

        # Рисуем результат
        painter.drawPixmap(0, 0, gradient_pixmap)  # offset не нужен
        painter.restore()

    def _create_gradient(self, rect):
        if not self.gradient_data:
            return QLinearGradient(0, 0, 1, 0)

        gradient_type = self.gradient_data.get('type', 'linear')
        colors = self.gradient_data.get('colors', [])

        if gradient_type == 'linear':
            gradient = self._create_linear_gradient(rect)
        elif gradient_type == 'radial':
            gradient = self._create_radial_gradient(rect)
        elif gradient_type == 'conical':
            gradient = self._create_conical_gradient(rect)
        else:
            gradient = QLinearGradient(0, 0, 1, 0)

        # Добавляем цвета
        for pos, color in colors:
            gradient.setColorAt(pos, color)

        return gradient

    def _create_linear_gradient(self, rect):
        direction = self.gradient_data.get('direction', 0)
        
        if isinstance(direction, (int, float)):
            import math
            angle_rad = math.radians(direction)
            x1 = 0.5 - 0.5 * math.cos(angle_rad)
            y1 = 0.5 - 0.5 * math.sin(angle_rad)
            x2 = 0.5 + 0.5 * math.cos(angle_rad)
            y2 = 0.5 + 0.5 * math.sin(angle_rad)
            
            return QLinearGradient(
                rect.width() * x1, rect.height() * y1,
                rect.width() * x2, rect.height() * y2
            )
        else:
            x1, y1, x2, y2 = direction
            return QLinearGradient(
                rect.width() * x1, rect.height() * y1,
                rect.width() * x2, rect.height() * y2
            )

    def _create_radial_gradient(self, rect):
        center = self.gradient_data.get('center', (0.5, 0.5))
        radius = self.gradient_data.get('radius', 0.5)
        
        cx, cy = center
        return QRadialGradient(
            rect.width() * cx, rect.height() * cy,
            min(rect.width(), rect.height()) * radius
        )

    def _create_conical_gradient(self, rect):
        center = self.gradient_data.get('center', (0.5, 0.5))
        angle = self.gradient_data.get('angle', 0)
        
        cx, cy = center
        return QConicalGradient(rect.width() * cx, rect.height() * cy, angle)