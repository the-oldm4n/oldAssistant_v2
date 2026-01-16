import os
from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget,\
    QFrame, QWidget, QGraphicsOpacityEffect
from PySide6.QtCore import Signal, QPropertyAnimation, Qt, QRectF, QPointF, QEasingCurve,\
    Property, QParallelAnimationGroup, QAbstractAnimation
from PySide6.QtGui import QColor, QCursor, QBrush, QPen, QLinearGradient, QPainter,\
    QPainterPath, QRadialGradient
from bin.apply_color_methods import main_apply_colors
from bin.custom_svg_widget import CustomSvgWidget
from bin.signals import color_signal
from logging_config import debug_logger

class GlowButton(QPushButton):
    def __init__(self, text="", parent=None, glow_color="#4686FD"):
        super().__init__(text, parent)
        self.setMouseTracking(True)
        self.glow_radius = 100
        self._glow_opacity = 0
        self.glow_color = QColor(glow_color)
        
        # Анимация для плавного изменения
        self.animation = QPropertyAnimation(self, b"glow_opacity")
        self.animation.setDuration(200)  # 200ms анимация
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        
    def update_color(self, color):
        self.glow_color = color
    
    @Property(float)
    def glow_opacity(self):
        return self._glow_opacity
        
    @glow_opacity.setter
    def glow_opacity(self, value):
        self._glow_opacity = value
        self.update()
        
    def enterEvent(self, event):
        # Останавливаем текущую анимацию и запускаем новую
        self.animation.stop()
        self.animation.setStartValue(self.glow_opacity)
        self.animation.setEndValue(80)
        self.animation.start()
        
    def leaveEvent(self, event):
        # Останавливаем текущую анимацию и запускаем новую  
        self.animation.stop()
        self.animation.setStartValue(self.glow_opacity)
        self.animation.setEndValue(0)
        self.animation.start()
        
    def mouseMoveEvent(self, event):
        self.update()  # Обновляем позицию свечения
    
    def paintEvent(self, event):
        super().paintEvent(event)
        
        if self.glow_opacity > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Устанавливаем маску кнопки как область отсечения
            mask = self.mask()
            if not mask.isEmpty():
                painter.setClipRegion(mask)
            else:
                # Если маски нет, создаем путь с закруглением по умолчанию
                path = QPainterPath()
                path.addRoundedRect(self.rect(), 15, 15)
                painter.setClipPath(path)
            
            cursor_pos = self.mapFromGlobal(QCursor.pos())
            
            start_color = QColor(self.glow_color)
            start_color.setAlpha(int(self.glow_opacity))
            
            end_color = QColor(self.glow_color)
            end_color.setAlpha(0)
            
            gradient = QRadialGradient(cursor_pos, self.glow_radius)
            gradient.setColorAt(0, start_color)
            gradient.setColorAt(1, end_color)
            
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(cursor_pos, self.glow_radius, self.glow_radius)
            

class GlowFrame(QFrame):
    def __init__(self, parent=None, glow_color="#4686FD"):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.glow_radius = 100
        self._glow_opacity = 0
        self.glow_color = QColor(glow_color)

        # Анимация
        self.animation = QPropertyAnimation(self, b"glow_opacity")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    def update_color(self, color):
        self.glow_color = QColor(color)

    @Property(float)
    def glow_opacity(self):
        return self._glow_opacity

    @glow_opacity.setter
    def glow_opacity(self, value):
        self._glow_opacity = value
        self.update()

    def enterEvent(self, event):
        self.animation.stop()
        self.animation.setStartValue(self.glow_opacity)
        self.animation.setEndValue(80)
        self.animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.animation.stop()
        self.animation.setStartValue(self.glow_opacity)
        self.animation.setEndValue(0)
        self.animation.start()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        self.update()
        super().mouseMoveEvent(event)

    def paintEvent(self, event):
        # Сначала отрисовываем содержимое фрейма (фон, дочерние виджеты)
        super().paintEvent(event)

        # Затем — свечение поверх всего
        if self.glow_opacity > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            # Ограничиваем свечение формой фрейма (чтобы не вылезало за границы)
            path = QPainterPath()
            path.addRoundedRect(self.rect(), 0, 0)
            painter.setClipPath(path)

            cursor_pos = self.mapFromGlobal(QCursor.pos())

            start_color = QColor(self.glow_color)
            start_color.setAlpha(int(self.glow_opacity * 2.55))  # 80 → 204 alpha (макс 255)

            end_color = QColor(self.glow_color)
            end_color.setAlpha(0)

            gradient = QRadialGradient(cursor_pos, self.glow_radius)
            gradient.setColorAt(0, start_color)
            gradient.setColorAt(1, end_color)

            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(cursor_pos, self.glow_radius, self.glow_radius)


