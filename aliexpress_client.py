import hashlib
import os
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

import requests

API_URL = os.getenv("ALIEXPRESS_API_URL", "https://eco.taobao.com/router/rest")


class AliExpressAPIError(RuntimeError):
    pass


def configured():
    return bool(os.getenv("ALIEXPRESS_APP_KEY") and os.getenv("ALIEXPRESS_APP_SECRET"))


def _sign(params, secret):
    # TOP MD5 signature: secret + sorted key/value pairs + secret.
    raw = "".join(f"{k}{params[k]}" for k in sorted(params))
    return hashlib.md5((secret + raw + secret).encode("utf-8")).hexdigest().upper()


def search_products(
    keywords,
    *,
    page_no=1,
    page_size=20,
    ship_to_country="CD",
    min_price=None,
    max_price=None,
    target_currency="USD",
):
    if not configured():
        raise AliExpressAPIError(
            "API AliExpress non configurée. Ajoute ALIEXPRESS_APP_KEY et "
            "ALIEXPRESS_APP_SECRET dans token.env."
        )

    keywords = (keywords or "").strip()
    if not keywords:
        raise ValueError("Le mot-clé est obligatoire.")
    if len(keywords) > 80:
        raise ValueError("Le mot-clé est trop long.")

    app_key = os.getenv("ALIEXPRESS_APP_KEY")
    secret = os.getenv("ALIEXPRESS_APP_SECRET")
    tracking_id = os.getenv("ALIEXPRESS_TRACKING_ID", "dropship_ai")

    # UTC+8 is the timestamp convention documented by TOP.
    timestamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")

    params = {
        "app_key": app_key,
        "format": "json",
        "method": "aliexpress.affiliate.product.query",
        "partner_id": "dropship_ai",
        "sign_method": "md5",
        "timestamp": timestamp,
        "v": "2.0",
        "fields": (
            "app_sale_price,app_sale_price_currency,commission_rate,discount,"
            "evaluate_rate,lastest_volume,product_detail_url,product_id,"
            "product_main_image_url,product_title,promotion_link,sale_price,"
            "sale_price_currency,shop_id,shop_url"
        ),
        "keywords": keywords,
        "page_no": str(max(1, int(page_no))),
        "page_size": str(min(50, max(1, int(page_size)))),
        "sort": "LAST_VOLUME_DESC",
        "target_currency": (target_currency or "USD").upper(),
        "target_language": "EN",
        "tracking_id": tracking_id,
        "ship_to_country": ship_to_country.upper(),
    }

    if min_price is not None:
        params["min_sale_price"] = str(min_price)
    if max_price is not None:
        params["max_sale_price"] = str(max_price)

    params["sign"] = _sign(params, secret)

    response = requests.post(API_URL, data=params, timeout=20)
    response.raise_for_status()
    data = response.json()

    root = data.get("aliexpress_affiliate_product_query_response", {})
    result = root.get("resp_result", {})
    if str(result.get("resp_code")) not in {"200", "0"}:
        raise AliExpressAPIError(result.get("resp_msg") or "Réponse API invalide.")

    products = result.get("result", {}).get("products", {}).get("product", []) or []
    if isinstance(products, dict):
        products = [products]

    return products
