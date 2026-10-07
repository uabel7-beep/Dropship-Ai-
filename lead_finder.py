import asyncio
import re
from urllib.parse import quote_plus
import requests

from config import GOOGLE_PLACES_API_KEY, HUNTER_SEARCH_TIMEOUT, HUNTER_MAX_RESULTS

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
GOOGLE_URL = "https://places.googleapis.com/v1/places:searchText"
UA = "HunterAI/4.0 (personal business lead research bot)"

# Hunter ne demande plus à l'utilisateur de connaître la niche du prospect.
# Il part de l'offre et élargit automatiquement la recherche vers plusieurs
# catégories de prospects plausibles.
OFFER_MAP = {
    "telephone": ["phone shop", "mobile phone store", "electronics store", "phone repair shop", "mobile phone accessories"],
    "téléphone": ["phone shop", "mobile phone store", "electronics store", "phone repair shop", "mobile phone accessories"],
    "smartphone": ["phone shop", "mobile phone store", "electronics store", "phone repair shop", "mobile phone accessories"],
    "iphone": ["iPhone store", "mobile phone store", "electronics store", "phone repair shop", "phone accessories"],
    "samsung": ["Samsung phone store", "mobile phone store", "electronics store", "phone repair shop"],
    "ordinateur": ["computer store", "electronics store", "computer repair shop", "IT store", "office equipment store"],
    "laptop": ["computer store", "electronics store", "computer repair shop", "IT store"],
    "vetement": ["clothing store", "fashion boutique", "shoe store", "fashion retailer", "clothing wholesaler"],
    "vêtement": ["clothing store", "fashion boutique", "shoe store", "fashion retailer", "clothing wholesaler"],
    "chaussure": ["shoe store", "fashion boutique", "sportswear store", "clothing store"],
    "parfum": ["perfume store", "cosmetics store", "beauty store", "beauty salon", "pharmacy"],
    "cosmetique": ["cosmetics store", "beauty store", "beauty salon", "pharmacy"],
    "cosmétique": ["cosmetics store", "beauty store", "beauty salon", "pharmacy"],
    "montage": ["restaurant", "hotel", "fashion store", "real estate agency", "local business"],
    "marketing": ["restaurant", "hotel", "retail store", "real estate agency", "local business"],
    "site web": ["restaurant", "hotel", "retail store", "real estate agency", "local business"],
    "application": ["business", "startup", "company", "retail store", "service business"],
    "formation": ["school", "training center", "company", "business center", "professional services"],
}

DEFAULT_QUERIES = [
    "retail store", "local business", "electronics store", "shop", "company"
]


