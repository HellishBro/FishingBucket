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

class Exporter(ABC):
    def __init__(self, proxies: list[Proxy], groups: list[ProxyGroup]):
        self.proxies = proxies
        self.groups = groups

    @abstractmethod
    def export_data(self) -> bytes: pass

    @property
    @abstractmethod
    def filename(self) -> str: pass