class _CustomToggle(QWidget):
    stateChanged = Signal(int)
    toggled = Signal(bool)
    
    def __init__(self, parent=None, checked=False, color="#4686FD"):
        super().__init__(parent)
        self._checked = checked
        self.style_manager = main_apply_colors
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()
        self._color = QColor(color)
        self._update_colors()
        color_signal.color_changed.connect(self.set_color)
        
        
        self._morph_progress = 1.0 if checked else 0.0
        self._rotation_angle = 0.0
        
        # Анимации
        self.morph_animation = QPropertyAnimation(self, b"morph_progress")
        self.morph_animation.setDuration(400)
        self.morph_animation.setEasingCurve(QEasingCurve.InOutCubic)
        
        self.rotation_animation = QPropertyAnimation(self, b"rotation_angle")
        self.rotation_animation.setDuration(400)
        self.rotation_animation.setEasingCurve(QEasingCurve.InOutCubic)

        self.setFixedSize(45, 26)
        self.setCursor(Qt.PointingHandCursor)
        self.set_color()

    def setChecked(self, checked):
        if self._checked != checked:
            self._checked = checked
            self._start_animation()
            self.stateChanged.emit(2 if checked else 0)
            self.toggled.emit(checked)
    
    def isChecked(self):
        return self._checked
    
    def toggle(self):
        self.setChecked(not self._checked)
    
    def _start_animation(self):
        self.morph_animation.stop()
        self.rotation_animation.stop()
        
        self.morph_animation.setStartValue(self._morph_progress)
        self.morph_animation.setEndValue(1.0 if self._checked else 0.0)
        
        if self._checked:
            self.rotation_animation.setStartValue(self._rotation_angle)
            self.rotation_animation.setEndValue(1080)
        else:
            self.rotation_animation.setStartValue(self._rotation_angle)
            self.rotation_animation.setEndValue(0)
        
        self.morph_animation.start()
        self.rotation_animation.start()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle()
    
    def set_color(self):
        """Устанавливает цвет или градиент"""
        self.styles = self.style_manager.load_styles()
        color_data = self.style_manager.get_gradient_color()
        
        if isinstance(color_data, list):
            # Градиент - список цветов
            self._gradient_colors = color_data
            self._color = color_data[0]  # Первый цвет как основной
        else:
            # Один цвет
            self._color = QColor(color_data)
            self._gradient_colors = None
        
        self._update_colors()
        self.update()

    def _update_colors(self):
        """Вычисляет более темный цвет для фона"""
        # Более темный цвет для фона
        self.bg_color = self._get_darker_color(self._color)
        self.borger_color = self._color

    def _get_darker_color(self, color):
        """Возвращает более темную версию цвета"""
        darker = QColor(color)
        darker = darker.darker(110)
        return darker
    
    @Property(float)
    def morph_progress(self):
        return self._morph_progress
    
    @morph_progress.setter
    def morph_progress(self, value):
        self._morph_progress = value
        self.update()
    
    @Property(float)
    def rotation_angle(self):
        return self._rotation_angle
    
    @rotation_angle.setter
    def rotation_angle(self, value):
        self._rotation_angle = value
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Фоновая дорожка
        bg_rect = QRectF(2, 2, self.width() - 4, self.height() - 4)
        painter.setBrush(QColor(240, 240, 240))
        painter.setPen(QPen(self.borger_color, 1))
        painter.drawRoundedRect(bg_rect, 11, 11)
        
        # Активная дорожка
        if self._morph_progress > 0:
            active_width = (self.width() - 4) * self._morph_progress
            
            # Определяем brush ДО отрисовки
            if hasattr(self, '_gradient_colors') and self._gradient_colors:
                # Градиент
                gradient = QLinearGradient(2, 2, active_width, self.height() - 4)
                for i, color in enumerate(self._gradient_colors):
                    gradient.setColorAt(i / (len(self._gradient_colors) - 1), color)
                brush = QBrush(gradient)
            else:
                # Обычный цвет
                active_color = self.bg_color
                active_color.setAlpha(220)
                brush = QBrush(active_color)
            
            # Отрисовка
            if active_width < 22:
                active_rect = QRectF(2, 2, 22, self.height() - 4)
                painter.setBrush(brush)
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(active_rect, 11, 11)
                
                if active_width < 22:
                    clip_rect = QRectF(2 + active_width, 2, 22 - active_width, self.height() - 4)
                    painter.setClipRect(clip_rect)
                    painter.setBrush(QColor(240, 240, 240))
                    painter.setPen(QPen(self.borger_color, 1))
                    painter.drawRoundedRect(bg_rect, 11, 11)
                    painter.setClipping(False)
            else:
                active_rect = QRectF(2, 2, active_width, self.height() - 4)
                painter.setBrush(brush)
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(active_rect, 11, 11)
        
        # Позиция крестика/галочки
        icon_x = 15 + (self.width() - 30) * self._morph_progress
        icon_pos = QPointF(icon_x, self.height() / 2)
        
        painter.save()
        painter.translate(icon_pos)
        
        if self._morph_progress < 0.8:
            # Вращаем крестик
            rotation = self._rotation_angle if self._checked else -self._rotation_angle
            painter.rotate(rotation)
            
            # Крестик такого же размера как галочка
            cross_alpha = 255 * (1.0 - self._morph_progress * 1.2) if self._checked else 255
            cross_color = QColor(100, 100, 100, int(cross_alpha))
            painter.setPen(QPen(cross_color, 2))
            
            # Уменьшаем размер крестика до размера галочки
            size = 4
            painter.drawLine(-size, -size, size, size)
            painter.drawLine(size, -size, -size, size)
        else:
            # Галочка
            check_color = QColor(255, 255, 255)
            painter.setPen(QPen(check_color, 2))
            
            path = QPainterPath()
            path.moveTo(-4, 0)
            path.lineTo(-1, 3)
            path.lineTo(5, -3)
            painter.drawPath(path)
        
        painter.restore()
 
 
