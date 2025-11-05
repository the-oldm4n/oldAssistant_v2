import json
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap, QPainter, QLinearGradient
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QGraphicsColorizeEffect

from bin.custom_svg_widget import CustomSvgWidget
from logging_config import debug_logger
from path_builder import get_path


class ApplyColor():
    def __init__(self, parent=None):
        self.parent = parent  # Сохраняем ссылку на родительское окно
        self.color_path = get_path('user_settings', 'color_settings.json')
        self.styles = self.load_styles()

    def load_styles(self):
        """Только загрузка стилей без применения"""
        try:
            with open(self.color_path, 'r') as file:
                self.styles = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            self.styles = {}
        return self.styles

    def apply_to_widget(self, widget, widget_name):
        """Применяет стиль к конкретному виджету"""
        if widget_name in self.styles:
            widget.setStyleSheet(self.format_style(self.styles[widget_name]))

    def apply_color_svg(self, svg_widget, strength: float, specified_color: str = "") -> None:
        """
        Применяет цвет к SVG виджету
        """
        try:
            if specified_color:
                color = QColor(specified_color)
                return svg_widget.applyColorEffect(color, strength)
            if "TitleBar" in self.styles and "border-bottom" in self.styles["TitleBar"]:
                border_value = self.styles["TitleBar"]["border-bottom"]
                color = QColor("#000000")

                # Ваш существующий код извлечения цвета
                gradient_match = re.search(r"qlineargradient\([^)]+\)", border_value)
                if gradient_match:
                    gradient_str = gradient_match.group(0)
                    color_match = re.search(r"stop:0\s+(#[0-9a-fA-F]+)", gradient_str)
                    if color_match:
                        color = QColor(color_match.group(1))
                else:
                    hex_match = re.search(r"#[0-9a-fA-F]{3,6}", border_value)
                    if hex_match:
                        color = QColor(hex_match.group(0))

                if isinstance(svg_widget, CustomSvgWidget):
                    # Используем наш кастомный метод
                    svg_widget.applyColorEffect(color, strength)
                else:
                    # Fallback для обычных QSvgWidget
                    self._apply_effect_fallback(svg_widget, color, strength)

        except Exception as e:
            debug_logger.error(f"Ошибка в apply_color_svg: {e}")

    def _apply_effect_fallback(self, svg_widget, color, strength):
        """Fallback для обычных QSvgWidget"""
        try:
            effect = QGraphicsColorizeEffect()
            effect.setColor(color)
            effect.setStrength(strength)

            # Удаляем старый эффект
            old_effect = svg_widget.graphicsEffect()
            if old_effect:
                old_effect.deleteLater()

            svg_widget.setGraphicsEffect(effect)
            svg_widget.update()

        except Exception as e:
            debug_logger.error(f"❌ Fallback ошибка: {e}")

    def format_style(self, style_dict):
        """Форматирует стиль в строку"""
        return '; '.join(f"{key}: {value}" for key, value in style_dict.items())

    def adjust_color(self, color, brightness=0):
        """
        Корректирует яркость цвета
        :param color: Исходный цвет (hex/rgb/rgba)
        :param brightness: Значение от -100 до 100
        :return: Новый цвет в hex-формате
        """
        from PySide6.QtGui import QColor
        try:
            qcolor = QColor(color)
            if brightness > 0:
                return qcolor.lighter(100 + brightness).name()
            elif brightness < 0:
                return qcolor.darker(100 - brightness).name()
            return qcolor.name()
        except:
            return color
        
    def get_color_from_border(self, widget_key):
        """Извлекает цвет или градиент из CSS-свойства border"""
        try:
            if widget_key and widget_key in self.styles:
                style = self.styles[widget_key]
                border_value = style.get("border", "")

                # Сначала ищем градиент в border
                import re
                gradient_match = re.search(
                    r'qlineargradient\([^)]*\)|qradialgradient\([^)]*\)|qconicalgradient\([^)]*\)',
                    border_value
                )
                
                if gradient_match:
                    return gradient_match.group(0)  # Возвращаем градиент как есть
                
                # Если градиента нет, ищем простой цвет
                color_match = re.search(
                    r'#(?:[0-9a-fA-F]{3}){1,2}|rgb\([^)]*\)|rgba\([^)]*\)',
                    border_value
                )
                return color_match.group(0) if color_match else "#05B8CC"
                
        except Exception as e:
            debug_logger.error(f"Ошибка извлечения цвета: {e}")
        return "#BB05CC"
    
    def apply_progressbar(self, key=None, widget=None, style="solid"):
        """
        Применяет стиль к прогресс-бару
        :param style: "solid" (default), "looper", "circle"
        :param key: Ключ из стилей для извлечения цвета (например "QPushButton")
        :param widget: Ссылка на виджет QProgressBar или CustomProgressBar
        """
        if not widget or not hasattr(widget, 'setStyleSheet'):
            debug_logger.warning("Не передан виджет или он не поддерживает стилизацию")
            return

        try:
            # Получаем цвет или градиент из стилей
            color_or_gradient = self.get_color_from_border(key) if key else "#05B8CC"

            # Если виджет является CustomProgressBar (круговой или looper)
            if hasattr(widget, 'style') and hasattr(widget, 'setProgressColor'):
                
                # Для кругового прогрессбара
                if widget.style == "circle":
                    # Обрабатываем градиент или цвет для кругового прогрессбара
                    if self.is_gradient(color_or_gradient):
                        # Если это градиент, используем первый цвет для прогресса
                        gradient = self.parse_gradient(color_or_gradient, widget.width(), widget.height())
                        widget.setProgressGradient(gradient)
                    else:
                        # Если это простой цвет
                        widget.setProgressColor(color_or_gradient)
                    
                    # Автоматически настраиваем дополнительные цвета
                    self.setup_circular_colors(widget, color_or_gradient)
                
                # Для линейных прогрессбаров применяем CSS стиль
                elif widget.style in ["default", "looper"]:
                    if self.is_gradient(color_or_gradient):
                        # Для градиента создаем специальный CSS
                        progress_style = self.create_gradient_css(color_or_gradient, widget.style)
                    else:
                        # Для простого цвета используем старую логику
                        progress_style = self.create_solid_css(color_or_gradient, widget.style)
                    
                    widget.linear_progress.setStyleSheet(progress_style)
                
                return

            # Старый функционал для обычного QProgressBar
            if self.is_gradient(color_or_gradient):
                progress_style = self.create_gradient_css(color_or_gradient, style)
            else:
                progress_style = self.create_solid_css(color_or_gradient, style)
                
            widget.setStyleSheet(progress_style)

        except Exception as e:
            debug_logger.error(f"Ошибка применения стиля прогресс-бара: {e}")
            # Применяем минимальный рабочий стиль при ошибках
            fallback_style = """
                QProgressBar {
                    border: 1px solid #cccccc;
                    border-radius: 5px;
                }
                QProgressBar::chunk {
                    background-color: #05B8CC;
                }
            """
            if hasattr(widget, 'linear_progress'):
                widget.linear_progress.setStyleSheet(fallback_style)
            else:
                widget.setStyleSheet(fallback_style)

    def is_gradient(self, color_string):
        """Проверяет, является ли строка градиентом"""
        return color_string.startswith('qlineargradient') or color_string.startswith('qradialgradient')

    def parse_gradient(self, gradient_string, width, height):
        """Создает QLinearGradient из строки"""
        try:
            # Парсим параметры градиента
            import re
            params = re.findall(r'([xy]\d):([\d.]+)', gradient_string)
            stops = re.findall(r'stop:([\d.]+)\s+([^,)]+)', gradient_string)
            
            # Создаем градиент
            gradient = QLinearGradient(0, 0, width, height)
            
            for stop in stops:
                pos = float(stop[0])
                color = stop[1].strip()
                gradient.setColorAt(pos, QColor(color))
                
            return gradient
        except Exception as e:
            debug_logger.error(f"Ошибка парсинга градиента: {e}")
            # Возвращаем градиент по умолчанию
            gradient = QLinearGradient(0, 0, width, height)
            gradient.setColorAt(0, QColor("#05B8CC"))
            gradient.setColorAt(1, QColor("#05B8CC"))
            return gradient

    def get_first_gradient_color(self, gradient_string):
        """Извлекает первый цвет из градиента"""
        try:
            import re
            stops = re.findall(r'stop:([\d.]+)\s+([^,)]+)', gradient_string)
            if stops:
                return stops[0][1].strip()
        except:
            pass
        return "#05B8CC"

    def setup_circular_colors(self, widget, color_or_gradient):
        """Автоматически настраивает цвета для кругового прогрессбара"""
        if self.is_gradient(color_or_gradient):
            first_color = self.get_first_gradient_color(color_or_gradient)
            base_color = QColor(first_color)
        else:
            base_color = QColor(color_or_gradient)
        
        # Фон под полосой прогресса (темнее основного цвета)
        widget.setTrackColor(base_color.darker(300))
        
        # Внутренняя область (еще темнее)
        # widget.setBackgroundColor(base_color.darker(300))

    def create_gradient_css(self, gradient, style_type):
        """Создает CSS для градиентного прогрессбара"""
        if style_type == "looper":
            return f"""
                QProgressBar {{
                    border: 1px solid {self.adjust_gradient_border(gradient)};
                    border-radius: 5px;
                    background: {self.adjust_gradient_background(gradient)};
                    height: 20px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background: {gradient};
                    border-radius: 2px;
                    width: 20px;
                    margin: 1px;
                }}
            """
        else:  # solid или default
            return f"""
                QProgressBar {{
                    border: 1px solid {self.adjust_gradient_border(gradient)};
                    border-radius: 5px;
                    height: 20px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background: {gradient};
                }}
            """

    def create_solid_css(self, color, style_type):
        """Создает CSS для одноцветного прогрессбара (старая логика)"""
        if style_type == "looper":
            return f"""
                QProgressBar {{
                    border: 1px solid {self.adjust_color(color, brightness=-30)};
                    border-radius: 5px;
                    background: {self.adjust_color(color, brightness=-80)};
                    height: 20px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 {self.adjust_color(color, brightness=-10)},
                        stop:1 {color}
                    );
                    border-radius: 2px;
                    width: 20px;
                    margin: 1px;
                }}
            """
        else:
            return f"""
                QProgressBar {{
                    border: 1px solid {self.adjust_color(color, brightness=-30)};
                    border-radius: 5px;
                    height: 20px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 {self.adjust_color(color, brightness=-10)},
                        stop:1 {color}
                    );
                }}
            """

    def adjust_gradient_border(self, gradient):
        """Создает темную версию градиента для border"""
        # Для простоты используем первый цвет градиента, затемненный
        first_color = self.get_first_gradient_color(gradient)
        return self.adjust_color(first_color, brightness=-30)

    def adjust_gradient_background(self, gradient):
        """Создает очень темную версию градиента для background"""
        first_color = self.get_first_gradient_color(gradient)
        return self.adjust_color(first_color, brightness=-80)
    
    def get_snow_color(self):
        if "TitleBar" in self.styles and "border-bottom" in self.styles["TitleBar"]:
            border_value = self.styles["TitleBar"]["border-bottom"]
            color = QColor("#FFFFFF")

            # Ваш существующий код извлечения цвета
            gradient_match = re.search(r"qlineargradient\([^)]+\)", border_value)
            if gradient_match:
                gradient_str = gradient_match.group(0)
                color_match = re.search(r"stop:0\s+(#[0-9a-fA-F]+)", gradient_str)
                if color_match:
                    color = QColor(color_match.group(1))
            else:
                hex_match = re.search(r"#[0-9a-fA-F]{3,6}", border_value)
                if hex_match:
                    color = QColor(hex_match.group(0))
        return color