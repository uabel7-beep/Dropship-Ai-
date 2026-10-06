"""Trend/potential signal engine.

This is intentionally transparent: without historical observations we cannot
claim a real trend. The module produces a demand/potential signal from the
current volume, rating, commission and price-position signals.
"""


def detect_signal(orders, rating, margin, commission=0, selling_price=0):
    orders = max(0, int(orders or 0))
    rating = max(0.0, min(5.0, float(rating or 0)))
    margin = max(0.0, float(margin or 0))
    commission = max(0.0, float(commission or 0))
    selling_price = max(0.0, float(selling_price or 0))

    points = 0
    reasons = []
    warnings = []

    if orders >= 5000:
        points += 35
        reasons.append("🔥 volume très élevé")
    elif orders >= 2000:
        points += 30
        reasons.append("📦 volume très fort")
    elif orders >= 1000:
        points += 24
        reasons.append("📦 volume solide")
    elif orders >= 300:
        points += 15
        reasons.append("📦 demande visible")
    elif orders > 0:
        points += 7
        warnings.append("⚠️ volume encore faible")

    if rating >= 4.8:
        points += 25
        reasons.append("⭐ excellente évaluation")
    elif rating >= 4.6:
        points += 20
        reasons.append("⭐ très bonne évaluation")
    elif rating >= 4.3:
        points += 13
    elif rating > 0 and rating < 4.0:
        warnings.append("⚠️ évaluation faible")

    if margin >= 60:
        points += 20
        reasons.append("💰 marge forte")
    elif margin >= 45:
        points += 16
        reasons.append("💰 marge intéressante")
    elif margin >= 30:
        points += 10
    else:
        warnings.append("⚠️ marge faible")

    if commission >= 8:
        points += 10
        reasons.append("💸 commission intéressante")
    elif commission >= 4:
        points += 6

    if 20 <= selling_price <= 80:
        points += 10
        reasons.append("🎯 prix facile à tester")
    elif selling_price > 120:
        warnings.append("⚠️ prix de vente élevé")

    score = max(0, min(100, round(points)))

    if score >= 75:
        level = "🔥 FORT"
    elif score >= 55:
        level = "📈 PROMETTEUR"
    else:
        level = "🧊 FAIBLE"

    if not reasons:
        reasons.append("ℹ️ peu de signaux positifs disponibles")

    return {
        "score": score,
        "level": level,
        "reasons": reasons[:5],
        "warnings": warnings[:3],
        "note": "Signal basé sur les données actuelles ; ce n'est pas une preuve de tendance réelle sans historique.",
    }
