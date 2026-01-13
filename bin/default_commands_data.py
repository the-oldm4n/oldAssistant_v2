from bin.function_list_main import (
    open_volume_mixer, close_volume_mixer,
    open_calc, close_calc,
    open_paint, close_paint,
    open_path,
    open_taskmgr, close_taskmgr,
    open_recycle_bin, close_recycle_bin,
    open_appdata, close_appdata
)
from bin.bluetooth_controller import bluetooth_controller

system_commands_data = {
    "mixer": {
        "open": open_volume_mixer,
        "close": close_volume_mixer
    },
    "calculator": {
        "open": open_calc,
        "close": close_calc
    },
    "paint": {
        "open": open_paint,
        "close": close_paint
    },
    "environment": {
        "open": open_path,
        "close": None
    },
    "task_manager": {
        "open": open_taskmgr,
        "close": close_taskmgr
    },
    "recycler": {
        "open": open_recycle_bin,
        "close": close_recycle_bin
    },
    "appdata": {
        "open": open_appdata,
        "close": close_appdata
    },
    "bluetooth": {
        "open": bluetooth_controller.toggle,
        "close": bluetooth_controller.toggle
    }

}