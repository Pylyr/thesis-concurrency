from typing import Dict, DefaultDict, Optional, List, Set, Any, Tuple
from collections import defaultdict
from classes import *
from graph import *
import math
import copy
import networkx as nx


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


def get_writes_per_var(sort_by_var: Dict[int, List[Call]]):
    return {var: next(c for c in var_class if isinstance(c, CallWrite)
                      or (isinstance(c, CallCAS) and c.cond and c.swap == var)) for var, var_class in sort_by_var.items()}


def basic_io_checks(sort_by_var: Dict[int, List[Call]]):
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


def make_intervals(sort_by_var: Dict[int, List[Call]]):
    intervals: Dict[int, I] = {}
    for var, var_class in sort_by_var.items():
        i1 = min(c.end for c in var_class)
        i2 = max(c.start for c in var_class)
        if i1 < i2:
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


def make_blocks(sort_by_var: Dict[int, List[Call]], intervals: Dict[int, I], true_cas_var_groups: List[List[int]]):

    # Step 0: Initialize
    # Step 0.1: Merge true cases
    merged_intervals: Dict[Tuple[int] | int, I] = copy.deepcopy(intervals)  # type: ignore

    for true_cas_group in true_cas_var_groups:
        joined_ops = {true_cas_group[0]: [op for var in true_cas_group for op in sort_by_var[var]]}
        intervals = make_intervals(joined_ops)
        merged_intervals[tuple(true_cas_group)] = intervals[true_cas_group[0]]
        for var in true_cas_group:
            del merged_intervals[var]

    blocks: List[List[Tuple[int] | int]] = []
    forward_intervals: Dict[Tuple[int] | int, I] = {var: interval for var,
                                                    interval in merged_intervals.items() if not interval.reversed}
    reverse_intervals: Dict[Tuple[int] | int, I] = {
        var: interval for var, interval in merged_intervals.items() if interval.reversed}
    # print(forward_intervals)
    # print(reverse_intervals)
    # Step 1: Skeleton. All forward intervals are in different blocks
    for forward_var in forward_intervals:
        blocks.append([forward_var])

    # Step 2.1: Reversed intervals that contain a forward interval get added to the block and get marked.

    # 0 = not marked
    # 1 = marked (cannot have a block of its own)
    isMarked: Dict[I, bool] = {interval: False for interval in reverse_intervals.values()}
    for var, reverse_interval in reverse_intervals.items():
        for forward_block in blocks:
            forward_interval = merged_intervals[forward_block[0]]
            if forward_interval.isContainedIn(reverse_interval):
                forward_block.append(var)
                isMarked[reverse_interval] = True

    # Step 2.2: Clique problem in P time, no problemo
    rev_intervals_map = {interval: var for var, interval in reverse_intervals.items()}
    new_blocks: List[List[Tuple[int] | int]] = []
    for interval_i in sorted(isMarked.copy(), key=lambda x: x.end):
        intersection_vars: List[Tuple[int] | int] = [rev_intervals_map[interval_i]]
        for interval_j in sorted(isMarked.copy(), key=lambda x: x.end):
            if interval_i == interval_j:
                continue
            if interval_j.start > interval_i.end:
                break
            if interval_i.isIntersecting(interval_j):
                intersection = interval_i.intersection(interval_j)
                for forward_interval in forward_intervals.values():
                    if intersection.isContainedIn(forward_interval):
                        break
                else:
                    intersection_vars.append(rev_intervals_map[interval_j])

        if not all(isMarked[merged_intervals[v]] for v in intersection_vars):
            new_blocks.append(intersection_vars)

        for v in intersection_vars:
            isMarked[merged_intervals[v]] = True

        del isMarked[interval_i]

    blocks += new_blocks

    blocks.sort(key=lambda x: min(merged_intervals[v].end for v in x))
    return blocks


