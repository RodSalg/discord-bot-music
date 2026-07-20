from typing import TYPE_CHECKING

import discord
from discord import Interaction

if TYPE_CHECKING:
    from .player import GuildPlayer

SALTO_TEMPO = 10


class ModalPularPara(discord.ui.Modal, title="Pular para uma música"):

    posicao: discord.ui.TextInput["ModalPularPara"] = discord.ui.TextInput(
        label="Número da música na fila",
        placeholder="Veja o número com o botão Lista. Ex: 7",
        max_length=4,
    )

    def __init__(self, player: "GuildPlayer") -> None:
        super().__init__()
        self._player = player

    async def on_submit(self, interaction: Interaction) -> None:
        texto = self.posicao.value.strip()
        if not texto.isdigit():
            await interaction.response.send_message("Digite um número válido.", ephemeral=True)
            return

        musica = await self._player.pular_para(int(texto))
        if musica is None:
            await interaction.response.send_message("Não tem música nessa posição da fila.", ephemeral=True)
            return

        await interaction.response.send_message(f"Pulando para: {musica.nome}", ephemeral=True)


class PlayerControls(discord.ui.View):

    def __init__(self, player: "GuildPlayer") -> None:
        super().__init__(timeout=None)
        self._player = player

    @discord.ui.button(emoji="🔀", label="Embaralhar", style=discord.ButtonStyle.secondary, row=0)
    async def embaralhar(self, interaction: Interaction, _botao: discord.ui.Button["PlayerControls"]) -> None:
        await interaction.response.defer()
        await self._player.embaralhar()

    @discord.ui.button(emoji="⏮️", label="Anterior", style=discord.ButtonStyle.secondary, row=0)
    async def anterior(self, interaction: Interaction, _botao: discord.ui.Button["PlayerControls"]) -> None:
        await interaction.response.defer()
        await self._player.voltar()

    @discord.ui.button(emoji="⏸️", label="Pausar", style=discord.ButtonStyle.primary, row=0)
    async def pausar_retomar(self, interaction: Interaction, botao: discord.ui.Button["PlayerControls"]) -> None:
        if self._player.esta_pausado():
            self._player.retomar()
            botao.emoji = "⏸️"
            botao.label = "Pausar"
        else:
            self._player.pausar()
            botao.emoji = "▶️"
            botao.label = "Retomar"

        embed = self._player.embed_atual()
        if embed is not None:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="⏭️", label="Próximo", style=discord.ButtonStyle.secondary, row=0)
    async def proximo(self, interaction: Interaction, _botao: discord.ui.Button["PlayerControls"]) -> None:
        await interaction.response.defer()
        await self._player.pular()

    @discord.ui.button(emoji="⏹️", label="Parar", style=discord.ButtonStyle.danger, row=0)
    async def parar(self, interaction: Interaction, _botao: discord.ui.Button["PlayerControls"]) -> None:
        await interaction.response.defer()
        await self._player.parar()

    @discord.ui.button(emoji="⏪", label="-10s", style=discord.ButtonStyle.secondary, row=1)
    async def retroceder(self, interaction: Interaction, _botao: discord.ui.Button["PlayerControls"]) -> None:
        await interaction.response.defer()
        await self._player.retroceder_tempo(SALTO_TEMPO)

    @discord.ui.button(emoji="⏩", label="+10s", style=discord.ButtonStyle.secondary, row=1)
    async def avancar(self, interaction: Interaction, _botao: discord.ui.Button["PlayerControls"]) -> None:
        await interaction.response.defer()
        await self._player.avancar_tempo(SALTO_TEMPO)

    @discord.ui.button(emoji="🔃", label="Inverter", style=discord.ButtonStyle.secondary, row=1)
    async def inverter(self, interaction: Interaction, _botao: discord.ui.Button["PlayerControls"]) -> None:
        await interaction.response.defer()
        await self._player.inverter()

    @discord.ui.button(emoji="📋", label="Lista", style=discord.ButtonStyle.secondary, row=1)
    async def ver_lista(self, interaction: Interaction, _botao: discord.ui.Button["PlayerControls"]) -> None:
        await interaction.response.send_message(self._player.mensagem_lista_completa(), ephemeral=True)

    @discord.ui.button(emoji="🎯", label="Ir para", style=discord.ButtonStyle.secondary, row=1)
    async def ir_para(self, interaction: Interaction, _botao: discord.ui.Button["PlayerControls"]) -> None:
        await interaction.response.send_modal(ModalPularPara(self._player))
