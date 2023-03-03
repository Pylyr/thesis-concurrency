from typing import Dict, List, Set, Tuple


def find_cycles(graph: Dict[int, List[int]]):
    """Return all unique cycles bigger than 2. Each cycle should be sorted."""
    cycles: Set[Tuple[int, ...]] = set()

    def dfs(node: int, visited: Set[int], path: List[int]):
        visited.add(node)
        path.append(node)

        for neighbor in graph[node]:
            if neighbor not in visited:
                dfs(neighbor, visited, path)
            elif neighbor == path[0] and len(path) > 2:
                cycle = tuple(sorted(path))
                cycles.add(cycle)

        path.pop()

    for node in graph:
        visited = set()
        path = []
        dfs(node, visited, path)

    return [sorted(cycle) for cycle in cycles if len(cycle) > 2]


def get_non_cycle_edges(graph: Dict[int, List[int]], cycles: List[List[int]]):
    """Return all edges that are not part of a cycle. Each edge should be sorted."""
    cycle_edges: Set[Tuple[int, int]] = set()
    for cycle in cycles:
        for i in range(len(cycle)):
            j = (i + 1) % len(cycle)
            cycle_edges.add(tuple(sorted((cycle[i], cycle[j]))))
    non_cycle_edges: Set[Tuple[int, int]] = set()
    for node, neighbors in graph.items():
        for neighbor in neighbors:
            if node != neighbor and tuple(sorted((node, neighbor))) not in cycle_edges:
                non_cycle_edges.add(tuple(sorted((node, neighbor))))
    return sorted([list(edge) for edge in non_cycle_edges])
