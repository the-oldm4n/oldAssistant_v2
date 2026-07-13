from typing import Optional

class MyGUIConfig:
    """Глобальная конфигурация библиотеки MyGUI"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._colors_path = None
            self._presets_path = None
            self._custom_presets_path = None
            self._icons_path = None
            self._custom_selectors = None
            self._sidebar_delay = 300
            self._initialized = True
    
    def configure(
        self,
        colors_path: str,
        presets_path: Optional[str] = None,
        custom_presets_path: Optional[str] = None,
        icons_path: Optional[str] = None,
        custom_selectors: Optional[str] = None,
        sidebar_delay: Optional[int] = 300,
    ):
        """Однократная настройка библиотеки"""
        if colors_path is not None:
            self._colors_path = colors_path

        if presets_path is not None:
            self._presets_path = presets_path

        if custom_presets_path is not None:
            self._custom_presets_path = custom_presets_path

        if icons_path is not None:
            self._icons_path = icons_path

        if custom_selectors is not None:
            self._custom_selectors = custom_selectors

        if sidebar_delay is not None:
            self._sidebar_delay = sidebar_delay

    def update(self, property_name: str, value):
        """Обновление любого свойства конфига с валидацией"""
        allowed_properties = {
            '_colors_path': str,
            '_presets_path': (str, type(None)),
            '_custom_presets_path': (str, type(None)),
            '_icons_path': (str, type(None)),
            '_custom_selectors': (str, type(None)),
            '_sidebar_delay': int,
        }

        internal_name = f"_{property_name}"

        if internal_name not in allowed_properties:
            raise AttributeError(f"Property '{property_name}' does not exist")

        expected_types = allowed_properties[internal_name]
        if not isinstance(value, expected_types):
            raise TypeError(
                f"Property '{property_name}' expects {expected_types}, got {type(value)}"
            )

        setattr(self, internal_name, value)
    
    @property
    def colors_path(self) -> str:
        if self._colors_path is None:
            raise ValueError(
                "MyGUI не настроен! Вызовите MyGUIConfig().configure(colors_path=...)"
            )
        return self._colors_path
    
    @property
    def presets_path(self) -> Optional[str]:
        return self._presets_path
    
    @property
    def custom_presets_path(self) -> Optional[str]:
        return self._custom_presets_path
    
    @property
    def icons_path(self) -> Optional[str]:
        return self._icons_path
    
    @property
    def custom_selectors(self) -> Optional[str]:
        return self._custom_selectors
    
    @property
    def sidebar_delay(self) -> Optional[int]:
        return self._sidebar_delay


mygui_config = MyGUIConfig()