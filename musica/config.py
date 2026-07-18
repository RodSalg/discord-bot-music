from pathlib import Path
from typing import Any

FFMPEG_BEFORE_OPTIONS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTIONS = "-vn"

MUSICAS_PATH = Path(__file__).resolve().parent.parent / "musicas.json"

MAX_ITENS_PLAYLIST = 50
QTD_PROXIMAS_EXIBIDAS = 10

# resolve a música (link direto pro ffmpeg), uma de cada vez, só quando ela for tocar
YTDL_OPCOES: dict[str, Any] = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch",
}

# extração rápida (sem resolver áudio) usada só para listar itens de playlists/mixes
YTDL_FLAT_OPCOES: dict[str, Any] = {
    "format": "bestaudio/best",
    "quiet": True,
    "default_search": "ytsearch",
    "extract_flat": "in_playlist",
    "noplaylist": False,
    "playlistend": MAX_ITENS_PLAYLIST,
}
