import json
import re

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtSvg import *
from PySide6.QtSvgWidgets import *
from PySide6.QtWidgets import *

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
            
            self.gradient_data = self.parse_gradient_from_styles()
            if self.gradient_data == None:
                
            
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
                        
            else:
                if isinstance(svg_widget, CustomSvgWidget):
                    return svg_widget.applyGradientEffect(self.gradient_data, strength)
                else:
                    # Fallback для обычных QSvgWidget - используем первый цвет
                    debug_logger.warning("Градиенты поддерживаются только для CustomSvgWidget, используем первый цвет")
                    if self.gradient_data and self.gradient_data.get('colors'):
                        first_color = self.gradient_data['colors'][0][1]
                        return self.apply_color_svg(svg_widget, strength, first_color)
                    return False

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
    
    def get_gradient_darker(self):
        color_or_gradient = self.get_color_from_border("border")
        return self.adjust_gradient_border(color_or_gradient, only_first_color=False)
    
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
    
    def get_gradient_colors(self, gradient_string):
        """Извлекает все цвета из градиента и возвращает их список в порядке следования"""
        try:
            import re
            colors = []
            # Ищем все значения stop с цветами
            stops = re.findall(r'stop:([\d.]+)\s+([^,)]+)', gradient_string)
            
            if stops:
                # Сортируем стопы по их позиции (первое число)
                sorted_stops = sorted(stops, key=lambda x: float(x[0]))
                
                # Извлекаем только цвета в правильном порядке
                colors = [stop[1].strip() for stop in sorted_stops]
                
            return colors if colors else ["#05B8CC"]
            
        except Exception:
            return ["#05B8CC"]

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

    def adjust_gradient_border(self, gradient, only_first_color=True):
        """Создает темную версию градиента для border"""
        colors = self.get_gradient_colors(gradient)
        
        if not colors:
            colors = ["#05B8CC"]
        
        if only_first_color:
            # Один цвет
            return self.adjust_color(colors[0], brightness=-30)
        else:
            # Все цвета с использованием list comprehension
            return [self.adjust_color(color, brightness=-30) for color in colors]


    def adjust_gradient_background(self, gradient):
        """Создает очень темную версию градиента для background"""
        # first_color = self.get_first_gradient_color(gradient)
        colors = self.get_gradient_colors(gradient)
        first_color = colors[0] if colors else "#05B8CC"
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
    
    def get_gradient_color(self):
        if "TitleBar" in self.styles and "border-bottom" in self.styles["TitleBar"]:
            border_value = self.styles["TitleBar"]["border-bottom"]
            color = QColor("#FFFFFF")

            gradient_match = re.search(r"qlineargradient\([^)]+\)", border_value)
            if gradient_match:
                gradient_str = gradient_match.group(0)
                # Ищем ВСЕ цвета градиента
                color_matches = re.findall(r"stop:\d+(?:\.\d+)?\s+(#[0-9a-fA-F]+)", gradient_str)
                if color_matches:
                    # Возвращаем список всех цветов градиента
                    return [QColor(color) for color in color_matches]
            else:
                hex_match = re.search(r"#[0-9a-fA-F]{3,6}", border_value)
                if hex_match:
                    color = QColor(hex_match.group(0))
            return color
    
    def get_transparent_background_from_border(self, opacity=180, darken_factor=130):
        """
        Расширенная версия с затемнением градиента
        :param opacity: прозрачность 0-255
        :param darken_factor: коэффициент затемнения (100 - без изменений, >100 - темнее)
        """
        try:
            if "TitleBar" in self.styles and "border-bottom" in self.styles["TitleBar"]:
                border_value = self.styles["TitleBar"]["border-bottom"]
                
                gradient_match = re.search(r"qlineargradient\([^)]+\)", border_value)
                if gradient_match:
                    gradient_str = gradient_match.group(0)
                    return self._create_transparent_darkened_gradient(gradient_str, opacity, darken_factor)
                else:
                    hex_match = re.search(r"#[0-9a-fA-F]{3,6}", border_value)
                    if hex_match:
                        base_color = QColor(hex_match.group(0))
                        darker_color = base_color.darker(darken_factor)
                        return f"rgba({darker_color.red()}, {darker_color.green()}, {darker_color.blue()}, {opacity})"
                
        except Exception as e:
            debug_logger.error(f"Ошибка получения цвета для фона: {e}")
        
        return f"rgba(30, 30, 30, {opacity})"

    def _create_transparent_darkened_gradient(self, gradient_str, opacity, darken_factor):
        """
        Создает полупрозрачный и затемненный градиент
        """
        try:
            import re
            stops = re.findall(r"stop:([\d.]+)\s+([^,)]+)", gradient_str)
            
            if not stops:
                return f"rgba(30, 30, 30, {opacity})"
            
            new_gradient = "qlineargradient("
            
            # Добавляем координаты градиента
            coords = re.findall(r"(x\d|y\d):([\d.]+)", gradient_str)
            for coord, value in coords:
                new_gradient += f"{coord}:{value}, "
            
            # Добавляем полупрозрачные и затемненные цвета
            for i, (position, color_hex) in enumerate(stops):
                color = QColor(color_hex.strip())
                # Затемняем цвет
                darkened_color = color.darker(darken_factor)
                # Создаем полупрозрачный вариант
                transparent_color = f"rgba({darkened_color.red()}, {darkened_color.green()}, {darkened_color.blue()}, {opacity/255:.2f})"
                new_gradient += f"stop:{position} {transparent_color}"
                if i < len(stops) - 1:
                    new_gradient += ", "
            
            new_gradient += ")"
            return new_gradient
            
        except Exception as e:
            debug_logger.error(f"Ошибка создания прозрачного градиента: {e}")
            first_color_match = re.search(r"stop:[\d.]+\s+([^,)]+)", gradient_str)
            if first_color_match:
                base_color = QColor(first_color_match.group(1).strip())
                darkened_color = base_color.darker(darken_factor)
                return f"rgba({darkened_color.red()}, {darkened_color.green()}, {darkened_color.blue()}, {opacity})"
            return f"rgba(30, 30, 30, {opacity})"
        
    def _parse_color_string(self, color_str):
        """Парсит строку цвета в QColor"""
        try:
            from PySide6.QtGui import QColor
            
            color_str = color_str.strip()
            
            # HEX цвета (#RRGGBB или #RGB)
            if color_str.startswith('#'):
                return QColor(color_str)
            
            # RGB цвета
            rgb_match = re.match(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', color_str)
            if rgb_match:
                return QColor(
                    int(rgb_match.group(1)),
                    int(rgb_match.group(2)), 
                    int(rgb_match.group(3))
                )
            
            # RGBA цвета
            rgba_match = re.match(r'rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)', color_str)
            if rgba_match:
                color = QColor(
                    int(rgba_match.group(1)),
                    int(rgba_match.group(2)),
                    int(rgba_match.group(3))
                )
                color.setAlphaF(float(rgba_match.group(4)))
                return color
            
            # Именованные цвета Qt
            if hasattr(Qt, 'GlobalColor') and hasattr(Qt.GlobalColor, color_str.upper()):
                return QColor(getattr(Qt.GlobalColor, color_str.upper()))
                
            # Попробуем создать QColor напрямую
            color = QColor(color_str)
            if color.isValid():
                return color
                
            return QColor("#000000")  # Fallback цвет
            
        except Exception as e:
            debug_logger.error(f"Ошибка парсинга цвета {color_str}: {e}")
            return QColor("#000000")

    def parse_gradient_from_styles(self, widget_key="TitleBar", css_property="border-bottom"):
        """
        Парсит градиент из CSS стилей и возвращает структуру для применения к SVG
        """
        try:
            if widget_key not in self.styles:
                debug_logger.warning(f"Ключ {widget_key} не найден в стилях")
                return None
                
            style_value = self.styles[widget_key].get(css_property, "")
            if not style_value:
                debug_logger.warning(f"Свойство {css_property} не найдено для {widget_key}")
                return None
            
            # print(f"🔍 Ищем градиент в: {style_value}")  # ДЛЯ ОТЛАДКИ
            
            # Линейный градиент
            linear_match = re.search(r'qlineargradient\s*\(([^)]+)\)', style_value)
            if linear_match:
                gradient_str = linear_match.group(1)
                return self._parse_linear_gradient(gradient_str)
            
            # Радиальный градиент  
            radial_match = re.search(r'qradialgradient\s*\(([^)]+)\)', style_value)
            if radial_match:
                gradient_str = radial_match.group(1)
                return self._parse_radial_gradient(gradient_str)
            
            # Конический градиент
            conical_match = re.search(r'qconicalgradient\s*\(([^)]+)\)', style_value)
            if conical_match:
                gradient_str = conical_match.group(1)
                return self._parse_conical_gradient(gradient_str)
                
            # debug_logger.info(f"Градиент не найден в свойстве {css_property}")
            return None
            
        except Exception as e:
            debug_logger.error(f"Ошибка парсинга градиента из стилей: {e}")
            return None

    def _parse_linear_gradient(self, gradient_params):
        """Парсит параметры линейного градиента"""
        try:
            import re
            from PySide6.QtGui import QColor
                        
            # Парсим координаты
            coords = {}
            coord_pattern = r'(x1|x2|y1|y2):\s*([\d.]+)'
            for match in re.finditer(coord_pattern, gradient_params):
                coords[match.group(1)] = float(match.group(2))
            
            # Парсим цвета - улучшенный паттерн
            colors = []
            stop_pattern = r'stop:\s*([\d.]+)\s+([^,)]+)'
            for match in re.finditer(stop_pattern, gradient_params):
                position = float(match.group(1))
                color_str = match.group(2).strip()
                                
                color = self._parse_color_string(color_str)
                if color:
                    colors.append((position, color))
            
            if not colors:
                debug_logger.error("❌ Не найдено цветов в градиенте")
                return None
                
            # Создаем структуру градиента
            gradient_data = {
                'type': 'linear',
                'colors': colors
            }
            
            # Добавляем направление если есть координаты
            if all(key in coords for key in ['x1', 'y1', 'x2', 'y2']):
                gradient_data['direction'] = (
                    coords['x1'], coords['y1'], 
                    coords['x2'], coords['y2']
                )
            else:
                # Используем угол по умолчанию (слева направо)
                gradient_data['direction'] = 0
                    
            return gradient_data
            
        except Exception as e:
            debug_logger.error(f"Ошибка парсинга линейного градиента: {e}")
            return None

    # Добавим также методы для других типов градиентов
    def _parse_radial_gradient(self, gradient_params):
        """Парсит параметры радиального градиента"""
        try:
            import re
            from PySide6.QtGui import QColor
                        
            # Парсим центр и радиус
            center_x = center_y = 0.5
            radius = 0.5
            
            center_pattern = r'cx:\s*([\d.]+).*?cy:\s*([\d.]+)'
            center_match = re.search(center_pattern, gradient_params)
            if center_match:
                center_x = float(center_match.group(1))
                center_y = float(center_match.group(2))
                
            radius_pattern = r'radius:\s*([\d.]+)'
            radius_match = re.search(radius_pattern, gradient_params)
            if radius_match:
                radius = float(radius_match.group(1))
            
            # Парсим цвета
            colors = []
            stop_pattern = r'stop:\s*([\d.]+)\s+([^,)]+)'
            for match in re.finditer(stop_pattern, gradient_params):
                position = float(match.group(1))
                color_str = match.group(2).strip()
                
                color = self._parse_color_string(color_str)
                if color:
                    colors.append((position, color))
            
            if not colors:
                return None
                
            return {
                'type': 'radial',
                'colors': colors,
                'center': (center_x, center_y),
                'radius': radius
            }
            
        except Exception as e:
            debug_logger.error(f"Ошибка парсинга радиального градиента: {e}")
            return None

    def _parse_conical_gradient(self, gradient_params):
        """Парсит параметры конического градиента"""
        try:
            import re
            from PySide6.QtGui import QColor
                        
            # Парсим центр и угол
            center_x = center_y = 0.5
            angle = 0
            
            center_pattern = r'cx:\s*([\d.]+).*?cy:\s*([\d.]+)'
            center_match = re.search(center_pattern, gradient_params)
            if center_match:
                center_x = float(center_match.group(1))
                center_y = float(center_match.group(2))
                
            angle_pattern = r'angle:\s*([\d.-]+)'
            angle_match = re.search(angle_pattern, gradient_params)
            if angle_match:
                angle = float(angle_match.group(1))
            
            # Парсим цвета
            colors = []
            stop_pattern = r'stop:\s*([\d.]+)\s+([^,)]+)'
            for match in re.finditer(stop_pattern, gradient_params):
                position = float(match.group(1))
                color_str = match.group(2).strip()
                
                color = self._parse_color_string(color_str)
                if color:
                    colors.append((position, color))
            
            if not colors:
                return None
                
            return {
                'type': 'conical',
                'colors': colors,
                'center': (center_x, center_y),
                'angle': angle
            }
            
        except Exception as e:
            debug_logger.error(f"Ошибка парсинга конического градиента: {e}")
            return None
