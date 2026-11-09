class PageNavigationMixin:
    """Page graph: which page (node) is shown and moving between pages on gestures.

    A graph is `{"nodes": [{"id", "widgets"}], "edges": [{"from", "to", "gesture"}]}`.
    Edges also accept `source`/`target` and any field in `edge_gesture_fields`
    (default: `gesture`, `trigger`, `event`).
    """

    def set_graph(self, graph):
        self.graph = graph or {"nodes": [], "edges": []}
        self._edges = [self._normalize_edge(edge) for edge in self.graph.get("edges", [])]
        if self._find_node(self.current_node_id) is None:
            nodes = self.graph.get("nodes", [])
            self.current_node_id = nodes[0].get("id") if nodes else None

    def set_current_node(self, node_id):
        """Show page `node_id`. Returns True if the page changed (usable as an event binding action)."""
        if node_id == self.current_node_id or self._find_node(node_id) is None:
            return False
        self.current_node_id = node_id
        return True

    def get_current_node(self):
        return self._find_node(self.current_node_id)

    def get_current_widgets(self):
        node = self.get_current_node()
        return node.get("widgets", []) if node else []

    def _normalize_edge(self, edge):
        return {
            "from": edge.get("from", edge.get("source")),
            "to": edge.get("to", edge.get("target")),
            "gestures": {edge[field] for field in self.edge_gesture_fields if edge.get(field)},
        }

    def _find_node(self, node_id):
        if node_id is None:
            return None
        for node in self.graph.get("nodes", []):
            if node.get("id") == node_id:
                return node
        return None

    def _dispatch_graph_navigation(self, event_name, now):
        outgoing = [edge for edge in self._edges if edge["from"] == self.current_node_id]
        matched = [edge for edge in outgoing if event_name in edge["gestures"]]

        if matched:
            edge = matched[0]
        elif self.gesture_config.get("allow_unmatched_single_edge_navigation", False) and len(outgoing) == 1:
            edge = outgoing[0]
        else:
            return False

        if edge["to"] == self.current_node_id or self._find_node(edge["to"]) is None:
            return False

        if self._is_rate_limited(
            key=f"node:{event_name}",
            now=now,
            cooldown=self.gesture_config["node_navigation_cooldown"],
        ):
            return False

        return self.set_current_node(edge["to"])
