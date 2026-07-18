import discord
from discord import Intents
from discord.ext import commands

from .cog import MusicCog
from .config import MUSICAS_PATH
from .historico import HistoricoStorage
from .player import GuildPlayer
from .playlists import listar_playlists
from .youtube import YoutubeService


class MusicBot(commands.Bot):

    def __init__(self) -> None:
        intents = Intents.default()
        intents.message_content = True
        super().__init__(intents=intents, command_prefix="$")

        self.youtube = YoutubeService()
        self.historico = HistoricoStorage(MUSICAS_PATH)
        self._players: dict[int, GuildPlayer] = {}

    def obter_player(self, guild_id: int) -> GuildPlayer:
        player = self._players.get(guild_id)
        if player is None:
            player = GuildPlayer(self.loop, self.youtube, self.historico)
            self._players[guild_id] = player
        return player

    async def setup_hook(self) -> None:
        cog = MusicCog(self)
        await self.add_cog(cog)

        for nome in listar_playlists():
            self.tree.command(
                name=f"{nome}_playlist",
                description=f'Toca a playlist "{nome}"',
            )(cog.criar_comando_playlist(nome))

        await self.tree.sync()

    async def on_ready(self) -> None:
        print(f"o bot {self.user} está pronto para tocar!")

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if self.user is None or member.id != self.user.id:
            return

        if before.channel is not None and after.channel is None:
            player = self._players.get(member.guild.id)
            if player is not None:
                await player.desconectado_externamente()
