import os
from urllib.parse import urljoin

import requests

from config import REEF_API_KEY, REEF_API_BASE_URL

BASE_URL = REEF_API_BASE_URL
SEARCH_PATH = "/aliexpress/v1/search"
DETAIL_PATH = "/aliexpress/v1/product_detail"


class ReefAPIError(RuntimeError):
    pass


def configured():
    return bool(REEF_API_KEY.strip()) and REEF_API_KEY.strip() != "COLLE_TA_CLE_REEF_ICI"


def _request(path, payload, timeout=12):
    api_key = REEF_API_KEY.strip()
    if not api_key or api_key == "COLLE_TA_CLE_REEF_ICI":
        raise ReefAPIError("Clé ReefAPI manquante.")

    url = urljoin(BASE_URL.rstrip("/") + "/", path.lstrip("/"))
    try:
        response = requests.post(
            url,
            headers={
                "x-api-key": api_key,
                "content-type": "application/json",
                "accept": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
    except requests.Timeout as exc:
        raise ReefAPIError("ReefAPI met trop de temps à répondre.") from exc
    except requests.RequestException as exc:
        raise ReefAPIError("Connexion ReefAPI impossible.") from exc

    if response.status_code in (401, 403):
        raise ReefAPIError("Clé ReefAPI refusée.")
    if response.status_code == 429:
        raise ReefAPIError("Limite ReefAPI atteinte.")
    if not response.ok:
        raise ReefAPIError(f"ReefAPI indisponible ({response.status_code}).")

    try:
        body = response.json()
    except ValueError as exc:
        raise ReefAPIError("Réponse ReefAPI invalide.") from exc

    if not body.get("ok"):
        error = body.get("error") or {}
        if isinstance(error, dict):
            message = error.get("message") or error.get("code") or "Erreur API."
        else:
            message = str(error)
        raise ReefAPIError(f"ReefAPI : {message}")

    return body.get("data") or {}


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def search_products(keywords, *, page=1, max_results=20, country="US", currency="USD", min_price=None, max_price=None):
    keywords = (keywords or "").strip()
    if not keywords:
        raise ValueError("Mot-clé vide.")
    if len(keywords) > 80:
        raise ValueError("Mot-clé trop long.")

    payload = {
        "query": keywords,
        "country": (country or "US").upper(),
        "currency": (currency or "USD").upper(),
        "page": max(1, int(page)),
        "max_results": min(50, max(1, int(max_results))),
    }
    if min_price is not None:
        payload["min_price"] = float(min_price)
    if max_price is not None:
        payload["max_price"] = float(max_price)

    data = _request(SEARCH_PATH, payload, timeout=12)
    results = data.get("results") or []
    if not isinstance(results, list):
        raise ReefAPIError("Résultats ReefAPI inattendus.")

    normalized = []
    for item in results:
        if not isinstance(item, dict):
            continue
        if str(item.get("product_type") or "natural").lower() == "ad":
            continue

        price = _number(item.get("price"))
        if price <= 0:
            continue
        sold = int(_number(item.get("sold_count")))
        rating = _number(item.get("rating"))
        normalized.append({
            "product_title": str(item.get("title") or "").strip(),
            "app_sale_price": price,
            "sale_price": price,
            "lastest_volume": sold,
            "evaluate_rate": rating * 20,
            "commission_rate": 0,
            "product_id": str(item.get("product_id") or ""),
            "product_detail_url": item.get("url") or "",
            "product_main_image_url": item.get("image") or "",
            "promotion_link": item.get("url") or "",
            "source": "reefapi_aliexpress",
            "currency": item.get("currency") or currency,
            "original_price": item.get("original_price"),
            "discount_pct": item.get("discount_pct"),
            "sold_text": item.get("sold_text") or "",
            "sku_id": str(item.get("sku_id") or ""),
            "product_type": item.get("product_type") or "natural",
            "promo_tags": item.get("promo_tags") or [],
        })
    return normalized


def product_detail(product_id=None, url=None, country="US", currency="USD"):
    if not product_id and not url:
        raise ValueError("Produit introuvable.")
    payload = {"country": (country or "US").upper(), "currency": (currency or "USD").upper()}
    if product_id:
        payload["product_id"] = str(product_id)
    else:
        payload["url"] = url
    return _request(DETAIL_PATH, payload, timeout=12)