class CustomToggle(QWidget):
    stateChanged = Signal(int)
    toggled = Signal(bool)
    
    def __init__(self, text="", parent=None, checked=False, color="#4686FD"):
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Тогл
        self.toggle = _CustomToggle(self, checked, color)
        self.toggle.stateChanged.connect(self.stateChanged)
        self.toggle.toggled.connect(self.toggled)
        
        # Лейбл
        self.label = QLabel(text)
        self.label.setCursor(Qt.PointingHandCursor)
        self.label.mousePressEvent = self._on_label_click
        
        layout.addWidget(self.toggle)
        layout.addWidget(self.label)
        layout.addStretch()
    
    def _on_label_click(self, event):
        self.toggle.toggle()
        event.accept()
    
    def setChecked(self, checked):
        self.toggle.setChecked(checked)
    
    def isChecked(self):
        return self.toggle.isChecked()
    
    def setText(self, text):
        self.label.setText(text)
    
    def text(self):
        return self.label.text()
    
    def toggle(self):
        self.toggle.toggle()
    
    def set_primary_color(self, hex_color):
        self.toggle.set_primary_color(hex_color)
        
        
class AnimatedSidebar(QWidget):
    """Анимированная боковая панель с выдвижением при наведении"""
    
    # Сигнал при клике на элемент
    element_clicked = Signal(str)
    
    def __init__(self, parent=None, elements_data=None):
        super().__init__(parent)
        self.is_expanded = False
        self.elements_data = elements_data or []
        self.text_labels = {}
        self.element_widgets = {}
        self.setAttribute(Qt.WA_Hover)
        self.min_width = 50
        self.max_width = 250
        self.style_manager = main_apply_colors
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()
        color_signal.color_changed.connect(self.set_color)
        self.setup_ui()
        self.setup_animations()
        
    def set_color(self):
        """Устанавливает цвет или градиент"""
        self.styles = self.style_manager.load_styles()
        
        for key, widgets in self.element_widgets.items():
            svg = widgets["svg_widget"]
            if isinstance(svg, CustomSvgWidget):  # или QSvgWidget
                self.style_manager.apply_color_svg(svg, strength=0.95)
                
            frame = widgets["frame"]
            if isinstance(frame, GlowFrame):
                frame.update_color(self.style_manager.get_snow_color())
    
    def setup_ui(self):
        """Настройка интерфейса"""
        # Основной layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(5)
        self.main_layout.setContentsMargins(5, 10, 5, 10)
        
        # Настройки виджета
        self.setFixedWidth(self.min_width)
        
        # Создаем элементы панели
        self.create_elements()
    
    def create_elements(self):
        for item in self.elements_data:
            widget = self.create_element_widget(
                icon_path=item["icon_path"],
                text=item["text"],
                name=item["key"]
            )
            self.main_layout.addWidget(widget)
        self.main_layout.addStretch()
        
    def create_element_widget(self, icon_path: str, text: str, name: str):
        """Создание виджета для одного элемента"""
        # Контейнер для элемента
        element_frame = GlowFrame()
        element_frame.setObjectName("SidebarElement")
        element_frame.setFixedHeight(50)
        element_frame.update_color(self.style_manager.get_snow_color())
        
        # Layout для элемента
        element_layout = QHBoxLayout(element_frame)
        element_layout.setSpacing(15)
        element_layout.setContentsMargins(10, 0, 10, 0)
        
        if icon_path and os.path.exists(icon_path):
            icon_widget = CustomSvgWidget(icon_path)
            icon_widget.setFixedSize(30, 30)
            self.style_manager.apply_color_svg(icon_widget, strength=0.95)
        else:
            # Заглушка, если иконка не найдена
            icon_widget = QLabel()
            icon_widget.setFixedSize(30, 30)
            icon_widget.setAlignment(Qt.AlignCenter)
            icon_widget.setStyleSheet("background: #3498db; color: white; border-radius: 8px; font-weight: bold;")
            icon_widget.setText(name[0].upper())
        
        # Текст элемента
        text_label = QLabel(text)
        text_label.setStyleSheet("font-size: 16px; background: transparent;")
        
        # Создаем эффект прозрачности для текста
        text_effect = QGraphicsOpacityEffect(text_label)
        text_effect.setOpacity(0.0)  # Начинаем полностью прозрачным
        text_label.setGraphicsEffect(text_effect)
        
        # Сохраняем ссылки на виджеты
        element_frame.text_label = text_label
        element_frame.text_effect = text_effect  # Сохраняем эффект
        element_frame.element_name = name
      
        # Добавляем в layout
        element_layout.addWidget(icon_widget, alignment=Qt.AlignmentFlag.AlignLeft)
        element_layout.addWidget(text_label)
        element_layout.addStretch()
        
        def on_frame_clicked():
            self.element_clicked.emit(name)
    
        # Присваиваем функцию как атрибут фрейма
        element_frame.mousePressEvent = lambda e: on_frame_clicked()
        
        self.element_widgets[name] = {
            "frame": element_frame,
            "svg_widget": icon_widget,      # может быть QLabel, но ок
            "text_label": text_label,
            "text_effect": text_effect,
            "icon_path": icon_path
        }
        
        self.text_labels[name] = text_label
        
        return element_frame
        
    def setup_animations(self):
        """Настройка анимаций"""
        # Анимация ширины
        self.width_animation = QPropertyAnimation(self, b"minimumWidth")
        self.width_animation.setDuration(500)
        self.width_animation.setEasingCurve(QEasingCurve.OutCubic)
        
        # Анимация ширины (максимальной)
        self.max_width_animation = QPropertyAnimation(self, b"maximumWidth")
        self.max_width_animation.setDuration(500)
        self.max_width_animation.setEasingCurve(QEasingCurve.OutCubic)
        
    def enterEvent(self, event):
        """Событие при входе курсора"""
        self.expand_sidebar()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        """Событие при выходе курсора"""
        self.collapse_sidebar()
        super().leaveEvent(event)
        
    def expand_sidebar(self):
        # Останавливаем анимации сворачивания, если они идут
        if hasattr(self, '_collapse_group') and self._collapse_group.state() == QAbstractAnimation.Running:
            self._collapse_group.stop()
            # Сразу показываем текст, если он был скрыт
            for i in range(self.main_layout.count() - 1):
                item = self.main_layout.itemAt(i)
                if item and item.widget():
                    frame = item.widget()
                    if hasattr(frame, 'text_label'):
                        frame.text_label.show()

        # Уже раскрыта — выходим
        if self.width() >= self.max_width:
            return

        # Анимация ширины
        self.width_animation.setStartValue(self.width())
        self.width_animation.setEndValue(self.max_width)
        self.max_width_animation.setStartValue(self.maximumWidth())
        self.max_width_animation.setEndValue(self.max_width)

        group = QParallelAnimationGroup(self)
        group.addAnimation(self.width_animation)
        group.addAnimation(self.max_width_animation)

        for i in range(self.main_layout.count() - 1):
            item = self.main_layout.itemAt(i)
            if item and item.widget():
                frame = item.widget()
                if hasattr(frame, 'text_effect'):
                    frame.text_label.show()
                    anim = QPropertyAnimation(frame.text_effect, b"opacity")
                    anim.setDuration(200)
                    anim.setStartValue(frame.text_effect.opacity())
                    anim.setEndValue(1.0)
                    group.addAnimation(anim)

        group.start()
        self._expand_group = group
        self.is_expanded = True
            
    def animate_texts_hide(self):
        """Анимировать исчезновение текста"""
            
        for i in range(self.main_layout.count() - 1):
            item = self.main_layout.itemAt(i)
            if item and item.widget():
                element_frame = item.widget()
                if hasattr(element_frame, 'text_label'):
                    text_label = element_frame.text_label
                    text_effect = element_frame.text_effect
                    
                    # Сохраняем ссылки для лямбды
                    tl = text_label
                    te = text_effect
                    
                    # Анимация прозрачности
                    opacity_anim = QPropertyAnimation(text_effect, b"opacity")
                    opacity_anim.setDuration(150)
                    opacity_anim.setStartValue(text_effect.opacity())
                    opacity_anim.setEndValue(0.0)
                    # Скрываем только после завершения анимации
                    opacity_anim.finished.connect(
                        lambda checked=False, t=tl: t.hide()
                    )
                    opacity_anim.start()
                
    def collapse_sidebar(self):
        # Останавливаем анимацию раскрытия
        if hasattr(self, '_expand_group') and self._expand_group.state() == QAbstractAnimation.Running:
            self._expand_group.stop()

        if self.width() <= self.min_width:
            return

        self.width_animation.setStartValue(self.width())
        self.width_animation.setEndValue(self.min_width)
        self.max_width_animation.setStartValue(self.maximumWidth())
        self.max_width_animation.setEndValue(self.min_width)

        group = QParallelAnimationGroup(self)
        group.addAnimation(self.width_animation)
        group.addAnimation(self.max_width_animation)

        for i in range(self.main_layout.count() - 1):
            item = self.main_layout.itemAt(i)
            if item and item.widget():
                frame = item.widget()
                if hasattr(frame, 'text_effect'):
                    anim = QPropertyAnimation(frame.text_effect, b"opacity")
                    anim.setDuration(150)
                    anim.setStartValue(frame.text_effect.opacity())
                    anim.setEndValue(0.0)
                    anim.finished.connect(lambda t=frame.text_label: t.hide())
                    group.addAnimation(anim)

        group.start()
        self._collapse_group = group
        self.is_expanded = False
        
    def update_element_text(self, key: str, new_text: str):
        """Обновить текст элемента по ключу"""
        label = self.text_labels.get(key)
        if label:
            label.setText(new_text)
        else:
            debug_logger.error(f"Элемент с ключом '{key}' не найден")
        
        

