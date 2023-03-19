from typing import Dict, DefaultDict, Optional, List, Set, Any, Tuple
from dataclasses import dataclass
from collections import defaultdict
import matplotlib.pyplot as plt
from classes import *
import random
import copy
import tqdm
import pickle
import import_ipynb
import math
import os
import linearize_io_helper as io_helper


def sort_by_thread(spec: List[Call]):
    threads: DefaultDict[int, List[Call]] = defaultdict(list)
    for c in spec:
        threads[c.threadno].append(c)
    return threads


def visualize_history(spec: List[Call]):
    # make the graph big enough so that the labels don't overlap
    fig, ax = plt.subplots(figsize=(16, 10))
    threads = sort_by_thread(spec)
    # name x-axis
    ax.set_xlabel('Time')
    # name y-axis
    ax.set_ylabel('Thread')

    ax.set_yticks(range(max(threads.keys()) + 2))
    # leave margins on the top and bottom of the graph for the labels
    ax.set_ylim(-0.5, max(threads.keys()) + 1.5)

    for threadno, ops in threads.items():
        for op in ops:
            # draw the interval
            ax.plot([op.start, op.end], [threadno, threadno], color='black')
            # add little ticks at the start and end of the interval
            ax.plot([op.start, op.start], [threadno - 0.1, threadno + 0.1], color='black')
            ax.plot([op.end, op.end], [threadno - 0.1, threadno + 0.1], color='black')
            # draw the label slightly above the interval
            ax.text((op.start + op.end) / 2, threadno + 0.1, str(op),
                    horizontalalignment='center', verticalalignment='center')
            # draw the order of the operation above the label in red
            if op.order is not None:
                ax.text((op.start + op.end) / 2, threadno + 0.25, str(op.order),
                        horizontalalignment='center', verticalalignment='center', color='red')

    plt.show()


def linearize_generic(spec: List[Call], state: State):
    threads: DefaultDict[int, List[Call]] = sort_by_thread(spec)

    def helper(threads: DefaultDict[int, List[Call]], state: State):
        res: List[List[Call]] = []
        first_op_per_thread = [t[0] for t in threads.values() if t]
        if not first_op_per_thread:
            return res
        ref = first_op_per_thread.pop()
        candidates: List[Call] = [ref]
        while first_op_per_thread:
            op = first_op_per_thread.pop()
            if op.start >= ref.end:
                # if op starts after ref ends, then we cannot call op before ref, as that would violate the linearizability
                continue
            elif op.end <= ref.end:
                ref = op
                candidates.append(op)
                # we have to recheck all exisiting candidates, as they might be invalidated by the new ref
                for c in tuple(candidates):
                    if c.start >= ref.end:
                        candidates.remove(c)
            else:
                # other 2 cases are when op starts before ref ends, and when op ends after ref ends
                candidates.append(op)

        # now we just pop a candidate an proceed by recursion
        # print(f'candidates: {candidates}')
        for c in candidates:
            # print(f'candidate: {c}')

            new_state = state.copy()
            optional_state = c.exec(new_state)
            if optional_state is not None:
                new_state, _ = optional_state
            else:
                continue

            threads_copy = copy.deepcopy(threads)

            threads_copy[c.threadno].pop(0)
            sol = helper(threads_copy, new_state)
            if sol is not None:
                # since sol is a list of solutions, we need to add the current candidate to all of them
                # two cases:
                # 1. sol is empty, then we just add the candidate
                # 2. sol is not empty, then we add the candidate to all of them
                if sol == []:
                    res.append([c])
                else:
                    for s in sol:
                        s.insert(0, c)
                    res.extend(sol)

        if not res:
            return None
        return res

    # sort threads by the start time of the first operation
    for t in threads.values():
        t.sort(key=lambda x: x.start)
    ret = helper(threads, state)
    if ret is None:
        return ret
    for i in range(len(ret)):
        for j in range(len(ret[i])):
            ret[i][j].order = j + 1

    return ret


