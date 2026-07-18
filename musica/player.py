import asyncio

import discord
from discord import FFmpegOpusAudio, StageChannel, VoiceChannel, VoiceClient

from .config import FFMPEG_BEFORE_OPTIONS, FFMPEG_OPTIONS, QTD_PROXIMAS_EXIBIDAS
from .fila import FilaDeReproducao
from .historico import HistoricoStorage
from .modelos import Musica
from .ui import PlayerControls
from .youtube import YoutubeService


def formatar_proximas(musicas: list[Musica], restantes: int) -> str:
    if not musicas:
        return "A fila está vazia."
    linhas = [f"{i}. {m.nome}" for i, m in enumerate(musicas, start=1)]
    texto = "\n".join(linhas)
    if restantes > 0:
        texto += f"\n+{restantes} música(s) restante(s)"
    return texto


class GuildPlayer:

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        youtube: YoutubeService,
        historico: HistoricoStorage,
    ) -> None:
        self._loop = loop
        self._youtube = youtube
        self._historico = historico
        self._suprimir_callback = False
        self._desconexao_esperada = False

        self.fila = FilaDeReproducao()
        self.voice_client: VoiceClient | None = None
        self.canal_texto: discord.abc.Messageable | None = None
        self.mensagem_atual: discord.Message | None = None

    def conectado(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_connected()

    def tocando_ou_pausado(self) -> bool:
        return self.voice_client is not None and (self.voice_client.is_playing() or self.voice_client.is_paused())

    def esta_pausado(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_paused()

    def pausar(self) -> None:
        if self.voice_client is not None and self.voice_client.is_playing():
            self.voice_client.pause()

    def retomar(self) -> None:
        if self.voice_client is not None and self.voice_client.is_paused():
            self.voice_client.resume()

    async def conectar(self, canal_voz: VoiceChannel | StageChannel) -> None:
        if self.conectado():
            return
        self.voice_client = await canal_voz.connect()

    async def adicionar_e_tocar_se_ocioso(self, musicas: list[Musica]) -> bool:
        ocioso = self.fila.esta_vazia() and not self.tocando_ou_pausado()
        self.fila.adicionar(musicas)
        if ocioso:
            await self._iniciar_reproducao(self.fila.avancar())
        return ocioso

    async def pular(self) -> Musica | None:
        musica = self.fila.avancar()
        await self._iniciar_reproducao(musica)
        return musica

    async def voltar(self) -> Musica | None:
        musica = self.fila.retroceder()
        if musica is not None:
            await self._iniciar_reproducao(musica)
        return musica

    async def parar(self) -> None:
        self.fila.limpar()
        self._parar_sem_avancar()
        await self._desativar_controles_antigos()
        if self.voice_client is not None:
            self._desconexao_esperada = True
            await self.voice_client.disconnect()
            self.voice_client = None

    async def desconectado_externamente(self) -> None:
        if self._desconexao_esperada:
            self._desconexao_esperada = False
            self.voice_client = None
            return

        self._suprimir_callback = True
        self.fila.limpar()
        await self._desativar_controles_antigos()
        self.voice_client = None

        if self.canal_texto is not None:
            await self.canal_texto.send("Fui desconectado do canal de voz - fila limpa.")

    def mensagem_fila(self, quantidade: int) -> str:
        proximas = self.fila.proximas_musicas(quantidade)
        restantes = max(self.fila.total_na_fila() - len(proximas), 0)
        return formatar_proximas(proximas, restantes)

    def _parar_sem_avancar(self) -> None:
        if self.voice_client is not None and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self._suprimir_callback = True
            self.voice_client.stop()

    async def _desativar_controles_antigos(self) -> None:
        if self.mensagem_atual is None:
            return
        try:
            await self.mensagem_atual.edit(view=None)
        except discord.HTTPException:
            pass
        self.mensagem_atual = None

    def _montar_embed(self, musica: Musica, thumbnail: str | None) -> discord.Embed:
        embed = discord.Embed(
            title="Tocando agora",
            description=musica.nome,
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"Pedido por {musica.usuario}")
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)

        proximas = self.fila.proximas_musicas(QTD_PROXIMAS_EXIBIDAS)
        if proximas:
            restantes = max(self.fila.total_na_fila() - len(proximas), 0)
            embed.add_field(name="Próximas", value=formatar_proximas(proximas, restantes), inline=False)

        return embed

    async def _iniciar_reproducao(self, musica: Musica | None) -> None:
        self._parar_sem_avancar()
        await self._desativar_controles_antigos()

        if musica is None or self.voice_client is None:
            return

        resolvido = await self._youtube.resolver(musica.url)
        if resolvido is None:
            if self.canal_texto is not None:
                await self.canal_texto.send(f"Não consegui tocar: {musica.nome}")
            await self._iniciar_reproducao(self.fila.avancar())
            return

        musica.nome = resolvido.titulo
        self._historico.salvar(musica.usuario, musica.url, musica.nome)

        player = FFmpegOpusAudio(
            resolvido.stream_url,
            before_options=FFMPEG_BEFORE_OPTIONS,
            options=FFMPEG_OPTIONS,
        )

        def ao_terminar(_erro: Exception | None) -> None:
            if self._suprimir_callback:
                self._suprimir_callback = False
                return
            asyncio.run_coroutine_threadsafe(self._proxima_automatica(), self._loop)

        self.voice_client.play(player, after=ao_terminar)

        if self.canal_texto is not None:
            embed = self._montar_embed(musica, resolvido.thumbnail)
            self.mensagem_atual = await self.canal_texto.send(embed=embed, view=PlayerControls(self))

    async def _proxima_automatica(self) -> None:
        await self._iniciar_reproducao(self.fila.avancar())
