import os
import re
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / "token.env", override=False)
load_dotenv(BASE_DIR / ".env", override=False)

# Conservés exactement comme dans ton projet actuel.
_raw_bot_token = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or ""
# Render/secret managers can accidentally preserve a pasted line break or spaces.
# Extract only a valid Telegram bot-token-shaped value so the HTTP URL never
# contains non-printable characters.
_match = re.search(r"\b(\d{6,20}:[A-Za-z0-9_-]{20,})\b", _raw_bot_token)
BOT_TOKEN = _match.group(1) if _match else re.sub(r"\s+", "", _raw_bot_token).strip().strip('\"\'')
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "8519505699"))
except ValueError:
    ADMIN_ID = 8519505699

DB_NAME = os.getenv("DROPSHIP_DB", "dropship_ai.db")
MAX_PRODUCT_NAME_LENGTH = 120
MAX_PRODUCTS_TO_SHOW = 10

# Optional live Product Hunter settings. Leave empty until API access is available.
REEF_API_KEY = os.getenv("REEF_API_KEY", "")
REEF_API_BASE_URL = os.getenv("REEF_API_BASE_URL", "https://api.reefapi.com")

# Profit Engine assumptions (kept simple and visible in the code).
AD_COST_RATE = 0.15
PLATFORM_FEE_RATE = 0.05
LIVE_SEARCH_TIMEOUT = 18
LIVE_DETAIL_TIMEOUT = 15

# Hunter AI lead discovery. Google Places is optional; without a key, Hunter
# uses OpenStreetMap/Overpass for low-volume public business discovery.
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
HUNTER_SEARCH_TIMEOUT = 15
HUNTER_MAX_RESULTS = 20

# Cinexa AI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
CINEXA_TEXT_MODEL = os.getenv("CINEXA_TEXT_MODEL", "gpt-6-luna")
CINEXA_IMAGE_MODEL = os.getenv("CINEXA_IMAGE_MODEL", "gpt-image-2.5-flare")
CINEXA_TTS_MODEL = os.getenv("CINEXA_TTS_MODEL", "gpt-4o-mini-tts")
CINEXA_OUTPUT_DIR = os.getenv("CINEXA_OUTPUT_DIR", str(BASE_DIR / "cinexa_output"))
