import sys
import math
import random
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QPoint, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QPixmap, QRadialGradient

import random
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import QPainter, QColor, QBrush, QPainterPath

class FrostedWidget(QWidget):
    def __init__(self, content_widget: QWidget, frost_width=10, parent=None):
        super().__init__(parent)
        self._border_width = frost_width
        self.content = content_widget
        self.content.setParent(self)
        self.content.resize(self.size())
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Кэш для инея
        self._frost_cache = None
        self._cached_size = QSize(-1, -1)

    def resizeEvent(self, event):
        self.content.resize(self.size())
        # Сбрасываем кэш при изменении размера
        self._frost_cache = None
        self._cached_size = QSize(-1, -1)
        super().resizeEvent(event)

    def paintEvent(self, event):
        # Используем кэш, если он актуален
        current_size = self.size()
        if self._frost_cache is None or self._cached_size != current_size:
            self._render_frost_to_cache()
        
        # Рисуем кэш
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawPixmap(0, 0, self._frost_cache)

    def _render_frost_to_cache(self):
        """Отрисовывает иней в QPixmap один раз."""
        size = self.size()
        self._frost_cache = QPixmap(size)
        self._frost_cache.fill(Qt.transparent)  # полностью прозрачный

        painter = QPainter(self._frost_cache)
        painter.setRenderHint(QPainter.Antialiasing)
        self.draw_frost_border(painter)
        painter.end()

        self._cached_size = size

    def draw_frost_border(self, painter):
        border_width = self._border_width
        density = 0.7
        min_size = 7
        max_size = 10
        grid_size = min_size // 2

        random.seed(123)  # для воспроизводимости

        left_bound = border_width
        right_bound = self.width() - border_width
        top_bound = border_width
        bottom_bound = self.height() - border_width

        for x in range(-grid_size, self.width() + grid_size, grid_size):
            for y in range(-grid_size, self.height() + grid_size, grid_size):
                in_left = x <= left_bound
                in_right = x >= right_bound
                in_top = y <= top_bound
                in_bottom = y >= bottom_bound

                if (in_left or in_right or in_top or in_bottom) and random.random() < density:
                    size = random.randint(min_size, max_size)
                    crystal_type = random.randint(1, 8)
                    offset_x = random.randint(-grid_size//2, grid_size//2)
                    offset_y = random.randint(-grid_size//2, grid_size//2)
                    center_x = x + offset_x
                    center_y = y + offset_y

                    # Ограничиваем центр, чтобы кристалл не вылезал за border_width
                    if in_left:
                        center_x = min(center_x, border_width + size // 2)
                    elif in_right:
                        center_x = max(center_x, self.width() - border_width - size // 2)
                    if in_top:
                        center_y = min(center_y, border_width + size // 2)
                    elif in_bottom:
                        center_y = max(center_y, self.height() - border_width - size // 2)

                    self.draw_advanced_crystal(painter, center_x, center_y, size, crystal_type)
                    
    def draw_advanced_crystal(self, painter, x, y, size, crystal_type):
        """Рисуем различные типы сложных кристаллов"""
        
        # Общие настройки
        alpha = random.randint(80, 180)
        color = QColor(200, 220, 255, alpha)
        painter.setPen(QPen(color, 1))
        painter.setBrush(QBrush(QColor(200, 220, 255, alpha // 3)))
        
        center_x = x + size // 2
        center_y = y + size // 2
        base_radius = size // 3
        
        if crystal_type == 1:
            self.draw_star_crystal(painter, center_x, center_y, base_radius)
        elif crystal_type == 2:
            self.draw_fern_crystal(painter, center_x, center_y, base_radius)
        elif crystal_type == 3:
            self.draw_dendrite_crystal(painter, center_x, center_y, base_radius)
        elif crystal_type == 4:
            self.draw_hexagonal_crystal(painter, center_x, center_y, base_radius)
        elif crystal_type == 5:
            self.draw_needle_crystal(painter, center_x, center_y, base_radius)
        elif crystal_type == 6:
            self.draw_plate_crystal(painter, center_x, center_y, base_radius)
        elif crystal_type == 7:
            self.draw_columnar_crystal(painter, center_x, center_y, base_radius)
        else:
            self.draw_complex_star_crystal(painter, center_x, center_y, base_radius)
    
    def draw_star_crystal(self, painter, cx, cy, radius):
        """Звездообразный кристалл с 6 лучами"""
        points = []
        for i in range(12):  # 12 точек для 6 лучей
            angle = math.pi * i / 6
            if i % 2 == 0:
                r = radius * 1.5  # Длинные лучи
            else:
                r = radius * 0.5  # Короткие лучи
            
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            points.append(QPoint(int(px), int(py)))
        
        painter.drawPolygon(points)
    
    def draw_fern_crystal(self, painter, cx, cy, radius):
        """Папоротниковый дендритный кристалл"""
        path = QPainterPath()
        path.moveTo(cx, cy - radius)
        
        # Основные ветви
        for angle in [0, 72, 144, 216, 288]:
            rad_angle = math.radians(angle)
            end_x = cx + radius * 0.8 * math.cos(rad_angle)
            end_y = cy + radius * 0.8 * math.sin(rad_angle)
            
            path.moveTo(cx, cy)
            path.lineTo(end_x, end_y)
            
            # Вторичные ветви
            for sub_angle in [angle - 20, angle + 20]:
                sub_rad = math.radians(sub_angle)
                sub_x = end_x + radius * 0.4 * math.cos(sub_rad)
                sub_y = end_y + radius * 0.4 * math.sin(sub_rad)
                path.moveTo(end_x, end_y)
                path.lineTo(sub_x, sub_y)
        
        painter.drawPath(path)
    
    def draw_dendrite_crystal(self, painter, cx, cy, radius):
        """Сложный дендритный кристалл"""
        path = QPainterPath()
        
        # Основные 6 направлений
        for i in range(6):
            angle = math.pi * i / 3
            self.draw_dendrite_branch(path, cx, cy, angle, radius, 3)
        
        painter.drawPath(path)
    
    def draw_dendrite_branch(self, path, start_x, start_y, angle, length, depth):
        """Рекурсивное рисование ветвей дендрита"""
        if depth == 0:
            return
        
        end_x = start_x + length * math.cos(angle)
        end_y = start_y + length * math.sin(angle)
        
        path.moveTo(start_x, start_y)
        path.lineTo(end_x, end_y)
        
        # Рекурсивно рисуем подветви
        if depth > 1:
            new_length = length * 0.6
            for branch_angle in [angle - math.pi/4, angle + math.pi/4]:
                self.draw_dendrite_branch(path, end_x, end_y, branch_angle, new_length, depth - 1)
    
    def draw_hexagonal_crystal(self, painter, cx, cy, radius):
        """Сложный гексагональный кристалл с внутренним узором"""
        # Внешний шестиугольник
        outer_points = []
        for i in range(6):
            angle = 2 * math.pi * i / 6
            px = cx + radius * 1.2 * math.cos(angle)
            py = cy + radius * 1.2 * math.sin(angle)
            outer_points.append(QPoint(int(px), int(py)))
        
        painter.drawPolygon(outer_points)
        
        # Внутренний шестиугольник
        inner_points = []
        for i in range(6):
            angle = 2 * math.pi * i / 6
            px = cx + radius * 0.6 * math.cos(angle)
            py = cy + radius * 0.6 * math.sin(angle)
            inner_points.append(QPoint(int(px), int(py)))
        
        painter.drawPolygon(inner_points)
        
        # Соединяющие линии
        for i in range(6):
            painter.drawLine(outer_points[i], inner_points[i])
            painter.drawLine(inner_points[i], outer_points[(i + 1) % 6])
    
    def draw_needle_crystal(self, painter, cx, cy, radius):
        """Игольчатый кристалл"""
        path = QPainterPath()
        
        # Длинные тонкие иглы в 4 направлениях
        for angle in [0, math.pi/2, math.pi, 3*math.pi/2]:
            end_x = cx + radius * 2 * math.cos(angle)
            end_y = cy + radius * 2 * math.sin(angle)
            
            path.moveTo(cx, cy)
            path.lineTo(end_x, end_y)
            
            # Короткие боковые иглы
            for side_angle in [angle - math.pi/6, angle + math.pi/6]:
                side_x = cx + radius * 0.8 * math.cos(side_angle)
                side_y = cy + radius * 0.8 * math.sin(side_angle)
                path.moveTo(cx, cy)
                path.lineTo(side_x, side_y)
        
        painter.drawPath(path)
    
    def draw_plate_crystal(self, painter, cx, cy, radius):
        """Пластинчатый кристалл с сложным узором"""
        # Внешний круг
        painter.drawEllipse(QPoint(cx, cy), radius, radius)
        
        # Внутренние концентрические круги
        painter.drawEllipse(QPoint(cx, cy), int(radius * 0.7), int(radius * 0.7))
        painter.drawEllipse(QPoint(cx, cy), int(radius * 0.4), int(radius * 0.4))
        
        # Радиальные линии
        for i in range(12):
            angle = math.pi * i / 6
            end_x = cx + radius * math.cos(angle)
            end_y = cy + radius * math.sin(angle)
            painter.drawLine(cx, cy, int(end_x), int(end_y))
    
    def draw_columnar_crystal(self, painter, cx, cy, radius):
        """Столбчатый кристалл с шестиугольными торцами"""
        # Основной столбик
        rect_width = radius * 0.8
        rect_height = radius * 1.5
        painter.drawRect(int(cx - rect_width/2), int(cy - rect_height/2), 
                        int(rect_width), int(rect_height))
        
        # Шестиугольные торцы
        for y_offset in [-rect_height/2, rect_height/2]:
            hex_points = []
            for i in range(6):
                angle = 2 * math.pi * i / 6
                px = cx + rect_width * 0.6 * math.cos(angle)
                py = cy + y_offset + rect_width * 0.3 * math.sin(angle)
                hex_points.append(QPoint(int(px), int(py)))
            painter.drawPolygon(hex_points)
    
    def draw_complex_star_crystal(self, painter, cx, cy, radius):
        """Очень сложный звездчатый кристалл"""
        path = QPainterPath()
        
        # Многоуровневая звезда
        levels = 3
        for level in range(levels):
            level_radius = radius * (1 - level * 0.2)
            points_count = 6 + level * 2  # Увеличиваем количество лучей
            
            points = []
            for i in range(points_count * 2):
                angle = math.pi * i / points_count
                if i % 2 == 0:
                    r = level_radius * 1.3
                else:
                    r = level_radius * 0.7
                
                px = cx + r * math.cos(angle)
                py = cy + r * math.sin(angle)
                points.append(QPoint(int(px), int(py)))
            
            if level == 0:
                path.moveTo(points[0])
                for point in points[1:]:
                    path.lineTo(point)
                path.closeSubpath()
            else:
                for i in range(len(points)):
                    next_i = (i + 1) % len(points)
                    path.moveTo(points[i])
                    path.lineTo(points[next_i])
        
        painter.drawPath(path)
      
#################################  #################################  #################################  

class SnowOverlay(QWidget):
    def __init__(self,
                parent=None,
                snowflake_count=80,
                fall_speed=0.8,
                flake_size_min=2,
                flake_size_max=6,
                change_interval_sec=60,
                change_probability=0.5,
                initial_preset_index=0,
                snow_color="#FFFFFF",
                preset_type="main_window"):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setWindowFlags(Qt.Widget)
        
        # Цвет снежинок
        self.snow_color = QColor(snow_color)  # Конвертируем hex в QColor
        self.snow_color.setAlpha(150)  # Прозрачность по умолчанию
        
        # Параметры интерполяции
        self.interpolate_duration_sec = 3.0  # секунды на переход
        self.interpolate_steps = 0
        self.interpolate_max_steps = 1
        
        # Инициализируем from_params с текущими значениями
        self.from_params = {
            "count": snowflake_count,
            "speed": fall_speed,
            "size_min": flake_size_min,
            "size_max": flake_size_max,
        }
        self.to_params = self.from_params.copy()
        
        # Пресеты
        self.preset_type = preset_type
        if self.preset_type == "main_window":
            self.presets = [
                {"count": 20, "speed": 0.4, "size_min": 0.5, "size_max": 4.0, "weight": 100},
                {"count": 50, "speed": 0.6, "size_min": 1.5, "size_max": 6.0, "weight": 70},
                {"count": 300, "speed": 0.8, "size_min": 1.0, "size_max": 5.5, "weight": 50},
                {"count": 400, "speed": 0.6, "size_min": 1.0, "size_max": 4.0, "weight": 30},
                {"count": 800, "speed": 4.0, "size_min": 1.0, "size_max": 5.0, "weight": 10},
            ]
        else:
            self.presets = [
                {"count": 20, "speed": 0.4, "size_min": 1.0, "size_max": 3.0, "weight": 70},
                {"count": 50, "speed": 0.3, "size_min": 1.0, "size_max": 4.0, "weight": 30},
                {"count": 10, "speed": 0.4, "size_min": 1.0, "size_max": 3.5, "weight": 150},
                {"count": 200, "speed": 4.4, "size_min": 1.0, "size_max": 4.0, "weight": 1},
            ]
        
        self.change_interval_ms = int(change_interval_sec * 1000)
        self.change_probability = change_probability
        self.current_preset_index = initial_preset_index

        # Параметры снега
        self.snowflake_count = snowflake_count
        self.fall_speed = fall_speed
        self.flake_size_min = flake_size_min
        self.flake_size_max = flake_size_max

        # Состояние снежинок: (x, y, size, speed_factor, sway_offset)
        self.flakes = []
        self._init_snowflakes()

        # Таймер анимации
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_snow)
        self.timer.start(20)  # 50 FPS
        
        self.preset_timer = QTimer(self)
        self.preset_timer.timeout.connect(self._try_change_preset)
        self.preset_timer.start(self.change_interval_ms)

        # Инициализация первого пресета
        self._apply_preset(initial_preset_index)
    
    def _choose_preset(self):
        """Выбирает пресет на основе весов"""
        # Исключаем текущий пресет из выбора
        available_presets = [p for i, p in enumerate(self.presets) 
                           if i != self.current_preset_index]
        
        if not available_presets:
            return random.choice(self.presets)
        
        # Создаем список весов для доступных пресетов
        weights = [p["weight"] for p in available_presets]
        
        # Выбираем пресет на основе весов
        chosen_preset = random.choices(available_presets, weights=weights, k=1)[0]
        
        # Обновляем текущий индекс
        self.current_preset_index = self.presets.index(chosen_preset)
        
        return chosen_preset
        
    def _start_interpolation(self, to_preset):
        # Сохраняем текущие параметры как "откуда"
        self.from_params = {
            "count": self.snowflake_count,
            "speed": self.fall_speed,
            "size_min": self.flake_size_min,
            "size_max": self.flake_size_max,
        }
        # Целевые параметры
        self.to_params = to_preset.copy()

        # Рассчитываем количество шагов
        self.interpolate_max_steps = max(1, int(self.interpolate_duration_sec * 1000 / 20))  # 50 мс = 20 FPS
        self.interpolate_steps = 0

    def _apply_preset(self, index):
        preset = self.presets[index]
        self.snowflake_count = preset["count"]
        self.fall_speed = preset["speed"]
        self.flake_size_min = preset["size_min"]
        self.flake_size_max = preset["size_max"]
        self._init_snowflakes()
    
    def _update_interpolated_params(self):
        if self.interpolate_steps > self.interpolate_max_steps:
            # Завершаем интерполяцию
            self.snowflake_count = self.to_params["count"]
            self._adjust_flakes_count()  # Плавная корректировка количества
            return

        t = self.interpolate_steps / self.interpolate_max_steps
        # Используем ease-функцию для более плавного перехода
        t_smooth = self._ease_in_out(t)

        def lerp(a, b, t):
            return a + (b - a) * t

        # Интерполируем параметры
        new_count = int(lerp(self.from_params["count"], self.to_params["count"], t_smooth))
        self.fall_speed = lerp(self.from_params["speed"], self.to_params["speed"], t_smooth)
        self.flake_size_min = lerp(self.from_params["size_min"], self.to_params["size_min"], t_smooth)
        self.flake_size_max = lerp(self.from_params["size_max"], self.to_params["size_max"], t_smooth)

        # ПЛАВНО изменяем количество снежинок
        self._adjust_flakes_count(new_count)
        
        # Плавно обновляем размеры существующих снежинок
        self._update_existing_flakes_sizes()

        self.interpolate_steps += 1

    def _ease_in_out(self, t):
        """Функция плавности для более естественных переходов"""
        return t * t * (3 - 2 * t)

    def _adjust_flakes_count(self, target_count=None):
        """Плавно регулирует количество снежинок"""
        if target_count is None:
            target_count = self.snowflake_count
        
        current_count = len(self.flakes)
        
        if target_count > current_count:
            # Добавляем новые снежинки постепенно
            to_add = min(target_count - current_count, 5)  # Не более 5 за кадр
            self._add_flakes(to_add)
        elif target_count < current_count:
            # Удаляем снежинки постепенно (те, что далеко за пределами)
            to_remove = min(current_count - target_count, 3)  # Не более 3 за кадр
            self._remove_distant_flakes(to_remove)

    def _add_flakes(self, count):
        """Добавляет новые снежинки"""
        w, h = self.width(), self.height()
        for _ in range(count):
            x = random.uniform(0, w)
            y = random.uniform(-h, -5)  # Появляются сверху
            size = random.uniform(self.flake_size_min, self.flake_size_max)
            speed_factor = random.uniform(0.7, 1.3)
            sway_offset = random.uniform(0, 1000)
            self.flakes.append([x, y, size, speed_factor, sway_offset])

    def _remove_distant_flakes(self, count):
        """Удаляет самые дальние снежинки"""
        if not self.flakes:
            return
        
        # Сортируем по удаленности от видимой области (снизу)
        self.flakes.sort(key=lambda flake: flake[1], reverse=True)
        
        # Удаляем самые нижние
        removed = 0
        for i in range(len(self.flakes) - 1, -1, -1):
            if removed >= count:
                break
            if self.flakes[i][1] > self.height() + 10:  # Далеко за пределами
                self.flakes.pop(i)
                removed += 1

    def _update_existing_flakes_sizes(self):
        """Плавно обновляет размеры существующих снежинок"""
        for flake in self.flakes:
            # Плавно изменяем размер к целевому диапазону
            current_size = flake[2]
            target_size = random.uniform(self.flake_size_min, self.flake_size_max)
            
            # Медленная интерполяция размера (10% за кадр)
            new_size = current_size + (target_size - current_size) * 0.1
            flake[2] = max(self.flake_size_min, min(self.flake_size_max, new_size))

    def _try_change_preset(self):
        if random.random() >= self.change_probability:
            return

        # Проверяем, не идет ли уже интерполяция
        if self.interpolate_steps <= self.interpolate_max_steps:
            return

        new_preset = self._choose_preset()
        self._start_interpolation(new_preset)

    def _init_snowflakes(self):
        self.flakes = []
        w, h = self.width(), self.height()
        for _ in range(self.snowflake_count):
            x = random.uniform(0, w)
            y = random.uniform(-h, h)  # начинают за пределами сверху
            size = random.uniform(self.flake_size_min, self.flake_size_max)
            speed_factor = random.uniform(0.7, 1.3)
            sway_offset = random.uniform(0, 1000)  # фаза для колебаний
            self.flakes.append([x, y, size, speed_factor, sway_offset])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._init_snowflakes()  # пересоздаём при изменении размера

    def _update_snow(self):
        # Обновляем интерполяцию если она активна
        if self.interpolate_steps <= self.interpolate_max_steps:
            self._update_interpolated_params()
        
        h = self.height()
        w = self.width()
        for flake in self.flakes:
            x, y, size, speed_factor, sway_offset = flake
            # Падение
            y += self.fall_speed * speed_factor
            # Лёгкое колебание (ветер)
            x += math.sin(y * 0.01 + sway_offset) * 0.3
            # Сброс, если ушла вниз
            if y > h + 20:
                y = -10
                x = random.uniform(0, w)
            flake[0], flake[1] = x, y
        
        self.update()  # запрос на перерисовку

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(self.snow_color))
        painter.setPen(Qt.NoPen)

        for x, y, size, _, _ in self.flakes:
            # Рисуем простую круглую снежинку
            painter.drawEllipse(QPointF(x, y), size, size)

    def setSnowParameters(self, count=None, speed=None, size_min=None, size_max=None):
        """Динамическая настройка параметров снега."""
        if count is not None:
            self.snowflake_count = count
        if speed is not None:
            self.fall_speed = speed
        if size_min is not None:
            self.flake_size_min = size_min
        if size_max is not None:
            self.flake_size_max = size_max
        self._init_snowflakes()
        
    def setSnowColor(self, color, alpha=None, white_balance=100):
        """Установка цвета снежинок с балансом белого"""
        if isinstance(color, str):
            # Если передан hex-строка
            base_color = QColor(color)
        elif isinstance(color, QColor):
            # Если передан QColor
            base_color = color
        elif isinstance(color, (list, tuple)):
            # Если передан RGB/RGBA список
            if len(color) == 3:
                base_color = QColor(*color)
            elif len(color) == 4:
                base_color = QColor(*color)
        
        # Применяем баланс белого (0-100%)
        # 0% = полностью переданный цвет, 100% = полностью белый
        if white_balance != 0:
            self.snow_color = self._blend_with_white(base_color, white_balance)
        else:
            self.snow_color = base_color
        
        # Устанавливаем прозрачность
        if alpha is not None:
            self.snow_color.setAlpha(alpha)
        
        self.update()  # Перерисовываем
        
    def _blend_with_white(self, color, white_balance_percent):
        """Смешивает цвет с белым"""
        # Ограничиваем диапазон
        white_balance_percent = max(0, min(100, white_balance_percent))
        
        # Конвертируем в коэффициент (0.0 - 1.0)
        t = white_balance_percent / 100.0
        
        # Белый цвет
        white = QColor(255, 255, 255)
        
        # Интерполируем между исходным цветом и белым
        r = int(color.red() + (white.red() - color.red()) * t)
        g = int(color.green() + (white.green() - color.green()) * t)
        b = int(color.blue() + (white.blue() - color.blue()) * t)
        a = color.alpha()  # Сохраняем альфа-канал
        
        return QColor(r, g, b, a)


class GarlandDecorator:
    def __init__(self, target_widget, light_count=15, light_size=8, width=820):
        self.target_widget = target_widget
        self.light_count = light_count
        self.light_size = light_size
        self.width = width
        self.lights = []
        self.visible = True
        self.color_offset = 0
        self.available_modes = ["wave", "breathing", "chase", "smash", "snake"]
        self.random_mode_timer = 0
        self.random_mode_interval = 60000  # 60 секунд в миллисекундах
        
        # Настройки анимации
        self.animation_mode = "random"
        self.animation_speed = 50  # ms
        self.animation_time = 0
        
        # Цветовые схемы
        self.color_palettes = {
            "classic": ['#ff0000', '#00ff00', "#0151ff", "#ff00f2", "#fbff00", "#01ffd5"],
            "warm": ['#ff6b6b', '#ffa726', '#ffca28', '#ffee58', '#fff176'],
            "cool": ['#42a5f5', '#5c6bc0', '#7e57c2', '#ab47bc', '#ec407a'],
            "rainbow": ['#ff0000', '#ff7f00', '#ffff00', '#00ff00', "#00d9ff", "#0548FF", '#9400d3']
        }
        self.current_palette = "rainbow"
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(self.animation_speed)
        
        self.original_paint_event = target_widget.paintEvent
        target_widget.paintEvent = self.custom_paint_event
        self.generate_lights()
    
    def set_color_palette(self, palette_name):
        """Смена цветовой палитры"""
        if palette_name in self.color_palettes:
            self.current_palette = palette_name
            colors = self.color_palettes[palette_name]
            for i, light in enumerate(self.lights):
                light['base_color'] = QColor(random.choice(colors))
    
    def show(self):
        """Показывает гирлянду"""
        self.visible = True
        self.timer.start(self.animation_speed)
        self.target_widget.update()
    
    def hide(self):
        """Скрывает гирлянду"""
        self.visible = False
        self.timer.stop()
        self.target_widget.update()
    
    def isVisible(self):
        """Проверяет видимость гирлянды"""
        return self.visible
    
    def toggle(self):
        """Переключает видимость гирлянды"""
        if self.visible:
            self.hide()
        else:
            self.show()
    
    def generate_lights(self):
        self.lights = []
        colors = self.color_palettes[self.current_palette]

        padding = 10
        
        for i in range(self.light_count):
            # Расчет позиции с учетом отступов
            available_width = self.width - (2 * padding)
            x = padding + (available_width * i) / max(1, self.light_count - 1)
            
            wave_height = 15
            y_offset = (math.sin(i * 0.8) - 1) * (wave_height / 2)
            
            base_color = QColor(random.choice(colors))
            self.lights.append({
                'x': x, 
                'y_offset': y_offset,
                'base_color': base_color, 
                'brightness': 0,
                'size': self.light_size,
                'phase': random.uniform(0, 2 * math.pi)
            })
    
    def update_animation(self):
        """Обновляет анимацию с учетом случайного режима"""
        self.animation_time += self.animation_speed / 1000.0
        
        # Обновляем таймер случайного режима
        if self.animation_mode == "random":
            self.random_mode_timer += self.animation_speed
            if self.random_mode_timer >= self.random_mode_interval:
                self._switch_random_mode()
                self.random_mode_timer = 0
        
        # Выполняем текущую анимацию
        if self.animation_mode == "snake":
            self._snake_animation()
        elif self.animation_mode == "wave":
            self._wave_animation()
        elif self.animation_mode == "breathing":
            self._breathing_animation()
        elif self.animation_mode == "random":
            # Для random выполняем текущий выбранный режим
            current_mode = getattr(self, '_current_random_mode', 'wave')
            if current_mode == "snake":
                self._snake_animation()
            elif current_mode == "wave":
                self._wave_animation()
            elif current_mode == "breathing":
                self._breathing_animation()
            elif current_mode == "chase":
                self._chase_animation()
            elif current_mode == "smash":
                self._smash_animation()
        elif self.animation_mode == "chase":
            self._chase_animation()
        elif self.animation_mode == "smash":
            self._smash_animation()
        
        self.target_widget.update()
        
    def _switch_random_mode(self):
        """Переключает на случайный режим"""
        # Исключаем текущий режим чтобы не повторяться подряд
        current_mode = getattr(self, '_current_random_mode', None)
        available_modes = [mode for mode in self.available_modes if mode != current_mode]
        
        if not available_modes:  # Если все режимы исключены, используем все
            available_modes = self.available_modes
        
        new_mode = random.choice(available_modes)
        self._current_random_mode = new_mode
        
        # Сбрасываем состояние анимации для нового режима
        if hasattr(self, 'color_offset'):
            self.color_offset = random.random()
        if hasattr(self, '_chase_active'):
            self._chase_active = False
        if hasattr(self, '_breath_initialized'):
            self._breath_initialized = False
            
    def next_animation(self):
        """Переключает на следующую анимацию вручную"""
        # Если сейчас режим random, переключаем внутри random
        if self.animation_mode == "random":
            self._switch_random_mode()
            self.random_mode_timer = 0  # Сбрасываем таймер
            return self._current_random_mode
        else:
            # Если не random, переключаем основной режим
            modes_cycle = ["snake", "wave", "breathing", "chase", "smash", "random"]
            
            if not hasattr(self, '_current_mode_index'):
                self._current_mode_index = modes_cycle.index(self.animation_mode)
            
            self._current_mode_index = (self._current_mode_index + 1) % len(modes_cycle)
            next_mode = modes_cycle[self._current_mode_index]
            
            self.set_animation_mode(next_mode)
            return next_mode

    def _switch_random_mode(self):
        """Переключает на следующий режим в random (по порядку)"""
        if not hasattr(self, '_random_mode_index'):
            self._random_mode_index = 0
        
        # Переходим к следующему режиму по порядку
        self._random_mode_index = (self._random_mode_index + 1) % len(self.available_modes)
        self._current_random_mode = self.available_modes[self._random_mode_index]
        
        # Сбрасываем состояние анимации для нового режима
        if hasattr(self, 'color_offset'):
            self.color_offset = random.random()
        if hasattr(self, '_chase_active'):
            self._chase_active = False
        if hasattr(self, '_breath_initialized'):
            self._breath_initialized = False

    def set_animation_mode(self, mode):
        """Установка режима анимации"""
        if mode in ["snake", "wave", "breathing", "random", "chase", "smash"]:
            self.animation_mode = mode
            self.animation_time = 0
            self.random_mode_timer = 0  # Всегда сбрасываем таймер при смене режима
            
            # Обновляем индекс для ручного переключения
            modes_cycle = ["snake", "wave", "breathing", "chase", "smash", "random"]
            if mode in modes_cycle:
                self._current_mode_index = modes_cycle.index(mode)
            
            # При переключении на random инициализируем первый режим
            if mode == "random":
                if not hasattr(self, '_random_mode_index'):
                    self._random_mode_index = 0
                self._current_random_mode = self.available_modes[self._random_mode_index]
    
    def _snake_animation(self):
        """Змейка - цвета бегут по гирлянде"""
        self.color_offset = (self.color_offset + 0.6) % self.light_count  # ← 0.2 вместо 1
        
        colors = self.color_palettes[self.current_palette]
        
        for i, light in enumerate(self.lights):
            # Вычисляем позицию цвета в змейке
            color_index = (i - int(self.color_offset)) % len(colors)  # ← округляем до целого
            light['base_color'] = QColor(colors[color_index])
            light['brightness'] = 255
            
    def _smash_animation(self):
        """Smash - две волны сталкиваются в центре"""
        self.color_offset = (self.color_offset + 0.009) % 1
        
        colors = self.color_palettes[self.current_palette]
        
        for i, light in enumerate(self.lights):
            # Нормализованная позиция лампочки (0-1)
            pos = i / max(1, self.light_count - 1)
            
            # Левая волна (от 0 до 1, где 1 - фронт волны)
            left_wave = (pos - self.color_offset) % 1
            # Правая волна (от 1 до 0, где 0 - фронт волны)  
            right_wave = (1 - pos - self.color_offset) % 1
            
            # Определяем какая волна активна для этой лампочки
            # Берем ту, что ближе к своему фронту
            left_strength = 1.0 - left_wave  # Сильнее ближе к фронту
            right_strength = 1.0 - right_wave  # Сильнее ближе к фронту
            
            if left_strength > right_strength:
                # Доминирует левая волна
                wave_pos = left_wave
            else:
                # Доминирует правая волна
                wave_pos = right_wave
            
            # Получаем цвет из волны
            segment = wave_pos * len(colors)
            color_index = int(segment) % len(colors)
            next_color_index = (color_index + 1) % len(colors)
            
            blend = segment - int(segment)
            current_color = QColor(colors[color_index])
            next_color = QColor(colors[next_color_index])
            
            mixed_color = QColor(
                int(current_color.red() * (1 - blend) + next_color.red() * blend),
                int(current_color.green() * (1 - blend) + next_color.green() * blend),
                int(current_color.blue() * (1 - blend) + next_color.blue() * blend)
            )
            
            light['base_color'] = mixed_color
            light['brightness'] = 255

    def _breathing_animation(self):
        """Пульсация - градиент меняется при каждом цикле"""
        breath_speed = 1
        breath = (math.sin(self.animation_time * breath_speed) + 1) / 2
        
        # Инициализация при первом запуске
        if not hasattr(self, '_breath_initialized'):
            self._generate_breath_gradient()
            self._apply_breath_gradient()
            self._breath_initialized = True
        
        # Генерируем новый градиент при начале цикла (минимальная яркость)
        if breath < 0.05:
            if not hasattr(self, '_last_breath_low') or not self._last_breath_low:
                self._generate_breath_gradient()
                self._apply_breath_gradient()
                self._last_breath_low = True
        else:
            self._last_breath_low = False
        
        # Применяем яркость
        for light in self.lights:
            light['brightness'] = int(breath * 200 + 55)

    def _generate_breath_gradient(self):
        """Генерирует случайный градиент"""
        colors = self.color_palettes[self.current_palette]
        
        self.breath_color_start = QColor(random.choice(colors))
        self.breath_color_end = QColor(random.choice(colors))
        
        # Убедимся что цвета разные
        while self.breath_color_end == self.breath_color_start:
            self.breath_color_end = QColor(random.choice(colors))

    def _apply_breath_gradient(self):
        """Применяет градиент ко всем лампочкам"""
        if hasattr(self, 'breath_color_start') and hasattr(self, 'breath_color_end'):
            for i, light in enumerate(self.lights):
                # Простой градиент от начала к концу
                blend = i / max(1, self.light_count - 1)
                mixed_color = QColor(
                    int(self.breath_color_start.red() * (1 - blend) + self.breath_color_end.red() * blend),
                    int(self.breath_color_start.green() * (1 - blend) + self.breath_color_end.green() * blend),
                    int(self.breath_color_start.blue() * (1 - blend) + self.breath_color_end.blue() * blend)
                )
                light['base_color'] = mixed_color

    def _wave_animation(self):
        """Волна - плавный градиент через все цвета палитры с зацикленностью"""
        self.color_offset = (self.color_offset + 0.008) % 1
        
        colors = self.color_palettes[self.current_palette]
        
        for i, light in enumerate(self.lights):
            # Позиция в полном цикле градиента
            pos = (i / self.light_count - self.color_offset) % 1
            
            # Находим между какими цветами находимся (с зацикленностью)
            segment = pos * len(colors)  # Умножаем на длину, а не на (len-1)
            color_index = int(segment) % len(colors)
            next_color_index = (color_index + 1) % len(colors)  # Зацикливаем
            
            blend = segment - int(segment)
            current_color = QColor(colors[color_index])
            next_color = QColor(colors[next_color_index])
            
            mixed_color = QColor(
                int(current_color.red() * (1 - blend) + next_color.red() * blend),
                int(current_color.green() * (1 - blend) + next_color.green() * blend),
                int(current_color.blue() * (1 - blend) + next_color.blue() * blend)
            )
            
            light['base_color'] = mixed_color
            light['brightness'] = 255

    def _chase_animation(self):
        """Chase - с улучшенным избеганием повторяющихся зон"""
        if not hasattr(self, '_chase_active'):
            self._chase_active = False
            self._chase_progress = 0
            self._chase_speed = 0.02
            self._chase_cooldown_zones = []  # Зоны в коуддауне
            self._chase_frame_counter = 0
        
        segment_length = 25
        
        # Сбрасываем лампочки
        for light in self.lights:
            light['brightness'] = 0
        
        self._chase_frame_counter += 1
        
        # Обновляем коуддаун зон
        self._chase_cooldown_zones = [zone for zone in self._chase_cooldown_zones 
                                    if zone['frames_left'] > 0]
        for zone in self._chase_cooldown_zones:
            zone['frames_left'] -= 1
        
        # Запуск нового сегмента
        if not self._chase_active and self._chase_frame_counter % 20 == 0:
            available_zones = []
            
            # Ищем все доступные зоны
            for pos in range(0, self.light_count - segment_length, segment_length // 2):
                zone_available = True
                for cooldown_zone in self._chase_cooldown_zones:
                    if abs(pos - cooldown_zone['position']) < segment_length * 2:
                        zone_available = False
                        break
                
                if zone_available:
                    available_zones.append(pos)
            
            if available_zones:
                self._chase_position = random.choice(available_zones)
                
                # Добавляем в коуддаун
                self._chase_cooldown_zones.append({
                    'position': self._chase_position,
                    'frames_left': 180  # ~3 секунды коуддауна
                })
                
                self._chase_active = True
                self._chase_progress = 0
                
                # Градиент
                colors = self.color_palettes[self.current_palette]
                self._chase_start_color = QColor(random.choice(colors))
                self._chase_end_color = QColor(random.choice(colors))
                while self._chase_end_color == self._chase_start_color:
                    self._chase_end_color = QColor(random.choice(colors))
        
        # Анимация (остается такой же как выше)
        if self._chase_active:
            self._chase_progress += self._chase_speed
            
            if self._chase_progress <= 1.0:
                alpha = self._ease_in_out(self._chase_progress)
            else:
                alpha = self._ease_in_out(2.0 - self._chase_progress)
            
            if self._chase_progress >= 2.0:
                self._chase_active = False
                return
            
            brightness = int(alpha * 255)
            
            for i in range(segment_length):
                lamp_index = self._chase_position + i
                if 0 <= lamp_index < len(self.lights):
                    blend = i / max(1, segment_length - 1)
                    mixed_color = QColor(
                        int(self._chase_start_color.red() * (1 - blend) + self._chase_end_color.red() * blend),
                        int(self._chase_start_color.green() * (1 - blend) + self._chase_end_color.green() * blend),
                        int(self._chase_start_color.blue() * (1 - blend) + self._chase_end_color.blue() * blend)
                    )
                    self.lights[lamp_index]['base_color'] = mixed_color
                    self.lights[lamp_index]['brightness'] = brightness
                    
    def _ease_in_out(self, t):
        """Плавная функция easing для естественных переходов"""
        return t * t * (3 - 2 * t)  # Кубический easing

    def custom_paint_event(self, event):
        """Отрисовывает гирлянду - упрощенная версия без бликов"""
        self.original_paint_event(event)
        
        if not self.visible:
            return
        
        painter = QPainter(self.target_widget)
        painter.setRenderHint(QPainter.Antialiasing)
        
        wire_y = 10

        # Лампочки
        for light in self.lights:
            x = light['x']
            y = wire_y + light['y_offset']
            
            base_color = light['base_color']
            # Применяем яркость к цвету
            final_color = QColor(
                min(255, base_color.red() * light['brightness'] // 255),
                min(255, base_color.green() * light['brightness'] // 255),
                min(255, base_color.blue() * light['brightness'] // 255)
            )
            
            radius = light['size'] / 2

            # Лампочка
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(final_color))
            painter.drawEllipse(QPointF(x, y), radius, radius)
