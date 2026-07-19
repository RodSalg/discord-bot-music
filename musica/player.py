import asyncio
import time

import discord
from discord import FFmpegOpusAudio, StageChannel, VoiceChannel, VoiceClient

from .config import COR_PAUSADO, COR_TOCANDO, FFMPEG_BEFORE_OPTIONS, FFMPEG_OPTIONS, QTD_PROXIMAS_EXIBIDAS
from .fila import FilaDeReproducao
from .historico import HistoricoStorage
from .modelos import FaixaResolvida, Musica
from .ui import PlayerControls
from .youtube import YoutubeService

INTERVALO_ATUALIZACAO_PROGRESSO = 10
LARGURA_BARRA_PROGRESSO = 20
LIMITE_CAMPO_EMBED = 1000


def formatar_proximas(musicas: list[Musica], restantes: int) -> str:
    if not musicas:
        return "A fila está vazia."
    linhas = [f"**{i}.** {m.nome}" for i, m in enumerate(musicas, start=1)]
    texto = "\n".join(linhas)
    if restantes > 0:
        texto += f"\n+{restantes} música(s) restante(s)"
    if len(texto) > LIMITE_CAMPO_EMBED:
        texto = texto[:LIMITE_CAMPO_EMBED].rsplit("\n", 1)[0] + "\n…"
    return texto


def formatar_duracao(segundos: float) -> str:
    total = max(int(segundos), 0)
    minutos, segs = divmod(total, 60)
    horas, minutos = divmod(minutos, 60)
    if horas:
        return f"{horas}:{minutos:02d}:{segs:02d}"
    return f"{minutos}:{segs:02d}"


