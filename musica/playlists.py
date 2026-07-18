import json
from pathlib import Path

PLAYLISTS_DIR = Path(__file__).resolve().parent.parent / "playlists"


def listar_playlists() -> list[str]:
    if not PLAYLISTS_DIR.exists():
        return []
    return sorted(caminho.stem for caminho in PLAYLISTS_DIR.glob("*.json"))


def carregar_playlist(nome: str) -> list[str]:
    caminho = PLAYLISTS_DIR / f"{nome}.json"
    if not caminho.exists():
        return []
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)
