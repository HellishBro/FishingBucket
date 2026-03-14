import math

import expr_dice_roller as dice
from expr_dice_roller.evaluator import EvalFunc, IEvaluator

@lambda _: _()
class min_function(EvalFunc):
    def __init__(self):
        pass

    def call(self, evaluator: IEvaluator, arguments: list[float]) -> float:
        return min(arguments)

    def __str__(self):
        return "min(...arguments) = <builtin function>"


@lambda _: _()
class max_function(EvalFunc):
    def __init__(self):
        pass

    def call(self, evaluator: IEvaluator, arguments: list[float]) -> float:
        return max(arguments)

    def __str__(self):
        return "max(...arguments) = <builtin function>"

@lambda _: _()
class round_function(EvalFunc):
    def __init__(self):
        pass

    @staticmethod
    def round_school(x):
        i, f = divmod(x, 1)
        return int(i + ((f >= 0.5) if (x > 0) else (f > 0.5))) # https://stackoverflow.com/questions/43851273/how-to-round-float-0-5-up-to-1-0-while-still-rounding-0-45-to-0-0-as-the-usual

    def call(self, evaluator: IEvaluator, arguments: list[float]) -> float:
        x, denomination = arguments[0] if len(arguments) >= 1 else 0, arguments[1] if len(arguments) >= 2 else 1
        return self.round_school(x / denomination) * denomination

    def __str__(self):
        return "round(x, denomination = 1) = <builtin function>"

@lambda _: _()
class floor_function(EvalFunc):
    def __init__(self):
        pass

    def call(self, evaluator: IEvaluator, arguments: list[float]) -> float:
        x, denomination = arguments[0] if len(arguments) >= 1 else 0, arguments[1] if len(arguments) >= 2 else 1
        return math.floor(x / denomination) * denomination

    def __str__(self):
        return "floor(x, denomination = 1) = <builtin function>"

@lambda _: _()
class ceil_function(EvalFunc):
    def __init__(self):
        pass

    def call(self, evaluator: IEvaluator, arguments: list[float]) -> float:
        x, denomination = arguments[0] if len(arguments) >= 1 else 0, arguments[1] if len(arguments) >= 2 else 1
        return math.ceil(x / denomination) * denomination

    def __str__(self):
        return "ceil(x, denomination = 1) = <builtin function>"


@lambda _: _()
class abs_function(EvalFunc):
    def __init__(self):
        pass

    def call(self, evaluator: IEvaluator, arguments: list[float]) -> float:
        x = arguments[0] if len(arguments) >= 1 else 0
        return abs(x)

    def __str__(self):
        return "abs(x) = <builtin function>"


@lambda _: _()
class sqrt_function(EvalFunc):
    def __init__(self):
        pass

    def call(self, evaluator: IEvaluator, arguments: list[float]) -> float:
        x = arguments[0] if len(arguments) >= 1 else 0
        if x < 0: return 0
        return x ** 0.5

    def __str__(self):
        return "sqrt(x) = <builtin function>"

@lambda _: _()
class mod_function(EvalFunc):
    def __init__(self):
        pass

    def call(self, evaluator: IEvaluator, arguments: list[float]) -> float:
        a, b = arguments[0] if len(arguments) >= 1 else 0, arguments[1] if len(arguments) >= 2 else 0
        if b == 0: return 0
        return a % b

    def __str__(self):
        return "mod(dividend, divisor) = <builtin function>"

@lambda _: _()
class if_function(EvalFunc):
    def __init__(self):
        pass

    def call(self, evaluator: IEvaluator, arguments: list[float]) -> float:
        condition, true, false = arguments[0] if len(arguments) >= 1 else 0, arguments[1] if len(arguments) >= 2 else 0, arguments[2] if len(arguments) >= 3 else 0
        return true if int(condition) else false

    def __str__(self):
        return "if(condition, true_value, false_value) = <builtin function>"

@lambda _: _()
class in_function(EvalFunc):
    def __init__(self):
        pass

    def call(self, evaluator: IEvaluator, arguments: list[float]) -> float:
        target, minimum, maximum = arguments[0] if len(arguments) >= 1 else 0, arguments[1] if len(arguments) >= 2 else 0, arguments[2] if len(arguments) >= 3 else 0
        return int(minimum <= target <= maximum)

    def __str__(self):
        return "in(x, minimum, maximum) = <builtin function>"


class global_functions(dice.Environment):
    def __init__(self):
        super().__init__()
        self.immutable: dice.Environment | None = None
        self.mutable: dice.Environment | None = None
        self.variables["min"] = min_function
        self.variables["max"] = max_function
        self.variables["round"] = round_function
        self.variables["floor"] = floor_function
        self.variables["ceil"] = ceil_function
        self.variables["abs"] = abs_function
        self.variables["sqrt"] = sqrt_function
        self.variables["mod"] = mod_function
        self.variables["if"] = if_function
        self.variables["in"] = in_function

    def get(self, name: str) -> float | EvalFunc:
        if (v := self.variables.get(name)) is not None: return v
        if self.immutable and (v := self.immutable.variables.get(name)) is not None: return v
        return self.mutable.get(name)

    def assign(self, name: str, value: float | EvalFunc):
        self.mutable.assign(name, value)


