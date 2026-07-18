from discord import Intents, Interaction
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

class rod_bot(commands.Bot):
    
    def __init__(self,) -> None:
        intents = Intents.all()
        super().__init__(intents = intents, command_prefix = "$")

    async def setup_hook(self) -> None:
        await self.tree.sync()

    async def on_ready(self, ):
        print(f"o bot {self.user} foi ligado com sucesso!")

def main():
    bot_rod = rod_bot()

    @bot_rod.tree.command(name =  "olá-mundo", description = "primeiro comando do bot")
    async def ola_mundo(interaction: Interaction) -> None:
        await interaction.response.send_message(f"olá {interaction.user.mention}!!")
    
    bot_rod.run(token = os.environ["TOKEN"])

if __name__ == "__main__":
    main()
