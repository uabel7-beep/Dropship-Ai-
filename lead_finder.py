import asyncio
import re
from urllib.parse import quote_plus
import requests

from config import GOOGLE_PLACES_API_KEY, HUNTER_SEARCH_TIMEOUT, HUNTER_MAX_RESULTS

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
GOOGLE_URL = "https://places.googleapis.com/v1/places:searchText"
UA = "HunterAI/2.0 (personal business lead research bot)"


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


def _google_sync(query, city, limit):
    body = {"textQuery": f"{query} in {city}", "pageSize": min(limit, 20), "languageCode": "fr"}
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.websiteUri,places.nationalPhoneNumber,places.rating,places.userRatingCount,places.businessStatus",
    }
    r = requests.post(GOOGLE_URL, json=body, headers=headers, timeout=HUNTER_SEARCH_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    out = []
    for x in data.get("places", []):
        name = (x.get("displayName") or {}).get("text") or "Entreprise"
        place_id = x.get("id", "")
        out.append({
            "name": name, "platform": "Google Maps", "contact": x.get("nationalPhoneNumber") or x.get("websiteUri") or "",
            "phone": x.get("nationalPhoneNumber") or "", "website": x.get("websiteUri") or "",
            "address": x.get("formattedAddress") or "", "rating": x.get("rating"),
            "review_count": x.get("userRatingCount", 0), "business_status": x.get("businessStatus"),
            "external_id": place_id, "source": "google_places",
            "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus(name + ' ' + (x.get('formattedAddress') or ''))}",
        })
    for x in out:
        x["score"] = _score(x, query)
        x["niche"] = query
    return out


def _geocode_sync(city):
    r = requests.get(NOMINATIM_URL, params={"q": city, "format": "jsonv2", "limit": 1}, headers={"User-Agent": UA}, timeout=HUNTER_SEARCH_TIMEOUT)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        raise ValueError("Ville introuvable")
    row = rows[0]
    return float(row["lat"]), float(row["lon"]), row.get("display_name", city)


def _osm_sync(query, city, limit):
    lat, lon, display = _geocode_sync(city)
    delta = 0.12
    south, north, west, east = lat - delta, lat + delta, lon - delta, lon + delta
    tokens = [t.lower() for t in re.findall(r"[\wÀ-ÿ]+", query) if len(t) >= 3]
    tag_map = {
        "restaurant": 'nwr["amenity"="restaurant"]', "restaurants": 'nwr["amenity"="restaurant"]',
        "cafe": 'nwr["amenity"="cafe"]', "café": 'nwr["amenity"="cafe"]',
        "salon": 'nwr["shop"="hairdresser"]', "coiffure": 'nwr["shop"="hairdresser"]',
        "mode": 'nwr["shop"="clothes"]', "vetements": 'nwr["shop"="clothes"]', "vêtements": 'nwr["shop"="clothes"]',
        "pharmacie": 'nwr["amenity"="pharmacy"]', "pharmacy": 'nwr["amenity"="pharmacy"]',
        "gym": 'nwr["leisure"="fitness_centre"]', "fitness": 'nwr["leisure"="fitness_centre"]',
        "hotel": 'nwr["tourism"="hotel"]', "hôtel": 'nwr["tourism"="hotel"]',
        "automobile": 'nwr["shop"="car"]', "voiture": 'nwr["shop"="car"]',
    }
    blocks = [tag_map[t] for t in tokens if t in tag_map]
    if not blocks:
        regex = ".*" + ".*".join(re.escape(t) for t in tokens[:3]) + ".*" if tokens else ".*"
        blocks = [f'nwr["name"~"{regex}",i]']
    query_parts = [f"{b}({south},{west},{north},{east});" for b in blocks[:3]]
    ql = "[out:json][timeout:20];(" + "".join(query_parts) + ");out center tags;"
    r = requests.post(OVERPASS_URL, data=ql, headers={"User-Agent": UA}, timeout=HUNTER_SEARCH_TIMEOUT + 8)
    r.raise_for_status()
    out, seen = [], set()
    for x in r.json().get("elements", []):
        tags = x.get("tags", {})
        name = tags.get("name") or tags.get("brand")
        if not name or x.get("id") in seen:
            continue
        seen.add(x.get("id"))
        website = tags.get("website") or tags.get("contact:website") or ""
        phone = tags.get("phone") or tags.get("contact:phone") or ""
        address = " ".join(filter(None, [tags.get("addr:housenumber"), tags.get("addr:street"), tags.get("addr:city")]))
        out.append({
            "name": name, "platform": "OpenStreetMap", "contact": phone or website,
            "phone": phone, "website": website, "address": address or display,
            "rating": None, "review_count": 0, "business_status": "OPERATIONAL",
            "external_id": f"osm:{x.get('type')}:{x.get('id')}", "source": "openstreetmap",
            "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus(name + ' ' + (address or display))}", "niche": query,
        })
        if len(out) >= limit:
            break
    for x in out:
        x["score"] = _score(x, query)
    return out


async def find_leads(query, city, limit=20):
    limit = max(1, min(int(limit), HUNTER_MAX_RESULTS))
    if GOOGLE_PLACES_API_KEY:
        try:
            return await asyncio.to_thread(_google_sync, query, city, limit), "google_places"
        except Exception as exc:
            google_error = str(exc)
        else:
            google_error = ""
    else:
        google_error = ""
    try:
        results = await asyncio.to_thread(_osm_sync, query, city, limit)
        return results, "openstreetmap"
    except Exception as exc:
        detail = str(exc)
        if google_error:
            detail = f"Google Places: {google_error} | OpenStreetMap: {detail}"
        raise RuntimeError(detail)
