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
            self._initialized = True
    
    def configure(
        self,
        colors_path: str,
        presets_path: Optional[str] = None,
        custom_presets_path: Optional[str] = None,
        icons_path: Optional[str] = None,
        custom_selectors: Optional[str] = None
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


mygui_config = MyGUIConfig()