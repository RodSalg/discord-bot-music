import random
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field

from .modelos import Musica


@dataclass
class FilaDeReproducao:
    atual: Musica | None = None
    proximas: deque[Musica] = field(default_factory=deque[Musica])
    historico: list[Musica] = field(default_factory=list[Musica])

    def adicionar(self, musicas: Iterable[Musica]) -> None:
        self.proximas.extend(musicas)

    def embaralhar(self) -> None:
        itens = list(self.proximas)
        random.shuffle(itens)
        self.proximas = deque(itens)

    def inverter(self) -> None:
        self.proximas.reverse()

    def avancar(self) -> Musica | None:
        if self.atual is not None:
            self.historico.append(self.atual)
        self.atual = self.proximas.popleft() if self.proximas else None
        return self.atual

    def pular_para(self, posicao: int) -> Musica | None:
        if posicao < 1 or posicao > len(self.proximas):
            return None
        resultado: Musica | None = None
        for _ in range(posicao):
            resultado = self.avancar()
        return resultado

    def retroceder(self) -> Musica | None:
        if not self.historico:
            return None
        if self.atual is not None:
            self.proximas.appendleft(self.atual)
        self.atual = self.historico.pop()
        return self.atual

    def limpar(self) -> None:
        self.proximas.clear()
        self.historico.clear()
        self.atual = None

    def esta_vazia(self) -> bool:
        return self.atual is None and not self.proximas

    def proximas_musicas(self, quantidade: int) -> list[Musica]:
        return list(self.proximas)[:quantidade]

    def total_na_fila(self) -> int:
        return len(self.proximas)
