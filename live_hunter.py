import asyncio

from config import LIVE_SEARCH_TIMEOUT, LIVE_DETAIL_TIMEOUT
from reefapi_client import search_products, product_detail
from product_analyzer import analyze_live_product, enrich_live_product


async def hunt_live(keywords, ship_to_country="CD", target_currency="USD", max_price=None):
    try:
        raw = await asyncio.wait_for(
            asyncio.to_thread(
                search_products,
                keywords,
                max_results=20,
                country=ship_to_country,
                currency=target_currency,
                max_price=max_price,
            ),
            timeout=LIVE_SEARCH_TIMEOUT,
        )
    except asyncio.TimeoutError:
        return [], "Recherche trop lente."
    except Exception as exc:
        return [], str(exc)

    results = []
    for item in raw:
        try:
            result = analyze_live_product(item)
            if result:
                results.append(result)
        except (TypeError, ValueError, KeyError):
            continue

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:3], None


async def load_product_detail(product, ship_to_country="US", target_currency="USD"):
    try:
        detail = await asyncio.wait_for(
            asyncio.to_thread(
                product_detail,
                product_id=product.get("product_id"),
                url=product.get("url"),
                country=ship_to_country,
                currency=target_currency,
            ),
            timeout=LIVE_DETAIL_TIMEOUT,
        )
        return enrich_live_product(product, detail), None
    except asyncio.TimeoutError:
        return product, "Analyse trop lente."
    except Exception as exc:
        return product, str(exc)


def format_live_products(products, limit=3):
    if not products:
        return "🔎 **Aucun produit trouvé.**"
    lines = ["🏆 **TOP 3**"]
    for i, p in enumerate(products[:limit], 1):
        lines.append(
            f"\n🥇 **#{i} {p['name'][:55]}**\n"
            f"💰 ${p['cost']:.2f} → ${p['selling_price']:.2f}  •  💵 +${p['profit']:.2f}\n"
            f"⭐ {p['rating']:.1f}  •  📦 {p['orders']}  •  🧠 **{p['score']}/100**\n"
            f"{p['verdict']}  •  {p.get('signal_level', 'N/A')}"
        )
    return "\n".join(lines)


def format_product_detail(p, index):
    shipping = p.get("shipping_cost")
    if p.get("shipping_free") is True:
        shipping_text = "🚚 Gratuit"
    elif shipping is not None:
        shipping_text = f"🚚 ${shipping:.2f}"
    else:
        shipping_text = "🚚 À vérifier"

    net = p.get("net_profit")
    net_text = f"💵 Net estimé : ${net:.2f}" if net is not None else "💵 Net : —"
    roi = p.get("roi")
    roi_text = f"📈 ROI : {roi:.1f}%" if roi is not None else "📈 ROI : —"
    reasons = p.get("reasons", [])[:2]
    warnings = p.get("warnings", [])[:2]

    text = (
        f"🔎 **#{index + 1}**\n\n"
        f"🛍️ **{p['name'][:90]}**\n\n"
        f"🧠 **{p['score']}/100**  {p['verdict']}\n"
        f"📈 {p.get('signal_level', 'N/A')}\n\n"
        f"💰 ${p['cost']:.2f} → ${p['selling_price']:.2f}\n"
        f"💵 Brut : +${p['profit']:.2f}  •  📊 {p['margin']:.1f}%\n"
        f"{shipping_text}"
    )
    if p.get("delivery_estimate"):
        text += f"  •  {p['delivery_estimate']}"
    text += f"\n{net_text}  •  {roi_text}\n"
    text += f"📦 {p['orders']} ventes  •  ⭐ {p['rating']:.1f}/5"
    if reasons:
        text += "\n\n✅ " + " • ".join(reasons)
    if warnings:
        text += "\n⚠️ " + " • ".join(warnings)
    return text
