from functools import cache
from typing import Literal, Callable

import ipsum


@cache
def get_ipsum_model(language: str) -> ipsum.LanguageModel:
    return ipsum.load_model(language)


def lorem_ipsum(length: Literal["SHORT"] | Literal["MEDIUM"] | Literal["LONG"]) -> Callable[[], str]:
    model = get_ipsum_model("en")
    if length == "SHORT":
        return lambda: " ".join(model.generate_words(10))
    elif length == "MEDIUM":
        return lambda: model.generate_sentences(1)[0]
    else:
        return lambda: model.generate_paragraphs(1)[0]