class VersionLabel(QWidget):
    def __init__(self, parent=None, version="1.0.0"):
        super().__init__(parent)
        self.version = version
        
        self.style_manager = main_apply_colors
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()
        color_signal.color_changed.connect(self.apply_color)
        self.init_ui()
        self.apply_color()
        
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 0)
        
        label = QLabel(f"{self.version}")
        label.setObjectName("VersionLabel")
        layout.addWidget(label)
        
    def apply_color(self):
        self.styles = self.style_manager.load_styles()

        style_sheet = ""
        for widget, styles in self.styles.items():
            if widget.startswith("Q"):
                selector = widget
            else:
                selector = f"#{widget}"

            style_sheet += f"{selector} {{\n"
            for prop, value in styles.items():
                style_sheet += f"    {prop}: {value};\n"
            style_sheet += "}\n"

        self.setStyleSheet(style_sheet)


class _CustomToggleSimple(QWidget):
    stateChanged = Signal(int)
    toggled = Signal(bool)
    
    def __init__(self, parent=None, checked=False, color="#4686FD"):
        super().__init__(parent)
        self._checked = checked
        self.style_manager = main_apply_colors
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()
        self._color = QColor(color)
        self._update_colors()
        color_signal.color_changed.connect(self.set_color)
        
        
        self._morph_progress = 1.0 if checked else 0.0
        
        # Анимации
        self.morph_animation = QPropertyAnimation(self, b"morph_progress")
        self.morph_animation.setDuration(400)
        self.morph_animation.setEasingCurve(QEasingCurve.InOutCubic)

        self.setFixedSize(36, 12)
        self.setCursor(Qt.PointingHandCursor)
        self.set_color()

    def setChecked(self, checked):
        if self._checked != checked:
            self._checked = checked
            self._start_animation()
            self.stateChanged.emit(2 if checked else 0)
            self.toggled.emit(checked)
    
    def isChecked(self):
        return self._checked
    
    def toggle(self):
        self.setChecked(not self._checked)
    
    def _start_animation(self):
        self.morph_animation.stop()
        
        self.morph_animation.setStartValue(self._morph_progress)
        self.morph_animation.setEndValue(1.0 if self._checked else 0.0)
        
        self.morph_animation.start()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle()
    
    def set_color(self):
        """Устанавливает цвет или градиент"""
        self.styles = self.style_manager.load_styles()
        color_data = self.style_manager.get_gradient_color()
        
        if isinstance(color_data, list):
            # Градиент - список цветов
            self._gradient_colors = color_data
            self._color = color_data[0]  # Первый цвет как основной
        else:
            # Один цвет
            self._color = QColor(color_data)
            self._gradient_colors = None
        
        self._update_colors()
        self.update()

    def _update_colors(self):
        """Вычисляет более темный цвет для фона"""
        # Более темный цвет для фона
        self.bg_color = self._get_darker_color(self._color)
        self.borger_color = self._color

    def _get_darker_color(self, color):
        """Возвращает более темную версию цвета"""
        darker = QColor(color)
        darker = darker.darker(110)
        return darker
    
    @Property(float)
    def morph_progress(self):
        return self._morph_progress
    
    @morph_progress.setter
    def morph_progress(self, value):
        self._morph_progress = value
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # Фоновая дорожка - полупрозрачный серый
        bg_rect = QRectF(1, 1, width - 2, height - 2)
        painter.setBrush(QColor(100, 100, 100, 60))  # Полупрозрачный серый (альфа=60)
        painter.setPen(QPen(self.borger_color, 1))
        painter.drawRoundedRect(bg_rect, (height - 2) / 2, (height - 2) / 2)
        
        # Активная дорожка
        if self._morph_progress > 0:
            active_width = (width - 2) * self._morph_progress
            
            # Определяем brush
            if hasattr(self, '_gradient_colors') and self._gradient_colors:
                gradient = QLinearGradient(1, 1, active_width, height - 2)
                for i, color in enumerate(self._gradient_colors):
                    gradient.setColorAt(i / (len(self._gradient_colors) - 1), color)
                brush = QBrush(gradient)
            else:
                active_color = self.bg_color
                active_color.setAlpha(220)
                brush = QBrush(active_color)
            
            # Рисуем активную часть поверх фона
            active_rect = QRectF(1, 1, active_width, height - 2)
            painter.setBrush(brush)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(active_rect, (height - 2) / 2, (height - 2) / 2)
 
 
class CustomToggleSimple(QWidget):
    stateChanged = Signal(int)
    toggled = Signal(bool)
    
    def __init__(self, text="", parent=None, checked=False, color="#4686FD"):
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Тогл
        self.toggle = _CustomToggleSimple(self, checked, color)
        self.toggle.stateChanged.connect(self.stateChanged)
        self.toggle.toggled.connect(self.toggled)
        layout.addWidget(self.toggle)
        
        # Лейбл
        if text:
            self.label = QLabel(text)
            self.label.setStyleSheet("background: transparent;")
            self.label.setCursor(Qt.PointingHandCursor)
            self.label.mousePressEvent = self._on_label_click
            layout.addWidget(self.label)

        layout.addStretch()
    
    def _on_label_click(self, event):
        self.toggle.toggle()
        event.accept()
    
    def setChecked(self, checked):
        self.toggle.setChecked(checked)
    
    def isChecked(self):
        return self.toggle.isChecked()
    
    def setText(self, text):
        self.label.setText(text)
    
    def text(self):
        return self.label.text()
    
    def toggle(self):
        self.toggle.toggle()
    
    def set_primary_color(self, hex_color):
        self.toggle.set_primary_color(hex_color)