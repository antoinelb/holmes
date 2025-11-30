from typing import Literal


def format_list(
    list_: list[str] | tuple[str, ...],
    surround: str = "",
    word: Literal["and", "or"] = "and",
) -> str:
    if surround:
        list_ = [f"{surround}{x}{surround}" for x in list_]
    if len(list_) == 0:
        return ""
    elif len(list_) == 1:
        return list_[0]
    else:
        return f"{', '.join(list_[:-1])} {word} {list_[-1]}"
