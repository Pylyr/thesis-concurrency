from typing import Dict, DefaultDict, Optional, List, Set, Any, Tuple
from dataclasses import dataclass
from collections import defaultdict
import bisect
from classes import *


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


def make_blocks(sort_by_var: DefaultDict[int, List[Call]], intervals: Dict[int, I]):
    graph: DefaultDict[int, List[int]] = defaultdict(list)

    for var_i, interval_i in intervals.items():
        i1, i2 = interval_i.start, interval_i.end
        for var_j, interval_j in intervals.items():
            j1, j2 = interval_j.start, interval_j.end
            if not interval_i.reversed and not interval_j.reversed:
                continue
            elif not interval_i.reversed:
                if j1 < i1 and j2 > i2:
                    graph[var_i].append(var_j)
            elif not interval_j.reversed:
                if i1 < j1 and i2 > j2:
                    graph[var_i].append(var_j)
            else:
                if i1 < j2 < i2 or j1 < i2 < j2:
                    graph[var_i].append(var_j)

    for key in sort_by_var:
        bisect.insort(graph[key], key)

    blocks: List[List[int]] = []
    for block in graph.values():
        if block not in blocks:
            blocks.append(block)

    blocks.sort(key=lambda x: max(intervals[v].start for v in x))

    return blocks


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


# def f():
    # available_writes: Set[CallWrite | CallCAS] = set()
    # block_i = 0
    # captured_write = None
    # false_cases.sort(key=lambda x: x.start)
    # while block_i < len(blocks):

    #     # 1. clear the available_writes if we are in a new block
    #     # 2. add the writes from the current block that started before the false cas return
    #     # 3. we advance to the next block if false cas start is after the last write in the current block

    #     block = blocks[block_i]
    #     writes_in_block = {writes[var] for var in block if writes[var].start < false_cas.end}

    #     if min((min(c.end for c in sort_by_var[var]) for var in block)) < false_cas.start:
    #         available_writes.clear()
    #         captured_write = None

    #     available_writes.update(writes_in_block)

    #     if len(writes_in_block) == 0:
    #         block_i -= 1
    #         break
    #     elif len(writes_in_block) == len(block):
    #         block_i += 1
    #     else:
    #         break

    # if false_cas.compare in writes:
    #     captured_write = writes[false_cas.compare]
    #     available_writes.discard(captured_write)

    # if not available_writes:
    #     return false_cas.compare

    #     if captured_write is not None and min(c.end for c in sort_by_var[captured_write.args[0]]) > false_cas.start:
    #         available_writes.add(captured_write)

    #     captured_write = None
