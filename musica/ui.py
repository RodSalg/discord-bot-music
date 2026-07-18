from typing import TYPE_CHECKING

import discord
from discord import Interaction

if TYPE_CHECKING:
    from .player import GuildPlayer


class PlayerControls(discord.ui.View):

    def __init__(self, player: "GuildPlayer") -> None:
        super().__init__(timeout=None)
        self._player = player

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary)
    async def anterior(self, interaction: Interaction, _botao: discord.ui.Button) -> None:
        await interaction.response.defer()
        await self._player.voltar()

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.primary)
    async def pausar_retomar(self, interaction: Interaction, botao: discord.ui.Button) -> None:
        if self._player.esta_pausado():
            self._player.retomar()
            botao.emoji = "⏸️"
        else:
            self._player.pausar()
            botao.emoji = "▶️"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def proximo(self, interaction: Interaction, _botao: discord.ui.Button) -> None:
        await interaction.response.defer()
        await self._player.pular()

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger)
    async def parar(self, interaction: Interaction, _botao: discord.ui.Button) -> None:
        await interaction.response.defer()
        await self._player.parar()