def basic_true_cas_checks(true_cases: List[CallCAS]):
    """
    checks that there are no loops, ex 1 -> 2, 2 -> 1
    checks that there is only one root, ex 1 -> 2, 1 -> 3 is not allowed
    """

    if has_loop(true_cases):
        return False

    if multiple_roots(true_cases):
        return False

    return True


def has_loop(true_cases: List[CallCAS]):
    graph = {}
    for c in true_cases:
        if c.compare not in graph:
            graph[c.compare] = []
        graph[c.compare].append(c.swap)

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
            if first_return < interval.end and last_call > interval.start:
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


def isAny_cas_intersect_write(false_cases: List[CallCAS], writes: Dict[int, CallWrite | CallCAS]):
    for c in false_cases:
        for w in writes.values():
            if I(c.start, c.end).isIntersecting(I(w.start, w.end)):
                return True
    return False


def make_true_cas_var_groups(true_cases: List[CallCAS]):
    true_cas_var_groups: List[List[int]] = []
    for true_cas in true_cases:
        for group in true_cas_var_groups:
            if true_cas.compare == group[-1]:
                group.append(true_cas.swap)
                break
        else:
            true_cas_var_groups.append([true_cas.compare, true_cas.swap])
    return true_cas_var_groups


def make_true_cas_call_groups(sort_by_var: Dict[int, List[Call]], true_cas_var_groups: List[List[int]]):
    true_cas_call_groups: List[List[Call]] = []
    for group in true_cas_var_groups:
        all_group_ops: List[Call] = []
        for var in group:
            all_group_ops.extend(sort_by_var[var])
        all_group_ops = list(dict.fromkeys(all_group_ops))
        true_cas_call_groups.append(all_group_ops)
    return true_cas_call_groups


def isValid_order(intervals: Dict[int, I], order: List[int]):
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


def intra_group_check(sort_by_var: Dict[int, List[Call]], true_cas_var_groups: List[List[int]]):
    true_cas_call_groups = make_true_cas_call_groups(sort_by_var, true_cas_var_groups)
    for group_i in range(len(true_cas_var_groups)):
        intra_group_bins = defaultdict(list)
        populate_call_bins(true_cas_call_groups[group_i], intra_group_bins, [], [])
        intra_group_intervals = make_intervals(intra_group_bins)
        order = true_cas_var_groups[group_i]
        if isValid_order(intra_group_intervals, order) is not True:
            return False
    return True


def inter_group_check(sort_by_var: Dict[int, List[Call]], true_cas_var_groups: List[List[int]]):
    sort_by_var = copy.deepcopy(sort_by_var)
    for var_group in true_cas_var_groups:
        var = var_group[0]
        for other_var in var_group[1:]:
            sort_by_var[var].extend(sort_by_var[other_var])
            del sort_by_var[other_var]

    intervals: Dict[int, I] = make_intervals(sort_by_var)

    return io_check(intervals)


