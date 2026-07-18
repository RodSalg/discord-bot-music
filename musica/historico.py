import json
from pathlib import Path


class HistoricoStorage:

    def __init__(self, caminho: Path) -> None:
        self._caminho = caminho

    def salvar(self, usuario: str, link: str, nome: str) -> None:
        registros: list[dict[str, str]] = []
        if self._caminho.exists():
            with open(self._caminho, "r", encoding="utf-8") as f:
                registros = json.load(f)

        registros.append({"usuario": usuario, "link": link, "nome": nome})

        with open(self._caminho, "w", encoding="utf-8") as f:
            json.dump(registros, f, ensure_ascii=False, indent=2)
