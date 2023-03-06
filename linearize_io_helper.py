from typing import Dict, DefaultDict, Optional, List, Set, Any, Tuple
from collections import defaultdict
from classes import *
from graph import *


def populate_call_bins(
        spec: List[Call],
        sort_by_var: DefaultDict[int, List[Call]],
        true_cases: List[CallCAS],
        false_cases: List[CallCAS]):
    for c in spec:
        if isinstance(c, (CallWrite, CallRead)):
            sort_by_var[c.arg].append(c)
        elif isinstance(c, CallCAS) and c.cond:
            sort_by_var[c.swap].append(c)
            sort_by_var[c.compare].append(c)
            true_cases.append(c)
        elif isinstance(c, CallCAS) and not c.cond:
            false_cases.append(c)


def get_writes_per_var(sort_by_var: DefaultDict[int, List[Call]]):
    return {var: next(c for _, c in enumerate(var_class) if isinstance(c, CallWrite)
                      or (isinstance(c, CallCAS) and c.cond and c.swap == var)) for var, var_class in sort_by_var.items()}


def basic_io_checks(sort_by_var: DefaultDict[int, List[Call]]):
    """
    check that there is only one write per variable
    checks that the read doesn't end before the write starts
    """

    for var, var_class in sort_by_var.items():
        if sum([isinstance(c, CallWrite) or (isinstance(c, CallCAS) and c.cond and c.swap == var) for c in var_class]) != 1:
            return

    writes = get_writes_per_var(sort_by_var)

    # check that the the first read doesn't end before the write starts
    for var, var_class in sort_by_var.items():
        write = writes[var]
        if not all(
                read.end > write.start for read in var_class
                if not (isinstance(read, CallWrite) or (isinstance(read, CallCAS) and read.cond and read.swap == var))):
            return

    return writes


def make_intervals(sort_by_var: DefaultDict[int, List[Call]]):
    intervals: Dict[int, I] = {}
    for var, var_class in sort_by_var.items():
        i1 = min(c.end for c in var_class)
        i2 = max(c.start for c in var_class)
        if i1 < i2:
            # No write/read happens in the interval
            intervals[var] = I(i1, i2)
        else:
            intervals[var] = I(i2, i1, True)
    return intervals


def list_cycles(graph: Dict[int, List[int]]):
    cycles: List[List[int]] = []
    for var, neighbors in graph.items():
        for neighbor in neighbors:
            if neighbor in graph:
                for neighbor_neighbor in graph[neighbor]:
                    if neighbor_neighbor == var:
                        cycles.append([var, neighbor])
    return cycles


def make_blocks(intervals: Dict[int, I]):
    blocks: List[List[int]] = []
    forward_intervals: Dict[int, I] = {var: interval for var, interval in intervals.items() if not interval.reversed}
    reverse_intervals: Dict[int, I] = {var: interval for var, interval in intervals.items() if interval.reversed}

    # Step 1: Skeleton. All forward intervals are in different blocks
    for forward_var in forward_intervals:
        blocks.append([forward_var])

    # Step 2.1: Reversed intervals either contain a forward interval (same block)
    reverse_joined: Set[int] = set()

    for var, reverse_interval in reverse_intervals.items():

        for forward_block in blocks:
            forward_interval = intervals[forward_block[0]]
            if forward_interval.isContainedIn(reverse_interval):
                forward_block.append(var)
                reverse_joined.add(var)

    # Step 2.2: Label all the intersections of reversed intervals that are not contained in a forward interval

    graph: Dict[int, List[int]] = defaultdict(list)
    for var_i, interval_i in reverse_intervals.items():
        for var_j, interval_j in reverse_intervals.items():

            if var_i == var_j:
                graph[var_i].append(var_j)
                continue

            if interval_i.isIntersecting(interval_j):
                intersection = interval_i.intersection(interval_j)
                for forward_block in blocks:
                    forward_interval = intervals[forward_block[0]]
                    if intersection.isContainedIn(forward_interval):
                        break
                else:
                    graph[var_i].append(var_j)

    # Step 2.3: Find cycles in the graph
    cycles = find_cycles(graph)
    non_cycle_edges = get_non_cycle_edges(graph, cycles)
    new_blocks = cycles + non_cycle_edges

    # Step 2.4: Remove blocks made only of reverse_joined variables
    new_blocks = [block for block in new_blocks if not all(var in reverse_joined for var in block)]
    blocks += new_blocks

    # Step 2.4: All nodes that only intersect themselves make a block
    for var in graph:
        if graph[var] == [var] and var not in reverse_joined:
            blocks.append([var])

    blocks.sort(key=lambda x: max(intervals[v].start for v in x))
    return blocks


