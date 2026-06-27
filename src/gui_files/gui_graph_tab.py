from gui_files.base_graph_tab import BaseGraphTab


class GraphTab(BaseGraphTab):
    def __init__(self, tab_name, keys, units, color_mapping):
        self.tab_name = tab_name
        super().__init__(tab_name, keys, units, color_mapping)
