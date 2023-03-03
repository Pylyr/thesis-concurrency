from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any, Tuple


class Call:
    def __init__(self, threadno: int, func: str, args: List[Any], start: float, end: float):
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


class I:
    """
    If normal, start = first return, end = last call\n
    If reversed, start = last call, end = first return
    """
    start: float
    end: float
    reversed: bool = False

    def __init__(self, start: float, end: float, reversed: bool = False, silent: bool = False):
        if not silent:
            assert start <= end, f'{start} > {end}'
        else:
            if start > end:
                start, end = end, start

        self.start = start
        self.end = end
        self.reversed = reversed

    def isIntersecting(self, other: 'I') -> bool:
        return self.start <= other.end and self.end >= other.start

    def isContainedIn(self, other: 'I') -> bool:
        return self.start >= other.start and self.end <= other.end

    def intersection(self, other: 'I') -> 'I':
        if not self.isIntersecting(other):
            raise Exception(f'{self} and {other} do not intersect')
        return I(max(self.start, other.start), min(self.end, other.end))

    def __repr__(self):
        return f'{self.start} - {self.end}'

    def __contains__(self, item: float):
        return self.start <= item <= self.end


@dataclass
class StateQueue(State):
    stack: List[Any] = field(default_factory=list)

    def copy(self):
        return StateQueue(stack=self.stack.copy())


class CallEnq(Call):
    def __init__(self, threadno: int, arg: int, start: float, end: float):
        self.arg = arg
        super().__init__(threadno, "enq", [arg], start, end)

    def exec(self, state):
        if not isinstance(state, StateQueue):
            raise Exception("State is not a StateQueue")
        state.stack.append(self.arg)
        return state, None


class CallDeq(Call):
    def __init__(self, threadno: int, arg: int, start: float, end: float):
        self.arg = arg
        super().__init__(threadno, "deq", [arg], start, end)

    def exec(self, state):
        if not isinstance(state, StateQueue):
            raise Exception("State is not a StateQueue")
        if len(state.stack) == 0:
            return
        e = state.stack.pop(0)
        if e != self.arg:
            return
        return state, e

# These are special cases for the i/o operations on the register example


@dataclass
class StateIO(State):
    value: Optional[int] = None

    def copy(self):
        return StateIO(value=self.value)


class CallWrite(Call):
    def __init__(self, threadno: int, arg: int, start: float, end: float):
        self.arg = arg
        super().__init__(threadno, "write", [arg], start, end)

    def exec(self, state):
        if not isinstance(state, StateIO):
            raise Exception("State is not of type StateIO")
        state.value = self.arg
        return state, None


class CallRead(Call):
    def __init__(self, threadno: int, arg: int, start: float, end: float):
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
    def __init__(self, threadno: int, cond: bool, compare: int, swap: int, start: float, end: float):
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