def is_strictly_before(var1: int, var2: int, blocks: List[List[int]]):
    block1 = 0
    block2 = 0
    for i, block in enumerate(reversed(blocks)):
        if var1 in block:
            block1 = len(blocks) - i - 1
        if var2 in block:
            block2 = len(blocks) - i - 1
    return block1 < block2


def basic_true_cas_checks(true_cases: List[CallCAS]):
    """
    checks that there are no loops, ex 1 -> 2, 2 -> 1
    checks that there is only one root, ex 1 -> 2, 1 -> 3 is not allowed
    """
    graph = {}
    for c in true_cases:
        if c.compare not in graph:
            graph[c.compare] = []
        graph[c.compare].append(c.swap)

    if has_loop(graph):
        return False

    if multiple_roots(true_cases):
        return False

    return True


def has_loop(graph: Dict[int, List[int]]):
    def dfs(node, visited):
        if node in visited:
            return True
        visited.add(node)
        if node not in graph:
            return False
        for child in graph[node]:
            if dfs(child, visited):
                return True
        return False

    for node in graph:
        if dfs(node, set()):
            return True
    return False


def multiple_roots(true_cases: List[CallCAS]):
    # If there is a node 3 -> 2, no other node can point from 3
    origins = {c.compare for c in true_cases}
    return len(origins) != len(true_cases)


def io_check(intervals: Dict[int, I]):
    for var in intervals:
        same_var_interval = intervals[var]
        last_call = same_var_interval.start if same_var_interval.reversed else same_var_interval.end
        first_return = same_var_interval.end if same_var_interval.reversed else same_var_interval.start
        for i_var, interval in intervals.items():
            if i_var == var or interval.reversed:
                continue
            # observation 1
            if first_return < interval.end and last_call > interval.start:
                return False
            # observation 2
            if last_call > interval.start and first_return < interval.end:
                return False

    return True


def topological_true_cas_sort(true_cases: List[CallCAS]):
    """
    sort the true cas calls in topological order
    nodes can only have one child, so
    1 -> 2, 1 -> 3 is not allowed

    e.g. 
    2 -> 3, 1 -> 2, 3 -> 4 => [1, 2, 3, 4]
    """
    graph: Dict[int, int] = {}
    for c in true_cases:
        graph[c.compare] = c.swap

    var_order: List[int] = []
    visited = set()

    def dfs(node):
        if node in visited:
            return
        visited.add(node)
        if node in graph:
            dfs(graph[node])
        var_order.append(node)

    for node in graph:
        dfs(node)

    indexed_var_order = {var: i for i, var in enumerate(reversed(var_order))}
    true_cases.sort(key=lambda c: indexed_var_order[c.compare])


def true_cas_intra_group_check(intervals: Dict[int, I], order: List[int]):
    """
    check that the true cas calls are in the right order
    """
    last_var = order[0]
    last_interval = intervals[last_var]
    for var in order[1:]:
        interval = intervals[var]
        if last_interval.reversed and interval.reversed:
            # I~ J~
            if last_interval.start > interval.end:
                return False

        elif last_interval.reversed:
            # I~ J
            if last_interval.start > interval.start:
                return False

        elif interval.reversed:
            # I J~
            if last_interval.end > interval.end:
                return False
        else:
            # I J
            if last_interval.end > interval.start:
                return False
        last_interval = interval
        last_var = var

    return True


def ordAfter(blocks: List[List[int]], var1: int, var2: int):
    """
    returns true if latest block index of var1 is before earliest block index of var2
    """
    block1 = None
    block2 = None
    for i in range(len(blocks)):
        if var1 in blocks[len(blocks) - i - 1]:
            block1 = len(blocks) - i - 1
            break
    for i in range(len(blocks)):
        if var2 in blocks[i]:
            block2 = i
            break
    if block1 is None or block2 is None:
        raise Exception("variable not found in blocks")

    return block2 > block1
