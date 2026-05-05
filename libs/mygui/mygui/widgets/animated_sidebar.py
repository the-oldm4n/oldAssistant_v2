"""Анимированная боковая панель"""
import os
import re
from PySide6.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QWidget, QFrame, \
QGraphicsOpacityEffect, QSizePolicy, QPushButton
from PySide6.QtCore import Signal, QPropertyAnimation, Qt, QEasingCurve, \
Property, QParallelAnimationGroup, QAbstractAnimation, QTimer, QRect
from PySide6.QtGui import QColor, QCursor, QBrush, QPainter, QPainterPath, QRadialGradient
from mygui.core.apply_color import main_apply_colors
from mygui.core.signals import color_signal, sidebar_animated_signal
from mygui.widgets.custom_svg import CustomSvgWidget


class AnimatedSidebar(QWidget):
    element_clicked = Signal(str)
    
    def __init__(self, parent=None, elements_data=None, min_width=60, max_width=150, 
                 main_window=None, is_animating=True, position="left"):
        super().__init__(parent)
        color_signal.color_changed.connect(self.set_color)
        self.min_width = min_width
        self.max_width = max_width
        self.position = position
        self.elements_data = elements_data
        self.is_animating = is_animating
        self.text_labels = {}
        self.element_widgets = {}
        self.is_expanded = False
        self.active_key = None
        self.dim_overlay = None
        self.setAttribute(Qt.WA_Hover)
        self.style_manager = main_apply_colors
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()
        self.setup_ui()
        
        if is_animating:
            self.geo_anim = QPropertyAnimation(self, b"geometry")
            self.geo_anim.setDuration(300)
            self.geo_anim.setEasingCurve(QEasingCurve.OutCubic)
        else:
            self.setFixedWidth(self.max_width)
            self.is_expanded = True

        self.expand_timer = QTimer()
        self.expand_timer.setSingleShot(True)
        self.expand_timer.timeout.connect(self.expand_sidebar)
        
        self.collapse_timer = QTimer()
        self.collapse_timer.setSingleShot(True)
        self.collapse_timer.timeout.connect(self.collapse_sidebar)

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
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.top_layout = QVBoxLayout()
        self.top_layout.setContentsMargins(0, 0, 0, 0)

        self.bottom_layout = QVBoxLayout()
        self.bottom_layout.setContentsMargins(5, 5, 5, 5)
        self.bottom_layout.setSpacing(5)

        layout.addLayout(self.top_layout)
        layout.addStretch()
        layout.addLayout(self.bottom_layout)

        self.setFixedWidth(self.min_width)
        self.create_elements()

    def get_dim_overlay(self):
        if self.is_expanded:
            self.dim_overlay.setGeometry(1, 1, self.parent().width() - 2, self.parent().height() - 2)
            self.dim_overlay.show()
            effect = self.dim_overlay.graphicsEffect()
            if effect:
                self.dim_opacity_anim = QPropertyAnimation(effect, b"opacity")
                self.dim_opacity_anim.setDuration(150)
                self.dim_opacity_anim.setStartValue(0.0)
                self.dim_opacity_anim.setEndValue(1.0)
                self.dim_opacity_anim.start()
            self.raise_()
        else:
            if hasattr(self, 'dim_overlay') and self.dim_overlay:
                effect = self.dim_overlay.graphicsEffect()
                if effect:
                    self.dim_opacity_anim = QPropertyAnimation(effect, b"opacity")
                    self.dim_opacity_anim.setDuration(150)
                    self.dim_opacity_anim.setStartValue(effect.opacity())
                    self.dim_opacity_anim.setEndValue(0.0)
                    self.dim_opacity_anim.finished.connect(self.dim_overlay.hide)
                    self.dim_opacity_anim.start()
                else:
                    self.dim_overlay.hide()

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
        text_label.setStyleSheet("font-size: 18px; background: transparent;")
        
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
    
    def expand_sidebar(self):
        if not self.is_animating or self.width() >= self.max_width:
            return
        
        parent = self.parent()
        if not parent:
            return
        group = QParallelAnimationGroup(self)
        # Снимаем ограничения
        self.setMinimumWidth(0)
        self.setMaximumWidth(16777215)  # QWIDGETSIZE_MAX
        
        new_height = parent.height() - 20
        if self.position == "left":
            end_geo = QRect(1, 0, self.max_width, new_height)
        else:
            end_geo = QRect(parent.width() - self.max_width - 1, 0, self.max_width, new_height)
        
        self.geo_anim.stop()
        self.geo_anim.setStartValue(self.geometry())
        self.geo_anim.setEndValue(end_geo)
        self.geo_anim.start()
        self.is_expanded = True

        for widget in self._get_all_widgets():
            if hasattr(widget, 'text_label') and hasattr(widget, 'text_effect'):
                widget.text_label.show()
                anim = QPropertyAnimation(widget.text_effect, b"opacity")
                anim.setDuration(100)
                anim.setStartValue(widget.text_effect.opacity())
                anim.setEndValue(1.0)
                group.addAnimation(anim)
            elif hasattr(widget, '_opacity_effect'):
                widget.show()
                anim = QPropertyAnimation(widget._opacity_effect, b"opacity")
                anim.setDuration(100)
                anim.setStartValue(widget._opacity_effect.opacity())
                anim.setEndValue(1.0)
                group.addAnimation(anim)
        group.start()
        # После анимации возвращаем ограничения
        def restore():
            self.setMinimumWidth(self.max_width)
            self.setMaximumWidth(self.max_width)
        self.geo_anim.finished.connect(restore)

        if not hasattr(self, 'dim_overlay') or self.dim_overlay is None:
            self.dim_overlay = QWidget(self.parent())
            self.dim_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 200); border-radius: 20px;")
            self.dim_opacity_effect = QGraphicsOpacityEffect(self.dim_overlay)
            self.dim_opacity_effect.setOpacity(0.0)
            self.dim_overlay.setGraphicsEffect(self.dim_opacity_effect)

        QTimer.singleShot(50, self.get_dim_overlay)

    def collapse_sidebar(self):
        if not self.is_animating or self.width() <= self.min_width:
            return
        
        parent = self.parent()
        if not parent:
            return
        group = QParallelAnimationGroup(self)
        # Снимаем ограничения
        self.setMinimumWidth(0)
        self.setMaximumWidth(16777215)
        
        new_height = parent.height() - 20
        if self.position == "left":
            end_geo = QRect(1, 0, self.min_width, new_height)
        else:
            end_geo = QRect(parent.width() - self.min_width - 1, 0, self.min_width, new_height)
        
        self.geo_anim.stop()
        self.geo_anim.setStartValue(self.geometry())
        self.geo_anim.setEndValue(end_geo)
        self.geo_anim.start()
        self.is_expanded = False

        for widget in self._get_all_widgets():
            if hasattr(widget, 'text_label') and hasattr(widget, 'text_effect'):
                widget.text_label.show()
                anim = QPropertyAnimation(widget.text_effect, b"opacity")
                anim.setDuration(10)
                anim.setStartValue(widget.text_effect.opacity())
                anim.setEndValue(0.0)
                group.addAnimation(anim)
            elif hasattr(widget, '_opacity_effect'):
                anim = QPropertyAnimation(widget._opacity_effect, b"opacity")
                anim.setDuration(10)
                anim.setStartValue(widget._opacity_effect.opacity())
                anim.setEndValue(0.0)
                anim.finished.connect(lambda w=widget: w.hide())
                group.addAnimation(anim)

        group.start()
        
        def restore():
            self.setMinimumWidth(self.min_width)
            self.setMaximumWidth(self.min_width)
        self.geo_anim.finished.connect(restore)

        QTimer.singleShot(50, self.get_dim_overlay)
    
    def enterEvent(self, event):
        self.collapse_timer.stop()
        self.expand_timer.start(50)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        self.expand_timer.stop()
        if self.is_expanded:
            self.collapse_timer.start(50)
        super().leaveEvent(event)

    def showEvent(self, event):
        """При первом показе задаем правильные размеры"""
        if self.is_animating:
            self.get_geometry_sidebar()
        super().showEvent(event)
    
    def finalize_setup(self):
        """Вызвать после добавления всех кастомных виджетов"""
        if not self.is_animating:
            self.set_always_expanded()

    def set_always_expanded(self):
        """Принудительно раскрыть панель и отключить анимацию"""
        self.setAttribute(Qt.WA_Hover, False)
        self.setFixedWidth(self.max_width)
        
        # Показываем все тексты у основных элементов
        for widget in self._get_all_widgets():
            if hasattr(widget, 'text_label') and hasattr(widget, 'text_effect'):
                widget.text_label.show()
                widget.text_effect.setOpacity(1.0)
            elif hasattr(widget, '_opacity_effect'):
                widget.show()
                widget._opacity_effect.setOpacity(1.0)
        
        # Показываем кастомные виджеты в bottom_layout
        for i in range(self.bottom_layout.count()):
            item = self.bottom_layout.itemAt(i)
            if item and item.widget():
                w = item.widget()
                if hasattr(w, '_opacity_effect'):
                    w.show()
                    w._opacity_effect.setOpacity(1.0)
                else:
                    w.show()
        
        self.is_expanded = True

    def set_active_element(self, key: str):
        """Устанавливает активный элемент по ключу"""
        if self.active_key and self.active_key in self.element_widgets:
            old_frame = self.element_widgets[self.active_key]["frame"]
            old_frame.setActive(False)
        
        if key in self.element_widgets:
            new_frame = self.element_widgets[key]["frame"]
            new_frame.setActive(True)
            self.active_key = key

    def _get_all_widgets(self):
        """Возвращает все виджеты из top_layout и bottom_layout"""
        widgets = []
        for layout in (self.top_layout, self.bottom_layout):
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget():
                    widgets.append(item.widget())
        return widgets
    
    def update_element_text(self, key, text):
        if key in self.text_labels:
            self.text_labels[key].setText(text)
    
    def get_geometry_sidebar(self):
        if self.parent():
            new_height = self.parent().height() - 20
            
            if self.position == "left":
                x_pos = 1
            else:
                x_pos = self.parent().width() - self.max_width - 1
            
            if self.is_expanded:
                self.setGeometry(x_pos, 0, self.max_width, new_height)
            else:
                if self.position == "left":
                    x_pos_collapsed = 1
                else:
                    x_pos_collapsed = self.parent().width() - self.min_width - 1
                self.setGeometry(x_pos_collapsed, 0, self.min_width, new_height)
    
    def on_parent_resize(self):
        """Вызывается при изменении размера родительского окна"""
        if self.is_animating:
            self.get_geometry_sidebar()


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