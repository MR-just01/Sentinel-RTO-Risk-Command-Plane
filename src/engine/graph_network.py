"""
Optimized In-Memory Identity Graph Sentinel.
Performs sub-millisecond local node degree lookups.
"""
import networkx as nx
import pandas as pd


class FraudRingSentinel:
    def __init__(self):
        self.graph = nx.Graph()

    def update_graph(self, df: pd.DataFrame):
        """Ingests high-confidence identity edges."""
        for _, row in df.iterrows():
            dev = f"DEV:{row['device_id']}"
            phone = f"PHONE:{row['phone']}"
            addr = f"ADDR:{hash(row['delivery_address'])}"

            self.graph.add_edge(dev, phone)
            self.graph.add_edge(dev, addr)

    def extract_graph_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Sub-millisecond local degree extraction."""
        self.update_graph(df)

        graph_features = []
        for _, row in df.iterrows():
            dev_node = f"DEV:{row['device_id']}"
            phone_node = f"PHONE:{row['phone']}"

            dev_degree = self.graph.degree(dev_node) if self.graph.has_node(dev_node) else 0
            phone_degree = self.graph.degree(phone_node) if self.graph.has_node(phone_node) else 0

            # Direct local check: device degree >= 3 or phone degree >= 2 flags syndicate
            is_syndicate = int(dev_degree >= 3 or phone_degree >= 2)

            graph_features.append({
                "graph_device_degree": dev_degree,
                "graph_phone_degree": phone_degree,
                "graph_is_syndicate_cluster": is_syndicate
            })

        return pd.DataFrame(graph_features, index=df.index)