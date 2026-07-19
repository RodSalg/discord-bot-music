# discord-bot-music

Discord bot with two entry points:

- `main.py` - base bot with a sample slash command.
- `music.py` - entry point for the music bot; the actual logic lives in the `musica/` package.

## Music bot structure

`music.py` only creates the bot and runs it (`bot.run(...)`). All the logic is split across `musica/`, one responsibility per file:

| File | Responsibility |
| --- | --- |
| `musica/config.py` | Constants (ffmpeg options, yt-dlp options, `musicas.json` path, limits) |
| `musica/modelos.py` | `Musica` - dataclass with `url`, `nome`, `usuario` |
| `musica/youtube.py` | `YoutubeService` - search (`buscar`, accepts playlists/mixes) and resolve (`resolver`) links via yt-dlp |
| `musica/fila.py` | `FilaDeReproducao` - upcoming songs queue plus history (used by `/anterior`) |
| `musica/historico.py` | `HistoricoStorage` - reads/writes `musicas.json` |
| `musica/player.py` | `GuildPlayer` - connects the queue to a server's `VoiceClient`: connect, play, skip, go back, pause, stop, build the embed |
| `musica/ui.py` | `PlayerControls` - the buttons (previous, pause/resume, next, stop) attached to the "Now playing" message |
| `musica/playlists.py` | Reads the `playlists/` folder (`listar_playlists`, `carregar_playlist`) |
| `musica/cog.py` | `MusicCog` - the slash commands (`/play`, `/proximo`, `/anterior`, `/fila`, `/stop`) and the playlist command handler |
| `musica/bot.py` | `MusicBot` - the bot class (`commands.Bot`), keeps one `GuildPlayer` per server and registers one command per playlist |

## Requirements

