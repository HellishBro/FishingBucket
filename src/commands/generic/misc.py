from typing import Literal, Callable

from lorem_text import lorem

def lorem_ipsum(length: Literal["MINI"] | Literal["SHORT"] | Literal["MEDIUM"] | Literal["LONG"]) -> Callable[[], str]:
    if length == "MINI":
        return lambda: lorem.words(1)
    elif length == "SHORT":
        return lambda: lorem.words(10)
    elif length == "MEDIUM":
        return lambda: lorem.sentence()
    else:
        return lambda: lorem.paragraph()
