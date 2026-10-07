# DROPSHIP AI — Render deployment

## Runtime
This project includes a Dockerfile because Cinexa AI needs FFmpeg. Deploy it as a **Background Worker using Docker**.

## Environment variables
Add these in Render:

- `BOT_TOKEN` = Telegram bot token
- `ADMIN_ID` = your Telegram numeric user ID (the included default is the existing project admin ID)
- `OPENAI_API_KEY` = OpenAI API key
- `REEF_API_KEY` = ReefAPI key
- `GOOGLE_PLACES_API_KEY` = Google Places API key
- `REEF_API_BASE_URL` = `https://api.reefapi.com`
- `CINEXA_TEXT_MODEL` = `gpt-6-luna`
- `CINEXA_IMAGE_MODEL` = `gpt-image-2.5-flare`
- `CINEXA_TTS_MODEL` = `gpt-4o-mini-tts`

The code also accepts `TELEGRAM_TOKEN` as a fallback for the Telegram token, but `BOT_TOKEN` is recommended.

## Important
Do **not** upload `token.env` to GitHub or Render. Secrets belong in Render Environment Variables. The fixed package intentionally does not contain the original `token.env`.

## Start
The Dockerfile installs Python dependencies and FFmpeg, then runs `python main.py`.

## Data persistence
The project currently uses SQLite. On a disposable container filesystem, database data can be lost after a replacement/redeploy. If you need the prospect/product history to survive restarts, configure a persistent disk or move the database to a managed PostgreSQL database.
