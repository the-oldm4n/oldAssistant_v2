from PySide6.QtGui import QCursor, QIcon, QFont, QDesktopServices, QAction, QPixmap, QPainter, QMouseEvent,\
    QFontDatabase, QPainterPath, QImage
from PySide6.QtWidgets import QVBoxLayout, QWidget, QStackedWidget
from PySide6.QtCore import Signal, QTimer, Qt, QEasingCurve, QPropertyAnimation, QRect, QEvent, QUrl, QPoint, Slot,\
    QThread, QThreadPool, QParallelAnimationGroup


class SlidingStackedWidget(QWidget):
    current_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setAttribute(Qt.WA_StyledBackground, True)

        self.setObjectName("SlidingStackedWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.layout.addWidget(self.stacked_widget)
        
        self.current_index = 0
        self.animation_duration = 300
        self.animation = None
        
        
    def add_page(self, widget: QWidget):
        self.stacked_widget.addWidget(widget)
        if self.width() > 0:
            widget.resize(self.width(), self.height())
    
    def switch_to(self, index: int, direction: str = "right"):
        if index == self.current_index:
            return
        
        # Определяем направление
        if direction == "right":
            start_x = self.width()
            end_x = 0
            next_start_x = -self.width()
            next_end_x = 0
        elif direction == "left":
            start_x = -self.width()
            end_x = 0
            next_start_x = self.width()
            next_end_x = 0
        elif direction == "top":
            start_y = -self.height()
            end_y = 0
            next_start_y = self.height()
            next_end_y = 0
        else:  # bottom
            start_y = self.height()
            end_y = 0
            next_start_y = -self.height()
            next_end_y = 0
        
        current_widget = self.stacked_widget.widget(self.current_index)
        next_widget = self.stacked_widget.widget(index)

        next_widget.setGeometry(0, 0, self.width(), self.height())
        next_widget.resize(self.width(), self.height())
        
        # Устанавливаем начальные позиции
        if direction in ["right", "left"]:
            current_widget.move(start_x, 0)
            next_widget.move(next_start_x, 0)
        else:
            current_widget.move(0, start_y)
            next_widget.move(0, next_start_y)
        
        current_widget.hide()
        # Показываем новый виджет
        next_widget.show()
        next_widget.raise_()
        
        # Создаем группу анимаций
        self.anim_group = QParallelAnimationGroup()
        
        # Анимация позиции текущего виджета
        current_pos_anim = QPropertyAnimation(current_widget, b"pos")
        current_pos_anim.setDuration(self.animation_duration)
        current_pos_anim.setStartValue(current_widget.pos())
        current_pos_anim.setEndValue(QPoint(end_x if direction in ["right", "left"] else 0, 
                                            end_y if direction in ["top", "bottom"] else 0))
        current_pos_anim.setEasingCurve(QEasingCurve.OutCubic)
        
        # Анимация позиции нового виджета
        next_pos_anim = QPropertyAnimation(next_widget, b"pos")
        next_pos_anim.setDuration(self.animation_duration)
        next_pos_anim.setStartValue(next_widget.pos())
        next_pos_anim.setEndValue(QPoint(next_end_x if direction in ["right", "left"] else 0,
                                          next_end_y if direction in ["top", "bottom"] else 0))
        next_pos_anim.setEasingCurve(QEasingCurve.OutCubic)
        
        self.anim_group.addAnimation(current_pos_anim)
        self.anim_group.addAnimation(next_pos_anim)

        self.anim_group.finished.connect(
            lambda: self._finish_animation(index, current_widget, next_widget)
        )
        self.current_changed.emit(index)
        self.anim_group.start()
        self.current_index = index

        self.update_current_page()
    
    def _finish_animation(self, index, current_widget, next_widget):
        """Завершение анимации"""
        self.stacked_widget.setCurrentIndex(index)
        current_widget.move(0, 0)
        next_widget.move(0, 0)
    
    def next_page(self):
        self.switch_to((self.current_index + 1) % self.stacked_widget.count(), "left")
    
    def prev_page(self):
        self.switch_to((self.current_index - 1) % self.stacked_widget.count(), "right")

    def update_current_page(self):
        """Обновляет только текущую страницу"""
        current = self.stacked_widget.currentWidget()
        if hasattr(current, 'refresh_data'):
            current.refresh_data()
        elif hasattr(current, 'update_colors'):
            current.update_colors()
        elif hasattr(current, 'update'):
            current.update()