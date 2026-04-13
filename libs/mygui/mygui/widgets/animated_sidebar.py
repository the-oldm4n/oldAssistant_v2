"""Анимированная боковая панель"""
import os
import re
from PySide6.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QWidget, QFrame, QGraphicsOpacityEffect
from PySide6.QtCore import Signal, QPropertyAnimation, Qt, QEasingCurve, Property, QParallelAnimationGroup, QAbstractAnimation
from PySide6.QtGui import QColor, QCursor, QBrush, QPainter, QPainterPath, QRadialGradient

from mygui.core.apply_color import main_apply_colors
from mygui.core.signals import color_signal, sidebar_animated_signal
from mygui.widgets.custom_svg import CustomSvgWidget

class AnimatedSidebar(QWidget):
    """Анимированная боковая панель с выдвижением при наведении"""
    
    # Сигнал при клике на элемент
    element_clicked = Signal(str)
    
    def __init__(self, parent=None, elements_data=None, min_width=60, max_width=150, main_window=None):
        super().__init__(parent)
        self.main = main_window
        self.is_expanded = False
        self.elements_data = elements_data or []
        self.text_labels = {}
        self.element_widgets = {}
        self.setAttribute(Qt.WA_Hover)
        self.min_width = min_width
        self.max_width = max_width
        self.active_key = None
        self._original_left_width = None
        self._original_right_width = None
        self._original_right_min = None
        self.style_manager = main_apply_colors
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()
        color_signal.color_changed.connect(self.set_color)
        self.setup_ui()
        self.setup_animations()

    def add_custom_widget(self, widget: QWidget):
        """Добавить произвольный виджет в нижнюю часть панели"""
        effect = widget.graphicsEffect()
        if not effect or not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        effect.setOpacity(0.0)
        widget._opacity_effect = effect
        widget.hide()

        self.bottom_layout.addWidget(widget)
        
    def set_color(self):
        """Устанавливает цвет или градиент"""
        self.styles = self.style_manager.load_styles()
        
        for key, widgets in self.element_widgets.items():
            svg = widgets["svg_widget"]
            if isinstance(svg, CustomSvgWidget):
                self.style_manager.apply_color_svg(svg)
                
            frame = widgets["frame"]
            if isinstance(frame, GlowFrame):
                frame.update_color(self.style_manager.get_raw_color())

    def set_active_element(self, key: str):
        """Устанавливает активный элемент по ключу"""
        if self.active_key and self.active_key in self.element_widgets:
            old_frame = self.element_widgets[self.active_key]["frame"]
            old_frame.setActive(False)
        
        if key in self.element_widgets:
            new_frame = self.element_widgets[key]["frame"]
            new_frame.setActive(True)
            self.active_key = key

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(5)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.top_layout = QVBoxLayout()
        self.top_layout.setSpacing(5)
        self.top_layout.setContentsMargins(0, 0, 0, 0)

        self.bottom_layout = QVBoxLayout()
        self.bottom_layout.setSpacing(5)
        self.bottom_layout.setContentsMargins(0, 0, 0, 0)

        self.main_layout.addLayout(self.top_layout)
        self.main_layout.addStretch()
        self.main_layout.addLayout(self.bottom_layout)

        self.setFixedWidth(self.min_width)
        self.create_elements()
    
    def create_elements(self):
        for item in self.elements_data:
            widget = self.create_element_widget(
                icon_path=item["icon_path"],
                text=item["text"],
                name=item["key"]
            )
            self.top_layout.addWidget(widget)
        
    def create_element_widget(self, icon_path: str, text: str, name: str):
        """Создание виджета для одного элемента"""
        # Контейнер для элемента
        element_frame = GlowFrame()
        element_frame.setObjectName("SidebarElement")
        element_frame.setFixedHeight(50)
        element_frame.update_color(self.style_manager.get_raw_color())
        
        # Layout для элемента
        element_layout = QHBoxLayout(element_frame)
        element_layout.setSpacing(15)
        element_layout.setContentsMargins(15, 0, 15, 0)
        
        if icon_path and os.path.exists(icon_path):
            icon_widget = CustomSvgWidget(icon_path)
            icon_widget.setFixedSize(30, 30)
            self.style_manager.apply_color_svg(icon_widget)
        else:
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
        text_effect.setOpacity(0.0)
        text_label.setGraphicsEffect(text_effect)
        text_label.hide()
        
        # Сохраняем ссылки на виджеты
        element_frame.text_label = text_label
        element_frame.text_effect = text_effect
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
            "svg_widget": icon_widget,
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
        sidebar_animated_signal.request_unfreeze.emit()
        self.collapse_sidebar()
        super().leaveEvent(event)

    def _get_all_widgets(self):
        """Возвращает все виджеты из top_layout и bottom_layout"""
        widgets = []
        for layout in (self.top_layout, self.bottom_layout):
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget():
                    widgets.append(item.widget())
        return widgets
        
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

        self.width_animation.setStartValue(self.width())
        self.width_animation.setEndValue(self.max_width)
        self.max_width_animation.setStartValue(self.maximumWidth())
        self.max_width_animation.setEndValue(self.max_width)

        group = QParallelAnimationGroup(self)
        group.addAnimation(self.width_animation)
        group.addAnimation(self.max_width_animation)

        if self.main:
            left_widget = None
            right_widget = None
            
            if hasattr(self.main, 'left_panel'):
                left_widget = self.main.left_panel
                self._original_left_width = left_widget.width()
                left_widget.setMinimumWidth(self._original_left_width)
                left_widget.setMaximumWidth(self._original_left_width)
            
            if hasattr(self.main, 'right_panel'):
                right_widget = self.main.right_panel
                self._original_right_width = right_widget.width()
                self._original_right_min = right_widget.minimumWidth()

        if self._original_right_width is not None and self._original_right_min is not None:
            current_available_space = self._original_right_width - self._original_right_min
        else:
            current_available_space = 0

        # Проверяем что right_widget существует перед использованием
        if current_available_space < self.max_width and right_widget is not None:
            new_temp_min = max(50, right_widget.width() - self.max_width - 10) 
            right_widget.setMinimumWidth(new_temp_min)
            
            if hasattr(self.main, 'splitter'):
                self.main.splitter.refresh()

        sidebar_animated_signal.is_animating.emit(True)

        for widget in self._get_all_widgets():
            if hasattr(widget, 'text_label') and hasattr(widget, 'text_effect'):
                widget.text_label.show()
                anim = QPropertyAnimation(widget.text_effect, b"opacity")
                anim.setDuration(200)
                anim.setStartValue(widget.text_effect.opacity())
                anim.setEndValue(1.0)
                group.addAnimation(anim)
            elif hasattr(widget, '_opacity_effect'):
                widget.show()
                anim = QPropertyAnimation(widget._opacity_effect, b"opacity")
                anim.setDuration(200)
                anim.setStartValue(widget._opacity_effect.opacity())
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
        self.width_animation.setStartValue(self.width())
        self.width_animation.setEndValue(self.min_width)
        self.max_width_animation.setStartValue(self.maximumWidth())
        self.max_width_animation.setEndValue(self.min_width)

        group = QParallelAnimationGroup(self)
        group.addAnimation(self.width_animation)
        group.addAnimation(self.max_width_animation)

        group.finished.connect(self._restore_left_panel)
        group.finished.connect(lambda: sidebar_animated_signal.is_animating.emit(False))

        if self.width() <= self.min_width:
            return

        for widget in self._get_all_widgets():
            if hasattr(widget, 'text_label') and hasattr(widget, 'text_effect'):
                widget.text_label.show()
                anim = QPropertyAnimation(widget.text_effect, b"opacity")
                anim.setDuration(200)
                anim.setStartValue(widget.text_effect.opacity())
                anim.setEndValue(0.0)
                group.addAnimation(anim)
            elif hasattr(widget, '_opacity_effect'):
                anim = QPropertyAnimation(widget._opacity_effect, b"opacity")
                anim.setDuration(150)
                anim.setStartValue(widget._opacity_effect.opacity())
                anim.setEndValue(0.0)
                anim.finished.connect(lambda w=widget: w.hide())  # скрываем после анимации
                group.addAnimation(anim)

        group.start()
        self._collapse_group = group
        self.is_expanded = False

    def _restore_left_panel(self):
        """Возвращает левой панели возможность менять размер"""
        if self.main and hasattr(self.main, 'left_panel') and hasattr(self.main, 'right_panel'):
            left_widget = self.main.left_panel
            right_widget = self.main.right_panel

            left_widget.setMinimumWidth(290)
            left_widget.setMaximumWidth(16777215) # QWIDGETSIZE_MAX

            right_widget.setMinimumWidth(350)
        
    def update_element_text(self, key: str, new_text: str):
        """Обновить текст элемента по ключу"""
        label = self.text_labels.get(key)
        if label:
            label.setText(new_text)


