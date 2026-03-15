class StateManager:
    def __init__(self, graph=None, initial_node_id=None):
        self.graph = graph or {"nodes": [], "edges": []}
        self.current_node_id = initial_node_id or self._get_default_node_id()

    def _get_default_node_id(self):
        nodes = self.graph.get("nodes", [])
        if not nodes:
            return None
        return nodes[0].get("id")

    def set_graph(self, graph):
        self.graph = graph or {"nodes": [], "edges": []}
        if self.current_node_id is None:
            self.current_node_id = self._get_default_node_id()

    def set_current_node(self, node_id):
        self.current_node_id = node_id

    def get_current_node(self):
        for node in self.graph.get("nodes", []):
            if node.get("id") == self.current_node_id:
                return node
        return None

    def get_current_widgets(self):
        current_node = self.get_current_node()
        if not current_node:
            return []
        return current_node.get("widgets", [])

    def get_state_snapshot(self):
        current_node = self.get_current_node() or {"id": None, "widgets": []}
        widgets = current_node.get("widgets", [])

        return {
            "nodeId": current_node.get("id"),
            "widgets": [widget.serialize() for widget in widgets],
        }