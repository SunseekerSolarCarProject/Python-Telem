from gui_files.base_graph_tab import BaseGraphTab


class BatteryPackGraphTab(BaseGraphTab):
    def __init__(self, pack_name, keys, units, color_mapping):
        self.pack_name = pack_name
        super().__init__(pack_name, keys, units, color_mapping)
