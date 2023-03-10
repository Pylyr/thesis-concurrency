from typing import Dict, List
import networkx as nx
import matplotlib.pyplot as plt

""" Return all unique cycles bigger than 2. Each cycle should be sorted.
ex. {1: [1, 2, 3, 4],
        2: [1, 2, 4],
        3: [1, 3, 7],
        4: [2, 4, 5, 6],
        5: [4, 5, 6],
        6: [4, 5, 6],
        7: [3, 7]}

returns [1,2,4], [4,5,6]

"""


def find_cycles(graph):
    cycles = set()

    def dfs(node, visited, path):
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


def get_non_cycle_edges(graph, cycles):
    cycle_edges = set()
    for cycle in cycles:
        for i in range(len(cycle)):
            j = (i + 1) % len(cycle)
            cycle_edges.add(tuple(sorted((cycle[i], cycle[j]))))
    non_cycle_edges = set()
    for node, neighbors in graph.items():
        for neighbor in neighbors:
            if node != neighbor and tuple(sorted((node, neighbor))) not in cycle_edges:
                non_cycle_edges.add(tuple(sorted((node, neighbor))))
    return sorted([list(edge) for edge in non_cycle_edges])


def make_blocks(graph):
    cycles = find_cycles(graph)
    non_cycle_edges = get_non_cycle_edges(graph, cycles)
    return cycles + non_cycle_edges


graph = {1: [2, 4, 5], 2: [1, 3, 4, 5], 3: [2, 4, 5, 6], 4: [1, 2, 3, 5, 6], 5: [1, 2, 3, 4, 6], 6: [3, 4, 5]}
# make a graph from the dictionary
G = nx.Graph()
for node, neighbors in graph.items():
    for neighbor in neighbors:
        G.add_edge(node, neighbor)

# find all maximal cliques
cliques = list(nx.find_cliques(G))
print(cliques)

# visualize the graph
nx.draw(G, with_labels=True)
plt.show()


def delete_subsets(arr):
    # given an array e.g. [[1,2,3], [1,2], [1,3], [2,3], [1], [2], [3], [4]]
    # return [[1,2,3], [4]]
    # i.e. delete all subsets and only keep the largest set
    arr = sorted(arr, key=lambda x: len(x))
    result = []
    for i in range(len(arr)):
        if not any(set(arr[i]).issubset(set(arr[j])) for j in range(i + 1, len(arr))):
            result.append(arr[i])
    return result


# write 10 tests
print(delete_subsets([[1, 3, 4, 6], [2, 3, 4, 6], [3, 4, 5, 6], [4, 5, 6], [5, 6]]))
