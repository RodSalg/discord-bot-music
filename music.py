import os

from dotenv import load_dotenv

from musica.bot import MusicBot

load_dotenv()


def main() -> None:
    bot = MusicBot()
    bot.run(token=os.environ["TOKEN"])


if __name__ == "__main__":
    main()
