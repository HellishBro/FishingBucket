from enum import Enum, auto


class Platform(Enum):
    Fluxer = auto()
    Discord = auto()

    def get(self) -> int:
        if self == Platform.Fluxer:
            return 0
        else:
            return 1

    @classmethod
    def from_(cls, id_: int) -> Platform:
        return [Platform.Fluxer, Platform.Discord][id_]