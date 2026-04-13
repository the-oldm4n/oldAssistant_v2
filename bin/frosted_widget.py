import math
import random
import re
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QPainter, QColor, QBrush
from log_config import debuglog


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
        self.snow_color = QColor(snow_color) if not isinstance(snow_color, QColor) else snow_color
        
        # Параметры интерполяции
        self.interpolate_duration_sec = 3.0  # секунды на переход
        self.interpolate_steps = 0
        self.interpolate_max_steps = 1

        self.alpha_min = 50
        self.alpha_max = 200

        self.gradient_start_color = None
        self.gradient_end_color = None
        
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
                {"count": 200, "speed": 0.8, "size_min": 1.0, "size_max": 5.5, "weight": 50},
                {"count": 200, "speed": 0.4, "size_min": 1.0, "size_max": 4.0, "weight": 50},
                {"count": 800, "speed": 4.0, "size_min": 1.0, "size_max": 5.0, "weight": 10},
            ]
        else:
            self.presets = [
                {"count": 10, "speed": 0.4, "size_min": 1.0, "size_max": 3.5, "weight": 150},
                {"count": 20, "speed": 0.4, "size_min": 1.0, "size_max": 3.0, "weight": 70},
                {"count": 30, "speed": 0.3, "size_min": 1.0, "size_max": 4.0, "weight": 30},
                {"count": 50, "speed": 4.4, "size_min": 1.0, "size_max": 4.0, "weight": 1},
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
        self.timer.start(30)  # 33 FPS
        
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
            alpha = random.randint(self.alpha_min, self.alpha_max)
            self.flakes.append([x, y, size, speed_factor, sway_offset, alpha])

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
        # Используем ТЕКУЩИЙ размер виджета, а не начальный
        w, h = self.width(), self.height()
        for _ in range(self.snowflake_count):
            x = random.uniform(0, w)  # от 0 до текущей ширины
            y = random.uniform(-h, h)  # от -текущей высоты до текущей высоты
            size = random.uniform(self.flake_size_min, self.flake_size_max)
            speed_factor = random.uniform(0.7, 1.3)
            sway_offset = random.uniform(0, 1000)
            alpha = random.randint(self.alpha_min, self.alpha_max)
            self.flakes.append([x, y, size, speed_factor, sway_offset, alpha])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._init_snowflakes()  # пересоздаём при изменении размера

    def _interpolate_color(self, color1, color2, t):
        """Интерполяция между двумя цветами"""
        t = max(0.0, min(1.0, t))
        
        r = int(color1.red() + (color2.red() - color1.red()) * t)
        g = int(color1.green() + (color2.green() - color1.green()) * t)
        b = int(color1.blue() + (color2.blue() - color1.blue()) * t)
        a = int(color1.alpha() + (color2.alpha() - color1.alpha()) * t)
        
        return QColor(r, g, b, a)

    def _update_snow(self):
        # Обновляем интерполяцию если она активна
        if self.interpolate_steps <= self.interpolate_max_steps:
            self._update_interpolated_params()
        
        h = self.height()
        w = self.width()
        
        for flake in self.flakes:
            x, y, size, speed_factor, sway_offset, alpha = flake[:6]
            
            # Падение
            y += self.fall_speed * speed_factor
            
            # Лёгкое колебание (ветер)
            x += math.sin(y * 0.01 + sway_offset) * 0.3
            
            # Обновляем прогресс цвета если есть градиент
            if hasattr(self, 'gradient_start_color') and self.gradient_start_color and len(flake) >= 7:
                # Прогресс меняется в зависимости от положения снежинки
                # Чем ниже снежинка, тем ближе к конечному цвету
                progress = y / h if h > 0 else flake[6]
                progress = max(0.0, min(1.0, progress))
                flake[6] = progress  # обновляем прогресс
            
            # Сброс, если ушла вниз
            if y > h + 20:
                y = -10
                x = random.uniform(0, w)
                # Сбрасываем прогресс цвета для новой снежинки
                if len(flake) >= 7:
                    flake[6] = random.uniform(0.0, 0.3)  # начинаем с начального цвета
            
            flake[0], flake[1] = x, y
        
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        
        # Проверяем, есть ли градиент
        has_gradient = (hasattr(self, 'gradient_start_color') and 
                    self.gradient_start_color is not None and
                    hasattr(self, 'gradient_end_color') and 
                    self.gradient_end_color is not None)
        
        for flake in self.flakes:
            x, y, size, _, _, alpha = flake[:6]
            
            # КРИТИЧНО: Правильная проверка и получение прогресса
            if has_gradient:
                # Проверяем, есть ли прогресс в снежинке
                if len(flake) >= 7:
                    progress = flake[6]
                else:
                    # Если прогресса нет - создаем случайный
                    progress = random.random()
                    flake.append(progress)
                
                # Интерполируем цвет
                color = self._interpolate_color(
                    self.gradient_start_color, 
                    self.gradient_end_color, 
                    progress
                )
                color.setAlpha(alpha)
            else:
                # Обычный цвет
                color = QColor(self.snow_color)
                color.setAlpha(alpha)
            
            painter.setBrush(QBrush(color))
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

    def setSnowColor(self, color, white_balance=100):
        """Установка цвета снежинок с балансом белого"""
        self.gradient_start_color = None
        self.gradient_end_color = None

        if isinstance(color, str) and color.startswith("qlineargradient"):
            try:
                pattern = r"stop:\d+(?:\.\d+)?\s+(#[0-9a-fA-F]{6})"
                colors = re.findall(pattern, color)
                
                if len(colors) >= 2:
                    self.gradient_start_color = QColor(colors[0])
                    self.gradient_end_color = QColor(colors[1])

                    for flake in self.flakes:
                        if len(flake) == 6:
                            flake.append(random.random())
                        elif len(flake) >= 7:
                            flake[6] = random.random()

                    if white_balance != 0:
                        self.gradient_start_color = self._blend_with_white(self.gradient_start_color, white_balance)
                        self.gradient_end_color = self._blend_with_white(self.gradient_end_color, white_balance)

                    self.snow_color = self.gradient_start_color

                    self.update()
                    return
                    
            except Exception as e:
                debuglog.error(f"Ошибка парсинга градиента: {e}")

        for flake in self.flakes:
            if len(flake) > 6:
                flake.pop()

        if isinstance(color, str):
            base_color = QColor(color)
        elif isinstance(color, QColor):
            base_color = color
        elif isinstance(color, (list, tuple)):
            if len(color) == 3:
                base_color = QColor(*color)
            elif len(color) == 4:
                base_color = QColor(*color)
        else:
            base_color = QColor("#FFFFFF")

        if white_balance != 0:
            self.snow_color = self._blend_with_white(base_color, white_balance)
        else:
            self.snow_color = base_color

        self.update()
        
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
    def __init__(self, target_widget, light_count=15, light_size=8, width=920):
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
        
        self.lights_density = light_count / width if width > 0 else 0.018
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
            
    def update_size(self, new_width):
        """Принудительное обновление размера гирлянды"""
        if new_width > 0 and new_width != self.width:
            self.width = new_width
            # Пересчитываем количество лампочек для сохранения плотности
            self.light_count = max(10, int(self.width * self.lights_density))
            self.generate_lights()
            self.target_widget.update()
    
    def generate_lights(self):
        self.lights = []
        colors = self.color_palettes[self.current_palette]

        padding = 10
        
        for i in range(self.light_count):
            # Расчет позиции с учетом отступов и ТЕКУЩЕЙ ширины
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