class GlowFrame(QFrame):
    def __init__(self, parent=None, glow_color="#4686FD"):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.glow_radius = 100
        self._glow_opacity = 0
        self.start_color = QColor("#4686FD")
        self.end_color = QColor("#4686FD")
        self._active = False

        # Анимация
        self.animation = QPropertyAnimation(self, b"glow_opacity")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

        self.update_color(glow_color)

    def setActive(self, active: bool):
        """Устанавливает активное состояние"""
        self._active = active
        # Обновляем стиль
        self.style().polish(self)
    
    def isActive(self) -> bool:
        return self._active
    
    active = Property(bool, isActive, setActive)

    def update_color(self, style):
        """
        Обновляет стиль свечения.
        
        Принимает:
        1. Цвет в виде строки: "#RRGGBB" - создается один цвет
        2. Градиент Qt строка: извлекаются первый и последний цвета
        
        Всегда создается радиальный градиент из двух цветов.
        """
        if isinstance(style, str):
            hex_colors = re.findall(r'#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b', style)
            
            if len(hex_colors) >= 2:
                self.start_color = QColor(hex_colors[0])
                self.end_color = QColor(hex_colors[-1])
            elif len(hex_colors) == 1:
                color = QColor(hex_colors[0])
                self.start_color = color
                self.end_color = color
            elif style.startswith("#"):
                color = QColor(style)
                self.start_color = color
                self.end_color = color
            else:
                try:
                    color = QColor(style)
                    self.start_color = color
                    self.end_color = color
                except:
                    self.start_color = QColor("#4686FD")
                    self.end_color = QColor("#4686FD")

    def _create_radial_gradient(self, center_pos):
        """Создает радиальный градиент для эллипса"""
        gradient = QRadialGradient(center_pos, self.glow_radius)

        start = QColor(self.start_color)
        start.setAlpha(int(self.glow_opacity * 2.55))
        
        end = QColor(self.end_color)
        end.setAlpha(int(self.glow_opacity * 0.8))
        
        transparent_end = QColor(self.end_color)
        transparent_end.setAlpha(0)
        
        gradient.setColorAt(0, start)
        gradient.setColorAt(0.7, end)
        gradient.setColorAt(1, transparent_end)
        
        return gradient

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
        super().paintEvent(event)

        if self.glow_opacity > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            path = QPainterPath()
            path.addRoundedRect(self.rect(), 0, 0)
            painter.setClipPath(path)

            cursor_pos = self.mapFromGlobal(QCursor.pos())

            gradient = self._create_radial_gradient(cursor_pos)

            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(cursor_pos, self.glow_radius, self.glow_radius)