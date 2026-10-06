import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / "token.env", override=False)
load_dotenv(BASE_DIR / ".env", override=False)

# Conservés exactement comme dans ton projet actuel.
BOT_TOKEN = "8721671832:AAF3os33FXhMIZ_sHt_FDUjKJWSnM8VipfA"
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