def get_false_cas_resolvers(
        sort_by_var: Dict[int, List[Call]],
        false_cases: List[CallCAS],
        blocks: List[List[Tuple[int] | int]],
        writes: Dict[int, CallWrite | CallCAS],
        intervals: Dict[int, I]):

    false_cases.sort(key=lambda x: x.end)
    false_cas_var_resolver: Dict[CallCAS, Set[int]] = {}
    for false_cas in false_cases:
        available_writes: List[int] = []
        block_i = 0
        while block_i < len(blocks):
            merged_block = blocks[block_i]
            block = _expand_list(merged_block)

            if min((min(c.end for c in sort_by_var[var]) for var in block)) < false_cas.start:
                available_writes.clear()

            writes_in_block = {var for var in block if writes[var].start < false_cas.end}
            true_cas_tuples = [t for t in merged_block if isinstance(t, tuple)]

            for true_cas in true_cas_tuples:
                cutoff_var = max(
                    (var for var in true_cas if min(c.end for c in sort_by_var[var]) < false_cas.start),
                    key=lambda x: true_cas.index(x), default=-1)
                if cutoff_var == -1:
                    continue

                cutoff_i = true_cas.index(cutoff_var)
                for var in true_cas[:cutoff_i]:
                    writes_in_block.discard(var)

            available_writes.extend(writes_in_block)

            # if len(writes_in_block) == 0:
            #     break

            line = 0
            for var in writes_in_block:
                interval = intervals[var]
                if interval.reversed:
                    line = max(line, interval.start)
                else:
                    line = max(line, interval.end)

            if false_cas.end > line:
                block_i += 1
            else:
                break

        # if the false cas is fully contained in a forward interval then the only available write is of that interval
        for var in available_writes.copy():
            interval = intervals[var]
            if interval.reversed:
                continue
            if I(false_cas.start, false_cas.end).isContainedIn(interval):
                available_writes = [var]
                break

        false_cas_var_resolver[false_cas] = set(available_writes)
        false_cas_var_resolver[false_cas].discard(false_cas.compare)

    visited: Dict[int, I] = {}
    for false_cas in false_cases:
        if false_cas.compare not in visited and false_cas.compare in writes:
            if false_cas.start > writes[false_cas.compare].end:
                visited[false_cas.compare] = I(false_cas.end, math.inf)

    for false_cas in false_cases:
        for var in false_cas_var_resolver[false_cas].copy():
            if var in visited:
                if I(false_cas.start, false_cas.end).isContainedIn(visited[var]):
                    false_cas_var_resolver[false_cas].remove(var)
    return false_cas_var_resolver


def false_cas_group_check(false_cas_var_resolver: Dict[CallCAS, Set[int]], writes: Dict[int, CallWrite | CallCAS]):
    writes_ret = [0] + sorted([w.end for w in writes.values()]) + [math.inf]
    writes_ret_i = 0
    latest_write_ret: List[int] = []
    false_cases = list(false_cas_var_resolver.keys())
    false_cases.sort(key=lambda x: x.end)
    for false_cas in false_cases:
        while True:
            if I(
                false_cas.start, false_cas.end).isContainedIn(
                I(writes_ret[writes_ret_i],
                  writes_ret[writes_ret_i + 1])):
                latest_write_ret.append(writes_ret_i)
                break
            else:
                writes_ret_i += 1

    false_cas_blocks_i: Dict[int, List[CallCAS]] = defaultdict(list)
    for false_cas_i in range(len(false_cases)):
        false_cas_blocks_i[latest_write_ret[false_cas_i]].append(false_cases[false_cas_i])

    false_cas_blocks = list(false_cas_blocks_i.values())
    for false_cas_block in false_cas_blocks:
        false_cas_block_vars = set.intersection(*[false_cas_var_resolver[false_cas] for false_cas in false_cas_block])
        if len(false_cas_block_vars) == 0:
            return False
    return True


def _expand_list(l: List[Tuple[int] | int]) -> List[int]:
    ret = []
    for t in l:
        if isinstance(t, tuple):
            ret.extend(_expand_list(list(t)))
        else:
            ret.append(t)
    return ret


def order_lambda(c: Call, v: int):
    if isinstance(c, CallWrite):
        return -1
    elif isinstance(c, CallCAS) and c.cond is True:
        if c.swap == v:
            return -1
        else:
            return math.inf
    return c.start


def set_order(sort_by_var: Dict[int, List[Call]], true_cas_var_groups: List[List[int]]):
    # now we just need to set the order attribute of each call
    intervals: Dict[int, I] = make_intervals(sort_by_var)
    blocks = make_blocks(sort_by_var, intervals, true_cas_var_groups)
    order = 1
    for block in blocks:
        for var in _expand_list(block):
            sort_by_var[var].sort(key=lambda x: order_lambda(x, var))
            for call in sort_by_var[var]:
                call.order = order
                print(f"Set order of {str(call)} to {order}")
                if order_lambda(call, var) != math.inf:
                    order += 1
