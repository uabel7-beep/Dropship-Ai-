from config import MAX_PRODUCT_NAME_LENGTH
from trend_detector import detect_signal
from profit_engine import calculate_profit


def _clamp(value, low, high):
    return max(low, min(high, value))


def _verdict(score):
    if score >= 75:
        return "🟢 À TESTER"
    if score >= 50:
        return "🟠 À SURVEILLER"
    return "🔴 À ÉVITER"


def _validate(name, cost, selling_price, orders, rating):
    name = str(name).strip()
    if not name:
        raise ValueError("Nom manquant")
    if len(name) > MAX_PRODUCT_NAME_LENGTH:
        raise ValueError("Nom trop long")
    cost = float(cost)
    selling_price = float(selling_price)
    orders = int(orders)
    rating = float(rating)
    if cost <= 0 or selling_price <= 0:
        raise ValueError("Prix invalides")
    if selling_price <= cost:
        raise ValueError("Prix de vente trop bas")
    if orders < 0:
        raise ValueError("Commandes invalides")
    if not 0 <= rating <= 5:
        raise ValueError("Note invalide")
    return name, cost, selling_price, orders, rating


def _percent(value):
    try:
        return float(str(value or "0").replace("%", "").strip() or 0)
    except (TypeError, ValueError):
        return 0.0


def _build_result(name, cost, selling_price, orders, rating, commission=0, source="manual", extra=None, shipping_cost=None):
    profit = selling_price - cost
    margin = profit / selling_price * 100
    profit_data = calculate_profit(cost, selling_price, shipping_cost=shipping_cost)

    margin_score = _clamp(margin / 60 * 30, 0, 30)
    volume_score = _clamp(orders / 2000 * 25, 0, 25)
    rating_score = _clamp(rating / 5 * 20, 0, 20)
    commission_score = _clamp(commission / 10 * 10, 0, 10)
    price_score = 15 if 20 <= selling_price <= 80 else (9 if selling_price <= 120 else 3)
    base_score = _clamp(margin_score + volume_score + rating_score + commission_score + price_score, 0, 100)

    signal = detect_signal(orders, rating, margin, commission, selling_price)
    score = (base_score * 0.65) + (signal["score"] * 0.25)
    if profit_data["shipping_known"]:
        net_margin = profit_data["net_margin"]
        if net_margin >= 30:
            score += 10
        elif net_margin >= 15:
            score += 6
        elif net_margin < 0:
            score -= 15
        elif net_margin < 8:
            score -= 6
    final_score = round(_clamp(score, 0, 100))

    reasons = list(signal["reasons"])
    warnings = list(signal["warnings"])
    if profit_data["shipping_known"]:
        if profit_data["shipping_cost"] == 0:
            reasons.append("🚚 livraison gratuite")
        elif profit_data["shipping_cost"] > 0:
            reasons.append(f"🚚 livraison ${profit_data['shipping_cost']:.2f}")
        if profit_data["net_profit"] < 0:
            warnings.append("⚠️ bénéfice net négatif")
        elif profit_data["net_margin"] < 15:
            warnings.append("⚠️ marge nette faible")
    else:
        warnings.append("🚚 livraison à vérifier")

    result = {
        "name": name[:MAX_PRODUCT_NAME_LENGTH],
        "cost": round(cost, 2),
        "selling_price": round(selling_price, 2),
        "orders": orders,
        "rating": round(rating, 2),
        "profit": round(profit, 2),
        "margin": round(margin, 2),
        "commission": round(commission, 2),
        "score": final_score,
        "verdict": _verdict(final_score),
        "source": source,
        "signal_level": signal["level"],
        "reasons": reasons[:5],
        "warnings": warnings[:3],
        "signal_note": signal["note"],
        **profit_data,
    }
    if extra:
        result.update(extra)
    return result


def analyze_product(name, cost, selling_price, orders=0, rating=0):
    values = _validate(name, cost, selling_price, orders, rating)
    return _build_result(*values, source="manual")


def analyze_live_product(item):
    name = str(item.get("product_title") or "").strip()
    if not name:
        return None
    try:
        cost = float(item.get("app_sale_price") or item.get("sale_price") or 0)
        orders = int(float(item.get("lastest_volume") or 0))
        rating = _percent(item.get("evaluate_rate")) / 20.0
        commission = _percent(item.get("commission_rate"))
    except (TypeError, ValueError):
        return None
    if cost <= 0:
        return None
    selling_price = round(cost * 2.5, 2)
    try:
        return _build_result(
            name, cost, selling_price, orders, rating, commission,
            source=item.get("source", "reefapi_aliexpress"),
            extra={
                "product_id": str(item.get("product_id") or ""),
                "url": item.get("product_detail_url") or "",
                "image_url": item.get("product_main_image_url") or "",
                "promotion_link": item.get("promotion_link") or "",
                "currency": item.get("currency") or "USD",
            },
        )
    except (ValueError, TypeError):
        return None


def enrich_live_product(product, detail):
    """Apply product_detail data, especially destination shipping, to a live result."""
    if not isinstance(detail, dict):
        return product

    price = detail.get("price_current")
    if price is None:
        price_block = detail.get("price")
        if isinstance(price_block, dict):
            price = price_block.get("current") or price_block.get("sale")
    try:
        if price is not None and float(price) > 0:
            product["cost"] = round(float(price), 2)
            product["selling_price"] = round(product["cost"] * 2.5, 2)
    except (TypeError, ValueError):
        pass

    shipping = detail.get("shipping")
    shipping_cost = None
    shipping_free = None
    delivery = ""
    if isinstance(shipping, dict):
        raw_cost = shipping.get("shipping_cost")
        shipping_free = shipping.get("free")
        if shipping_free is True:
            shipping_cost = 0.0
        elif shipping_free is False and raw_cost is not None:
            try:
                shipping_cost = float(raw_cost)
            except (TypeError, ValueError):
                shipping_cost = None
        delivery = shipping.get("delivery_estimate") or ""

    rebuilt = _build_result(
        product["name"], product["cost"], product["selling_price"],
        product.get("orders", 0), product.get("rating", 0),
        product.get("commission", 0), product.get("source", "reefapi_aliexpress"),
        extra={
            "product_id": product.get("product_id", ""),
            "url": detail.get("url") or product.get("url", ""),
            "image_url": detail.get("image") or product.get("image_url", ""),
            "promotion_link": product.get("promotion_link", ""),
            "currency": product.get("currency", "USD"),
            "shipping_free": shipping_free,
            "delivery_estimate": delivery,
            "detail_loaded": True,
        },
        shipping_cost=shipping_cost,
    )
    return rebuilt