def formatar_barra_progresso(posicao: float, duracao: float) -> str:
    duracao = max(duracao, 1.0)
    posicao = max(0.0, min(posicao, duracao))
    preenchido = min(int((posicao / duracao) * LARGURA_BARRA_PROGRESSO), LARGURA_BARRA_PROGRESSO - 1)
    barra = "▬" * preenchido + "🔘" + "▬" * (LARGURA_BARRA_PROGRESSO - preenchido - 1)
    return f"{barra}\n{formatar_duracao(posicao)} / {formatar_duracao(duracao)}"


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
        self._musica_atual: Musica | None = None
        self._resolvido_atual: FaixaResolvida | None = None
        self._offset_base = 0.0
        self._inicio_monotonic: float | None = None
        self._tarefa_progresso: asyncio.Task[None] | None = None

    def conectado(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_connected()

    def tocando_ou_pausado(self) -> bool:
        return self.voice_client is not None and (self.voice_client.is_playing() or self.voice_client.is_paused())

    def esta_pausado(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_paused()

    def posicao_atual(self) -> float:
        if self._inicio_monotonic is None:
            return self._offset_base
        return self._offset_base + (time.monotonic() - self._inicio_monotonic)

    def pausar(self) -> None:
        if self.voice_client is not None and self.voice_client.is_playing():
            self.voice_client.pause()
            self._offset_base = self.posicao_atual()
            self._inicio_monotonic = None

    def retomar(self) -> None:
        if self.voice_client is not None and self.voice_client.is_paused():
            self.voice_client.resume()
            self._inicio_monotonic = time.monotonic()

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

    async def embaralhar(self) -> bool:
        if not self.fila.proximas:
            return False
        self.fila.embaralhar()
        await self._atualizar_mensagem_atual()
        return True

    async def inverter(self) -> bool:
        if not self.fila.proximas:
            return False
        self.fila.inverter()
        await self._atualizar_mensagem_atual()
        return True

    async def pular_para(self, posicao: int) -> Musica | None:
        musica = self.fila.pular_para(posicao)
        if musica is not None:
            await self._iniciar_reproducao(musica)
        return musica

    async def avancar_tempo(self, segundos: float) -> None:
        await self._buscar_posicao(self.posicao_atual() + segundos)

    async def retroceder_tempo(self, segundos: float) -> None:
        await self._buscar_posicao(self.posicao_atual() - segundos)

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

    def mensagem_lista_completa(self) -> str:
        todas = list(self.fila.proximas)
        if not todas:
            return "A fila está vazia."

        linhas = [f"**{i}.** {m.nome}" for i, m in enumerate(todas, start=1)]
        texto = "\n".join(linhas)
        if len(texto) > 1900:
            texto = texto[:1900] + "\n… (lista truncada)"

        return f"**Fila completa ({len(todas)} música(s)):**\n{texto}"

    def _parar_sem_avancar(self) -> None:
        if self.voice_client is not None and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self._suprimir_callback = True
            self.voice_client.stop()

    def _cancelar_tarefa_progresso(self) -> None:
        if self._tarefa_progresso is not None:
            self._tarefa_progresso.cancel()
            self._tarefa_progresso = None

    async def _ciclo_atualizacao_progresso(self) -> None:
        try:
            while True:
                await asyncio.sleep(INTERVALO_ATUALIZACAO_PROGRESSO)
                await self._atualizar_mensagem_atual()
        except asyncio.CancelledError:
            pass

    async def _desativar_controles_antigos(self) -> None:
        self._cancelar_tarefa_progresso()

        if self.mensagem_atual is None:
            return
        try:
            await self.mensagem_atual.edit(view=None)
        except discord.HTTPException:
            pass
        self.mensagem_atual = None
        self._musica_atual = None
        self._resolvido_atual = None
        self._offset_base = 0.0
        self._inicio_monotonic = None

    async def _atualizar_mensagem_atual(self) -> None:
        if self.mensagem_atual is None or self._musica_atual is None:
            return
        embed = self._montar_embed(self._musica_atual, self._resolvido_atual)
        try:
            await self.mensagem_atual.edit(embed=embed)
        except discord.HTTPException:
            pass

    def embed_atual(self) -> discord.Embed | None:
        if self._musica_atual is None:
            return None
        return self._montar_embed(self._musica_atual, self._resolvido_atual)

    def _montar_embed(self, musica: Musica, resolvido: FaixaResolvida | None) -> discord.Embed:
        pausado = self.esta_pausado()

        embed = discord.Embed(
            title=musica.nome,
            url=musica.url,
            description=f"Pedido por **{musica.usuario}**",
            color=COR_PAUSADO if pausado else COR_TOCANDO,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name="Pausado" if pausado else "Tocando agora")

        if resolvido is not None and resolvido.thumbnail:
            embed.set_thumbnail(url=resolvido.thumbnail)

        if resolvido is not None and resolvido.duracao:
            barra = formatar_barra_progresso(self.posicao_atual(), resolvido.duracao)
            embed.add_field(name="Progresso", value=barra, inline=False)

        proximas = self.fila.proximas_musicas(QTD_PROXIMAS_EXIBIDAS)
        if proximas:
            restantes = max(self.fila.total_na_fila() - len(proximas), 0)
            embed.add_field(name="Próximas", value=formatar_proximas(proximas, restantes), inline=False)

        return embed

    async def _buscar_posicao(self, segundos: float) -> None:
        if self.voice_client is None or self._resolvido_atual is None:
            return

        segundos = max(0.0, segundos)
        if self._resolvido_atual.duracao:
            segundos = min(segundos, max(self._resolvido_atual.duracao - 1, 0))

        self._parar_sem_avancar()
        self._cancelar_tarefa_progresso()

        player = FFmpegOpusAudio(
            self._resolvido_atual.stream_url,
            before_options=f"{FFMPEG_BEFORE_OPTIONS} -ss {segundos:.2f}",
            options=FFMPEG_OPTIONS,
        )

        def ao_terminar(_erro: Exception | None) -> None:
            if self._suprimir_callback:
                self._suprimir_callback = False
                return
            asyncio.run_coroutine_threadsafe(self._proxima_automatica(), self._loop)

        self.voice_client.play(player, after=ao_terminar)

        self._offset_base = segundos
        self._inicio_monotonic = time.monotonic()
        self._tarefa_progresso = self._loop.create_task(self._ciclo_atualizacao_progresso())

        await self._atualizar_mensagem_atual()

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

        self._musica_atual = musica
        self._resolvido_atual = resolvido
        self._offset_base = 0.0
        self._inicio_monotonic = time.monotonic()
        self._tarefa_progresso = self._loop.create_task(self._ciclo_atualizacao_progresso())

        if self.canal_texto is not None:
            embed = self._montar_embed(musica, resolvido)
            try:
                self.mensagem_atual = await self.canal_texto.send(embed=embed, view=PlayerControls(self))
            except discord.HTTPException:
                self.mensagem_atual = None
                await self.canal_texto.send(f"Tocando agora: {musica.nome}")

    async def _proxima_automatica(self) -> None:
        await self._iniciar_reproducao(self.fila.avancar())
