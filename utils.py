from typing import List, Dict, Any, Optional, DefaultDict
from dataclasses import dataclass
from collections import defaultdict
import matplotlib.pyplot as plt
from classes import *
import random
import copy
import tqdm
import pickle
import import_ipynb
import os


def sort_by_thread(spec: List[Call]):
    threads: DefaultDict[int, List[Call]] = defaultdict(list)
    for c in spec:
        threads[c.threadno].append(c)
    return threads


def visualize_history(spec: List[Call]):
    # make the graph big enough so that the labels don't overlap
    fig, ax = plt.subplots(figsize=(16, 10))
    threads = sort_by_thread(spec)

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


def generate_random_spec(n: int, m: int, p: int, ops: List[str]):
    """
    n is the number of threads\n
    m is the number of operations\n
    p is the number of variables\n
    the only constraint is that operations cannot overlap in time on the same thread
    """

    print(f"generating spec with {n} threads, {m} operations, {p} variables"
          f" and ops: {ops}")
    var_dict: DefaultDict[Any, bool] = defaultdict(lambda: False)

    threads: DefaultDict[int, List[Call]] = defaultdict(list)
    for _ in range(m):
        thread = random.randint(1, n)
        op = random.choice(ops)
        start: float
        end: float
        if len(threads[thread]) == 0:
            start = 0
        else:
            start = threads[thread][-1].end

        start += random.randint(0, 5) + random.random()
        end = start + random.randint(1, 10) + random.random()
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
                    compare=arg2,
                    swap=arg,
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
    return [c for thread in threads.values() for c in thread]


def generate_tests(filename: str, total=1000, success_percentage=0.2, n=3, m=8, p=4, ops=["io", "cas"]):
    success = []
    fail = []
    loading = tqdm.tqdm(total=total)
    while loading.n < loading.total:
        spec = generate_random_spec(n, m, p, ops)
        # if there is not at least 2 cas operations, then we can't test the false case
        if "cas" in ops and len([c for c in spec if isinstance(c, CallCAS)]) < 1:
            continue
        if len([c for c in spec if isinstance(c, CallRead)]) < 1:
            continue
        if len(spec) < 8:
            continue
        sol = linearize_generic(spec, StateIO())
        if sol is None and len(fail) < total * (1 - success_percentage):
            fail.append(spec)
            loading.update()
        elif sol is not None and len(success) < total * success_percentage:
            success.append(spec)
            loading.update()

    with open(filename, "wb") as f:
        for spec in success:
            pickle.dump((spec, True), f)
        for spec in fail:
            pickle.dump((spec, False), f)


def load_test(filename: str) -> List[Tuple[List[Call], bool]]:
    if not os.path.exists(f"tests/{filename}"):
        raise FileNotFoundError(f"tests/{filename} not found")

    if not filename.endswith(".pkl"):
        raise ValueError(f"File {filename} is not a pickle file")

    with open(f"tests/{filename}", "rb") as f:
        test = []
        while True:
            try:
                test.append(pickle.load(f))
            except EOFError:
                break
    return test
