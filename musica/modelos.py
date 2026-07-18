from dataclasses import dataclass


@dataclass
class Musica:
    url: str
    nome: str
    usuario: str


@dataclass
class FaixaResolvida:
    stream_url: str
    titulo: str
    thumbnail: str | None = None