def generate_random_spec(
        n: int, m: int, p: int, ops: List[str],
        min_offset: int, max_offset: int, min_duration: int, max_duration: int):
    """
    n is the number of threads\n
    m is the number of operations\n
    p is the number of variables\n
    the only constraint is that operations cannot overlap in time on the same thread
    """

    var_dict: DefaultDict[Any, bool] = defaultdict(lambda: False)

    threads: DefaultDict[int, List[Call]] = defaultdict(list)
    m_counter = 0
    while m_counter < m:
        thread = random.randint(1, n)
        op = random.choice(ops)
        start: float
        end: float
        if len(threads[thread]) == 0:
            start = 0
        else:
            start = threads[thread][-1].end

        start += random.randint(min_offset, max_offset) + random.random()
        end = start + random.randint(min_duration, max_duration) + random.random()
        arg = random.randint(0, p)
        arg2 = arg
        if op == "cas":
            while arg == arg2:
                arg2 = random.randint(0, p)
        if op == "io" and var_dict[arg]:
            threads[thread].append(
                CallRead(
                    threadno=thread,
                    arg=arg,
                    start=start,
                    end=end))
        elif op == "io" and not var_dict[arg]:
            var_dict[arg] = True
            threads[thread].append(
                CallWrite(
                    threadno=thread,
                    arg=arg,
                    start=start,
                    end=end))
        elif op == "cas" and var_dict[arg]:
            threads[thread].append(
                CallCAS(
                    threadno=thread,
                    compare=arg,
                    swap=arg2,
                    cond=False,
                    start=start,
                    end=end))
        elif op == "cas" and not var_dict[arg]:
            var_dict[arg] = True
            var_dict[arg2] = True
            threads[thread].append(
                CallCAS(
                    threadno=thread,
                    compare=arg2,
                    swap=arg,
                    cond=True,
                    start=start,
                    end=end))
        else:
            raise NotImplementedError(f"Operation {op} not implemented")
        m_counter += 1
    return [c for thread in threads.values() for c in thread]


def generate_tests(
        filename: str, total=1000, success_percentage=0.2, no_threads=3, no_operations=8,
        no_variables=4, ops=["io", "cas"], min_cas=0, min_read=-0,
        min_offset=1, max_offset=5, min_duration=1, max_duration=10):
    success = 0
    fail = 0
    loading = tqdm.tqdm(total=total)
    with open(f"tests/{filename}", "wb") as f:
        while loading.n < loading.total:
            spec = generate_random_spec(
                n=no_threads,
                m=no_operations,
                p=no_variables,
                ops=ops,
                min_offset=min_offset,
                max_offset=max_offset,
                min_duration=min_duration,
                max_duration=max_duration)
            if "cas" in ops and len([c for c in spec if isinstance(c, CallCAS)]) < min_cas:
                continue
            if len([c for c in spec if isinstance(c, CallRead)]) < min_read:
                continue
            if isAny_fcas_intersect_write_comb(spec):
                continue

            sol = linearize_generic(spec, StateIO())
            if sol is None and fail < total * (1 - success_percentage):
                fail += 1
                pickle.dump((spec, False), f)
                loading.update()
            elif sol is not None and success < total * success_percentage:
                success += 1
                pickle.dump((spec, True), f)
                loading.update()


def save_test(test: List[Tuple[List[Call], bool]], filename: str):
    if not filename.endswith(".pkl"):
        raise ValueError(f"File {filename} is not a pickle file")

    with open(f"tests/{filename}", "wb") as f:
        for t in test:
            pickle.dump(t, f)


def load_test(filename: str) -> List[Tuple[List[Call], bool]]:
    if not os.path.exists(f"tests/{filename}"):
        raise FileNotFoundError(f"tests/{filename} not found")

    if not filename.endswith(".pkl"):
        raise ValueError(f"File {filename} is not a pickle file")

    loader = tqdm.tqdm()
    with open(f"tests/{filename}", "rb") as f:
        test = []
        while True:
            try:
                test.append(pickle.load(f))
                loader.update()
            except EOFError:
                break
    return test


def str_specification(spec: List[Call]):
    spec.sort(key=lambda x: x.start)
    res = ""
    symbol_dict = {
        "CallCAS": "!",
        "CallWrite": "+",
        "CallRead": "-",
    }
    for c in spec:
        print(f"{symbol_dict[c.__class__.__name__]}{c.args[0]} {c.start}-{c.end}")

    return res


def isIntervals_strictly_ordered(spec: List[Call]):
    sort_by_var = defaultdict(list)
    io_helper.populate_call_bins(spec, sort_by_var, [], [])
    intervals = io_helper.make_intervals(sort_by_var)
    for var_i, i in intervals.items():
        for var_j, j in intervals.items():
            if i.isIntersecting(j) and var_i != var_j:
                return False
    return True


def isRead_before_cas(spec: List[Call]):
    sort_by_var = defaultdict(list)
    false_cases: List[CallCAS] = []
    io_helper.populate_call_bins(spec, sort_by_var, [], false_cases)
    for c in false_cases:
        earliest_read = min((r.end for r in sort_by_var[c.compare] if isinstance(r, CallRead)), default=math.inf)
        if c.start < earliest_read:
            return False
    return True


def isAny_fcas_intersect_write_comb(spec: List[Call]):
    sort_by_var: DefaultDict[int, List[Call]] = defaultdict(list)
    false_cases: List[CallCAS] = []
    io_helper.populate_call_bins(spec, sort_by_var, [], false_cases)
    if io_helper.basic_io_checks(sort_by_var) is None:
        return False
    writes = io_helper.get_writes_per_var(sort_by_var)
    return io_helper.isAny_cas_intersect_write(false_cases, writes)
