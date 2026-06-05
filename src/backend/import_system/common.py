from abc import ABC, abstractmethod

from ..models import Proxy, ProxyGroup


class Importer(ABC):
    def __init__(self):
        self.proxies: list[Proxy] = []
        self.groups: list[ProxyGroup] = []

    @abstractmethod
    def import_data(self, data: bytes, owner: int): pass

    @staticmethod
    def sanitize_potential_template_fragment(fragment: str) -> str:
        return fragment.replace("{", "\\{").replace("}", "\\}")
