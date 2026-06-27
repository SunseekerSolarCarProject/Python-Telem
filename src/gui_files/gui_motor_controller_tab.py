from gui_files.base_graph_tab import BaseGraphTab


class MotorControllerGraphTab(BaseGraphTab):
    def __init__(self, controller_name, keys, units, color_mapping):
        self.controller_name = controller_name
        super().__init__(controller_name, keys, units, color_mapping)
