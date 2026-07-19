import asyncio
from typing import Any

import yt_dlp

from .config import YTDL_FLAT_OPCOES, YTDL_OPCOES
from .modelos import FaixaResolvida, Musica


def normalizar_url(entrada: dict[str, Any]) -> str:
    url = entrada.get("webpage_url") or entrada.get("url") or entrada.get("id") or ""
    url = str(url)
    if url and not url.startswith("http"):
        url = f"https://www.youtube.com/watch?v={url}"
    return url


class YoutubeService:

    def __init__(self) -> None:
        self._ytdl = yt_dlp.YoutubeDL(YTDL_OPCOES)  # type: ignore[arg-type]
        self._ytdl_flat = yt_dlp.YoutubeDL(YTDL_FLAT_OPCOES)  # type: ignore[arg-type]

    async def buscar(self, termo: str, usuario: str) -> list[Musica]:
        loop = asyncio.get_event_loop()
        dados = await loop.run_in_executor(None, lambda: self._ytdl_flat.extract_info(termo, download=False))
        if not dados:
            return []

        entradas = dados.get("entries") or [dados]
        musicas: list[Musica] = []
        for entrada_bruta in entradas:
            if not entrada_bruta:
                continue
            entrada: dict[str, Any] = dict(entrada_bruta)
            url = normalizar_url(entrada)
            if not url:
                continue
            nome = entrada.get("title") or url
            musicas.append(Musica(url=url, nome=nome, usuario=usuario))

        return musicas

    async def sugestoes(self, termo: str, quantidade: int = 10) -> list[tuple[str, str]]:
        if not termo:
            return []

        loop = asyncio.get_event_loop()
        consulta = f"ytsearch{quantidade}:{termo}"
        dados = await loop.run_in_executor(None, lambda: self._ytdl_flat.extract_info(consulta, download=False))
        if not dados:
            return []

        resultados: list[tuple[str, str]] = []
        entradas: list[Any] = dados.get("entries") or []
        for entrada_bruta in entradas:
            if not entrada_bruta:
                continue
            entrada: dict[str, Any] = dict(entrada_bruta)
            url = normalizar_url(entrada)
            if not url:
                continue
            titulo = entrada.get("title") or url
            resultados.append((titulo, url))

        return resultados

    async def resolver(self, url: str) -> FaixaResolvida | None:
        loop = asyncio.get_event_loop()
        dados = await loop.run_in_executor(None, lambda: self._ytdl.extract_info(url, download=False))
        if not dados:
            return None

        stream_url = dados.get("url")
        if not stream_url:
            return None

        titulo = dados.get("title") or url
        thumbnail = dados.get("thumbnail")
        duracao = dados.get("duration")
        return FaixaResolvida(stream_url=stream_url, titulo=titulo, thumbnail=thumbnail, duracao=duracao)
