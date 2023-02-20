from typing import Dict, Optional, List, Any, Tuple
from dataclasses import dataclass
import nbimporter

# These are special cases for the i/o operations on the register example


class Call:
    def __init__(self, threadno, func, args, start, end):
        super().__init__()
        self.threadno: int = threadno
        self.func: str = func
        self.args: List[Any] = args
        self.start: float = start
        self.end: float = end
        self.order: Optional[int] = None

    def __eq__(self, other: object):
        if not isinstance(other, Call):
            raise NotImplementedError
        return (self.threadno, self.func, self.args, self.start, self.end, self.order) == (other.threadno, other.func, other.args, other.start, other.end, other.order)

    def __hash__(self):
        return hash((self.threadno, self.func, tuple(self.args), self.start, self.end, self.order))

    def __str__(self):
        return f'{self.func}({self.args})'

    def exec(self, state: 'State') -> Tuple['State', Any]:
        raise NotImplementedError


class State:
    def copy(self) -> 'State':
        raise NotImplementedError


class History:
    """Nice wrapper for a list of calls"""

    def __init__(self, calls: List[Call]):
        self.calls: List[Call] = calls

    def __eq__(self, other: object):
        if not isinstance(other, History):
            raise NotImplementedError
        return self.calls == other.calls


@dataclass
class I:
    """
    If normal, start = first return, end = last call\n
    If reversed, start = last call, end = first return
    """
    start: float
    end: float
    reversed: bool = False


@dataclass
class StateIO(State):
    value: Optional[int] = None

    def copy(self):
        return StateIO(value=self.value)


class CallWrite(Call):
    def __init__(self, threadno, arg: int, start, end):
        self.arg = arg
        super().__init__(threadno, "write", [arg], start, end)

    def exec(self, state):
        if not isinstance(state, StateIO):
            raise Exception("State is not of type StateIO")
        state.value = self.arg
        return state, None


class CallRead(Call):
    def __init__(self, threadno, arg: int, start, end):
        self.arg = arg
        super().__init__(threadno, "read", [arg], start, end)

    def exec(self, state):
        if not isinstance(state, StateIO):
            raise Exception("State is not of type StateIO")
        if state.value is None:
            return
        if state.value != self.arg:
            return
        return state, None


class CallCAS(Call):
    def __init__(self, threadno, compare: int, swap: int, cond: bool, start, end):
        self.cond = cond
        self.compare = compare
        self.swap = swap
        super().__init__(threadno, f"cas", [compare, swap, cond], start, end)

    def __str__(self):
        if self.cond:
            return f"{self.compare} -> {self.swap}"
        else:
            return f"!{self.compare}"

    def exec(self, state):
        if not isinstance(state, StateIO):
            raise Exception("State is not of type StateIO")
        if state.value is None:
            return
       # if cond is True, the value must be equal to compare
        if self.cond:
            if state.value != self.compare:
                return
            state.value = self.swap
            return state, None
        # if cond is False, the value must be different from compare
        else:
            if state.value == self.compare:
                return
            return state, None


# def make_intervals(sort_by_var):
#     intervals: Dict[int, I] = {}
#     for var, var_class in sort_by_var.items():
#         i1 = min(c.end for c in var_class)
#         i2 = max(c.start for c in var_class)
#         if i1 < i2:
#             # No write/read happens in the interval
#             intervals[var] = I(i1, i2)
#         else:
#             intervals[var] = I(i2, i1, True)

#     return intervals

inp1 = [(1, 2), (2, 1)]
inp2 = [(1, 2), (2, 3), (3, 1)]
inp3 = [(2, 1), (1, 3)]
inp4 = [(1, 3), (2, 1)]


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
