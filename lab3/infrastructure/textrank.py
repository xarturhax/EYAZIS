"""Undirected weighted TextRank; lemma overlap is an explicit adaptation."""

import math
from itertools import combinations

from lab3.domain.models import Analyzed, Ranking
from lab3.domain.ranking import position


def similarity(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    if not left or not right:
        return 0.0
    denominator = math.log(len(left)) + math.log(len(right))
    # For two single-term sentences the original denominator is zero.
    if denominator == 0:
        return float(left[0] == right[0])
    return len(set(left) & set(right)) / denominator


class TextRank:
    name = "textrank"

    def __init__(self) -> None:
        self.prepared = False

    def prepare(self) -> None:
        if not self.prepared:
            import networkx as nx

            # Load PageRank's numerical dependencies before document timing.
            nx.pagerank(nx.path_graph(2), alpha=0.85)
            self.prepared = True

    def rank(self, document: Analyzed, weights: dict[str, float]) -> Ranking:
        import networkx as nx

        sentences = document.sentences
        graph = nx.Graph()
        graph.add_nodes_from(range(len(sentences)))
        for i, j in combinations(range(len(sentences)), 2):
            weight = similarity(sentences[i].terms, sentences[j].terms)
            if weight > 0:
                graph.add_edge(i, j, weight=weight)
        if not graph.number_of_edges():
            return Ranking(
                tuple(position(s, len(document.document.text)) for s in sentences),
                ("У графа нет рёбер: применено ранжирование по позиции.",),
            )
        try:
            values = nx.pagerank(graph, alpha=0.85, max_iter=200, tol=1e-8, weight="weight")
        except nx.PowerIterationFailedConvergence as error:
            raise ValueError("TextRank не сошёлся за 200 итераций.") from error
        return Ranking(tuple(float(values[i]) for i in range(len(sentences))))
