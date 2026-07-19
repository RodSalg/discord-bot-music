from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

import discord
from discord import Interaction, app_commands
from discord.ext import commands

from .config import QTD_PROXIMAS_EXIBIDAS
from .modelos import Musica
from .player import GuildPlayer
from .playlists import carregar_playlist

if TYPE_CHECKING:
    from .bot import MusicBot


class MusicCog(commands.Cog):

    def __init__(self, bot: "MusicBot") -> None:
        self.bot = bot

    async def _preparar_player(self, interaction: Interaction) -> GuildPlayer | None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return None

        player = self.bot.obter_player(interaction.guild.id)

        if not player.conectado():
            canal_voz = interaction.user.voice.channel if interaction.user.voice else None
            if canal_voz is None:
                await interaction.followup.send("Você precisa estar em um canal de voz!")
                return None
            await player.conectar(canal_voz)

        if isinstance(interaction.channel, discord.abc.Messageable):
            player.canal_texto = interaction.channel

        return player

    @app_commands.command(name="play", description="Toca uma música ou adiciona na fila (aceita playlists e mixes)")
    @app_commands.describe(musica="Link do YouTube (vídeo, playlist ou mix) ou nome da música para pesquisar")
    async def play(self, interaction: Interaction, musica: str) -> None:
        await interaction.response.defer(ephemeral=True)
        player = await self._preparar_player(interaction)
        if player is None:
            return

        musicas = await self.bot.youtube.buscar(musica, str(interaction.user))
        if not musicas:
            await interaction.followup.send("Não encontrei nenhuma música com esse link/termo.")
            return

        await player.adicionar_e_tocar_se_ocioso(musicas)

        if len(musicas) == 1:
            await interaction.followup.send(f"Adicionado à fila: {musicas[0].nome}")
        else:
            await interaction.followup.send(f"{len(musicas)} músicas adicionadas à fila.")

    @play.autocomplete("musica")
    async def autocomplete_musica(self, interaction: Interaction, atual: str) -> list[app_commands.Choice[str]]:
        if len(atual) < 2 or atual.startswith("http"):
            return []

        sugestoes = await self.bot.youtube.sugestoes(atual)
        return [
            app_commands.Choice(name=titulo[:100], value=url[:100])
            for titulo, url in sugestoes
        ]

    @app_commands.command(name="proximo", description="Pula para a próxima música da fila")
    async def proximo(self, interaction: Interaction) -> None:
        if not interaction.guild:
            return

        player = self.bot.obter_player(interaction.guild.id)
        if not player.tocando_ou_pausado():
            await interaction.response.send_message("Não tem nada tocando agora.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await player.pular()
        await interaction.followup.send("Música pulada.")

    @app_commands.command(name="anterior", description="Volta para a música anterior da fila")
    async def anterior(self, interaction: Interaction) -> None:
        if not interaction.guild:
            return

        player = self.bot.obter_player(interaction.guild.id)
        await interaction.response.defer(ephemeral=True)
        musica = await player.voltar()

        if musica is None:
            await interaction.followup.send("Não tem música anterior no histórico.")
            return

        await interaction.followup.send("Voltando para a música anterior.")

    @app_commands.command(name="fila", description="Mostra as próximas músicas da fila")
    async def fila(self, interaction: Interaction) -> None:
        if not interaction.guild:
            return

        player = self.bot.obter_player(interaction.guild.id)
        await interaction.response.send_message(player.mensagem_fila(QTD_PROXIMAS_EXIBIDAS), ephemeral=True)

    @app_commands.command(name="embaralhar", description="Embaralha a ordem das próximas músicas da fila")
    async def embaralhar(self, interaction: Interaction) -> None:
        if not interaction.guild:
            return

        player = self.bot.obter_player(interaction.guild.id)
        embaralhou = await player.embaralhar()

        if not embaralhou:
            await interaction.response.send_message("A fila está vazia, não tem o que embaralhar.", ephemeral=True)
            return

        await interaction.response.send_message("Fila embaralhada.", ephemeral=True)

    @app_commands.command(name="inverter", description="Inverte a ordem das próximas músicas da fila")
    async def inverter(self, interaction: Interaction) -> None:
        if not interaction.guild:
            return

        player = self.bot.obter_player(interaction.guild.id)
        inverteu = await player.inverter()

        if not inverteu:
            await interaction.response.send_message("A fila está vazia, não tem o que inverter.", ephemeral=True)
            return

        await interaction.response.send_message("Fila invertida.", ephemeral=True)

    @app_commands.command(name="lista", description="Mostra a fila completa de músicas")
    async def lista(self, interaction: Interaction) -> None:
        if not interaction.guild:
            return

        player = self.bot.obter_player(interaction.guild.id)
        await interaction.response.send_message(player.mensagem_lista_completa(), ephemeral=True)

    @app_commands.command(name="pular_para", description="Pula direto para uma música específica da fila")
    @app_commands.describe(posicao="Número da música na fila (veja com /lista)")
    async def pular_para(self, interaction: Interaction, posicao: int) -> None:
        if not interaction.guild:
            return

        player = self.bot.obter_player(interaction.guild.id)
        await interaction.response.defer(ephemeral=True)
        musica = await player.pular_para(posicao)

        if musica is None:
            await interaction.followup.send("Não tem música nessa posição da fila.")
            return

        await interaction.followup.send(f"Pulando para: {musica.nome}")

    @app_commands.command(name="stop", description="Para a música, limpa a fila e desconecta o bot do canal de voz")
    async def stop(self, interaction: Interaction) -> None:
        if not interaction.guild:
            return

        player = self.bot.obter_player(interaction.guild.id)
        if not player.conectado():
            await interaction.response.send_message("O bot não está conectado a nenhum canal de voz.", ephemeral=True)
            return

        await player.parar()
        await interaction.response.send_message("Bot desconectado e fila limpa.")

    async def _tocar_playlist(self, interaction: Interaction, nome_playlist: str) -> None:
        await interaction.response.defer(ephemeral=True)
        player = await self._preparar_player(interaction)
        if player is None:
            return

        links = carregar_playlist(nome_playlist)
        if not links:
            await interaction.followup.send(f'A playlist "{nome_playlist}" está vazia.')
            return

        usuario = str(interaction.user)
        musicas: list[Musica] = []
        for link in links:
            musicas.extend(await self.bot.youtube.buscar(link, usuario))

        if not musicas:
            await interaction.followup.send(f'Não consegui carregar nenhuma música da playlist "{nome_playlist}".')
            return

        await player.adicionar_e_tocar_se_ocioso(musicas)
        await interaction.followup.send(f'{len(musicas)} música(s) da playlist "{nome_playlist}" adicionada(s) à fila.')

    def criar_comando_playlist(self, nome_playlist: str) -> Callable[[Interaction], Coroutine[Any, Any, None]]:
        async def comando(interaction: Interaction) -> None:
            await self._tocar_playlist(interaction, nome_playlist)

        return comando