def _clean_offer(offer):
    text = (offer or "").lower().strip()
    text = re.sub(r"\b(je|j'|j|nous|on)\b", " ", text)
    text = re.sub(r"\b(vends|vend|vendre|propose|proposons|commercialise|commercialiser)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def infer_prospect_queries(offer):
    """Transforme une offre libre en plusieurs catégories de prospects."""
    clean = _clean_offer(offer)
    found = []
    for key, queries in OFFER_MAP.items():
        if key in clean:
            found.extend(queries)
    if not found:
        tokens = [t for t in re.findall(r"[\wÀ-ÿ]+", clean) if len(t) >= 3]
        # Pour une offre inconnue, on conserve le produit/service et on ajoute
        # des catégories larges plutôt que de demander à l'utilisateur de cibler.
        if tokens:
            phrase = " ".join(tokens[:5])
            found = [phrase, f"{phrase} store", f"{phrase} retailer", "retail store", "local business"]
        else:
            found = DEFAULT_QUERIES[:]
    unique = []
    seen = set()
    for q in found:
        q = q.strip()
        if q and q.lower() not in seen:
            unique.append(q)
            seen.add(q.lower())
    return unique[:6]


def infer_buyer_profile(offer, queries):
    if len(queries) <= 3:
        return ", ".join(queries)
    return ", ".join(queries[:4]) + " et autres acheteurs professionnels"


def _score(place, query):
    score = 35
    if place.get("website") or place.get("phone"):
        score += 20
    reviews = int(place.get("review_count") or 0)
    rating = float(place.get("rating") or 0)
    score += min(25, reviews // 20)
    score += min(15, int(rating * 3))
    if place.get("business_status") in (None, "OPERATIONAL"):
        score += 5
    return max(0, min(100, score))


def _google_sync(queries, city, limit):
    out, seen = [], set()
    for query in queries:
        location_suffix = f" in {city}" if city else ""
        body = {"textQuery": f"{query}{location_suffix}", "pageSize": min(limit, 20), "languageCode": "fr"}
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.websiteUri,places.nationalPhoneNumber,places.rating,places.userRatingCount,places.businessStatus",
        }
        r = requests.post(GOOGLE_URL, json=body, headers=headers, timeout=HUNTER_SEARCH_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        for x in data.get("places", []):
            place_id = x.get("id", "")
            if place_id in seen:
                continue
            seen.add(place_id)
            name = (x.get("displayName") or {}).get("text") or "Entreprise"
            out.append({
                "name": name, "platform": "Google Maps", "contact": x.get("nationalPhoneNumber") or x.get("websiteUri") or "",
                "phone": x.get("nationalPhoneNumber") or "", "website": x.get("websiteUri") or "",
                "address": x.get("formattedAddress") or "", "rating": x.get("rating"),
                "review_count": x.get("userRatingCount", 0), "business_status": x.get("businessStatus"),
                "external_id": place_id, "source": "google_places",
                "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus(name + ' ' + (x.get('formattedAddress') or ''))}",
                "niche": query,
            })
            if len(out) >= limit:
                return out
    for x in out:
        x["score"] = _score(x, x.get("niche", ""))
    return out


def _geocode_sync(city):
    r = requests.get(NOMINATIM_URL, params={"q": city, "format": "jsonv2", "limit": 1}, headers={"User-Agent": UA}, timeout=HUNTER_SEARCH_TIMEOUT)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        raise ValueError("Ville introuvable")
    row = rows[0]
    return float(row["lat"]), float(row["lon"]), row.get("display_name", city)


def _osm_sync(queries, city, limit):
    lat, lon, display = _geocode_sync(city)
    delta = 0.12
    south, north, west, east = lat - delta, lat + delta, lon - delta, lon + delta
    tag_map = {
        "restaurant": 'nwr["amenity"="restaurant"]', "hotel": 'nwr["tourism"="hotel"]',
        "phone shop": 'nwr["shop"="mobile_phone"]', "mobile phone store": 'nwr["shop"="mobile_phone"]',
        "electronics store": 'nwr["shop"="electronics"]', "computer store": 'nwr["shop"="computer"]',
        "clothing store": 'nwr["shop"="clothes"]', "shoe store": 'nwr["shop"="shoes"]',
        "pharmacy": 'nwr["amenity"="pharmacy"]', "beauty salon": 'nwr["shop"="beauty"]',
        "perfume store": 'nwr["shop"="beauty"]', "retail store": 'nwr["shop"]',
        "local business": 'nwr["name"]', "shop": 'nwr["shop"]',
    }
    blocks = [tag_map[q] for q in queries if q in tag_map]
    if not blocks:
        blocks = ['nwr["name"]']
    query_parts = [f"{b}({south},{west},{north},{east});" for b in blocks[:6]]
    ql = "[out:json][timeout:25];(" + "".join(query_parts) + ");out center tags;"
    r = requests.post(OVERPASS_URL, data=ql, headers={"User-Agent": UA}, timeout=HUNTER_SEARCH_TIMEOUT + 12)
    r.raise_for_status()
    out, seen = [], set()
    for x in r.json().get("elements", []):
        tags = x.get("tags", {})
        name = tags.get("name") or tags.get("brand")
        key = f"{x.get('type')}:{x.get('id')}"
        if not name or key in seen:
            continue
        seen.add(key)
        website = tags.get("website") or tags.get("contact:website") or ""
        phone = tags.get("phone") or tags.get("contact:phone") or ""
        address = " ".join(filter(None, [tags.get("addr:housenumber"), tags.get("addr:street"), tags.get("addr:city")]))
        out.append({
            "name": name, "platform": "OpenStreetMap", "contact": phone or website,
            "phone": phone, "website": website, "address": address or display,
            "rating": None, "review_count": 0, "business_status": "OPERATIONAL",
            "external_id": f"osm:{key}", "source": "openstreetmap",
            "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus(name + ' ' + (address or display))}",
            "niche": " / ".join(queries[:3]),
        })
        if len(out) >= limit:
            break
    for x in out:
        x["score"] = _score(x, x.get("niche", ""))
    return out


def _osm_global_sync(queries, limit):
    """Fallback sans ville : quelques recherches Nominatim par catégorie.
    Ce n'est pas un annuaire mondial exhaustif; il sert de secours quand
    Google Places n'est pas configuré."""
    out, seen = [], set()
    for query in queries[:5]:
        r = requests.get(
            NOMINATIM_URL,
            params={"q": query, "format": "jsonv2", "limit": max(3, min(8, limit))},
            headers={"User-Agent": UA}, timeout=HUNTER_SEARCH_TIMEOUT,
        )
        r.raise_for_status()
        for x in r.json():
            osm_id = f"{x.get('osm_type')}:{x.get('osm_id')}"
            name = (x.get("display_name") or "").split(",")[0].strip()
            if not name or osm_id in seen:
                continue
            seen.add(osm_id)
            address = x.get("display_name") or ""
            out.append({
                "name": name, "platform": "OpenStreetMap", "contact": "", "phone": "", "website": "",
                "address": address, "rating": None, "review_count": 0, "business_status": "OPERATIONAL",
                "external_id": f"nominatim:{osm_id}", "source": "nominatim",
                "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus(name + ' ' + address)}",
                "niche": query, "score": 40,
            })
            if len(out) >= limit:
                return out
    return out


async def find_leads(offer, city="", limit=20):
    limit = max(1, min(int(limit), HUNTER_MAX_RESULTS))
    queries = infer_prospect_queries(offer)
    if GOOGLE_PLACES_API_KEY:
        try:
            return await asyncio.to_thread(_google_sync, queries, city.strip(), limit), "google_places", queries
        except Exception as exc:
            google_error = str(exc)
    else:
        google_error = "Clé Google Places non configurée"

    if city.strip():
        try:
            results = await asyncio.to_thread(_osm_sync, queries, city.strip(), limit)
            return results, "openstreetmap", queries
        except Exception as exc:
            osm_error = str(exc)
    else:
        try:
            results = await asyncio.to_thread(_osm_global_sync, queries, limit)
            if results:
                return results, "nominatim", queries
            osm_error = "Aucun résultat global"
        except Exception as exc:
            osm_error = str(exc)

    raise RuntimeError(f"Google Places: {google_error} | Recherche publique: {osm_error}")