- Python 3.13+ (already pinned in `.python-version`)
- [uv](https://docs.astral.sh/uv/) installed
- ffmpeg installed and on the system PATH (only needed for `music.py`)

## Setup from scratch

### 1. Install the Python dependencies

From the `discord-proj` folder, run:

```
uv sync
```

This reads `pyproject.toml` / `uv.lock` and installs everything into `.venv`, including:

- `discord-py` - the bot library
- `python-dotenv` - loads the token from the `.env` file
- `yt-dlp` - extracts audio from YouTube
- `pynacl` - required for discord.py to use voice
- `davey` - required for discord.py to use voice (call encryption protocol)
- `pandas` - dependency of `main.py`

If any of these packages is missing from `pyproject.toml`, add it with:

```
uv add package-name
```

### 2. Configure the bot token

Create/edit the `.env` file at the root of `discord-proj` with:

```
TOKEN=your_token_here
```

The token is generated in the [Discord Developer Portal](https://discord.com/developers/applications), under the "Bot" tab of your application. `.env` is gitignored and must never be committed.

### 3. Install ffmpeg (music bot only)

`music.py` uses `ffmpeg` to process audio before sending it to the voice channel. On Windows, install it with:

```
winget install --id=Gyan.FFmpeg -e
```

After installing, **close and reopen your terminal** (PATH only updates in a new session).

Confirm it worked with:

```
ffmpeg -version
```

### 4. Run the bot

Base bot:

```
uv run python main.py
```

Music bot:

```
uv run python music.py
```

(or `python music.py` / `python main.py` if `.venv` is already active in the terminal)

## Using the music bot

`music.py` uses slash commands (tree), same as `main.py`, and keeps a per-server song queue. Available commands:

| Command | Parameter | Description |
| --- | --- | --- |
| `/play` | `musica` - YouTube link (video, playlist or mix) or a song name to search for | Joins the user's voice channel (if not already connected) and plays the song; if something is already playing, adds it to the queue |
| `/proximo` | - | Skips the current song and plays the next one in the queue |
| `/anterior` | - | Goes back and plays the previous song (uses the history of already-played songs) |
| `/fila` | - | Shows the next songs in the queue (up to 10, plus a remaining count) |
| `/embaralhar` | - | Shuffles the order of the upcoming songs in the queue |
| `/stop` | - | Stops the current song, clears the queue and disconnects the bot from the voice channel |

Basic flow:

1. Join a voice channel on the server.
2. Type `/play`, fill in the `musica` parameter with a link or a song name, and send it.
3. Run `/play` again with another link/name to add more songs to the queue - they play one after another automatically.
4. Use `/proximo` to skip forward, `/anterior` to go back, `/fila` to see what is coming up, `/embaralhar` to shuffle it, and `/stop` to end and clear everything.

While typing a song name (not a link) in the `musica` parameter of `/play`, Discord shows up to 10 YouTube search suggestions to pick from, once you have typed at least 2 characters.

Every time a song starts playing (via `/play`, `/proximo`, `/anterior`, or because the previous one just ended), the bot sends a "Now playing" embed in the channel with the song's thumbnail, who requested it, the next 10 songs in the queue (configurable via the `QTD_PROXIMAS_EXIBIDAS` constant in `musica/config.py`), and a row of buttons:

- previous - goes back to the previous song
- pause/resume - pauses and resumes the current song (the icon switches automatically)
- next - skips to the next song in the queue
- shuffle - shuffles the upcoming songs in the queue and refreshes the queue preview in the embed
- stop - stops everything, clears the queue and disconnects the bot

When a new song starts, the buttons on the previous message are disabled - only the most recent message stays interactive.

If the bot gets disconnected from the voice channel from the outside (someone kicked it, moved it, deleted the channel, connection dropped, etc.) - that is, without going through `/stop` or the stop button - the bot detects this (`on_voice_state_update` in `musica/bot.py`) and clears the queue on its own, announcing it in the text channel.

### Ready-made playlists (`playlists/`)

Besides `/play`, the bot creates one slash command per `.json` file inside the `playlists/` folder at the project root. Currently there are:

- `playlists/laffayate.json` -> `/laffayate_playlist`
- `playlists/kayrex.json` -> `/kayrex_playlist`
- `playlists/rod.json` -> `/rod_playlist`

Each file is a plain list of YouTube links, for example:

```json
[
  "https://www.youtube.com/watch?v=vIaH35-MLsk",
  "https://www.youtube.com/watch?v=WuDFz4MgEgw"
]
```

Running the command (e.g. `/laffayate_playlist`) adds every link in the file to the queue at once, in the order they appear in the JSON.

To add a song to an existing playlist, just open the `.json` file and add the new link to the list - the bot reads the file every time the command is used, so there is no need to restart the bot.

To create a new playlist (for a new person, for example), create a `playlists/name.json` file with a list of links (it can start empty, `[]`) and **restart the bot** - command registration (`/name_playlist`) happens on startup, so only new files require a restart; editing an existing file does not.

### YouTube playlists and mixes (direct link in `/play`)

If the `/play` link is a YouTube playlist or mix/radio (`.../watch?v=...&list=RD...`), the bot fetches the items from the link and adds all of them to the queue at once (limit of 50 items, configurable via the `MAX_ITENS_PLAYLIST` constant in `musica/config.py` - YouTube mixes are effectively endless, so a cap is needed). Each song is only resolved (its real audio link fetched) right before it plays, so adding a large playlist to the queue is fast. Use `/anterior` and `/proximo` to move through the playlist.

If the slash commands do not show up right away, wait for Discord to sync (`setup_hook` calls `tree.sync()` every time the bot starts) or restart the Discord client.

### Song history (`musicas.json`)

Every time a song actually starts playing (left the queue and reached the voice channel), the bot saves a record in `musicas.json` (created at the root of `discord-proj` the first time someone uses the command). Each entry has:

```json
{
  "usuario": "name#0000",
  "link": "the song's own URL, even if it came from a playlist/mix",
  "nome": "song title found by yt-dlp"
}
```

If yt-dlp cannot find a title, the `nome` field falls back to the same value as `link`.

## Common issues

- `RuntimeError: PyNaCl library needed in order to use voice` -> run `uv add pynacl`.
- `RuntimeError: davey library needed in order to use voice` -> run `uv add davey`.
- `discord.errors.ClientException: ffmpeg was not found.` -> install ffmpeg (step 3) and open a new terminal.
- Bot does not read messages -> confirm the "Message Content Intent" option is enabled in the Developer Portal, under Bot > Privileged Gateway Intents.
