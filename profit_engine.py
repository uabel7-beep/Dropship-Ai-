"""Simple, transparent profit estimation for DROPSHIP AI.

The engine separates known costs from unknown costs. It never treats an
unknown shipping price as free.
"""

from config import AD_COST_RATE, PLATFORM_FEE_RATE


def calculate_profit(cost, selling_price, shipping_cost=None, ad_rate=None, fee_rate=None):
    cost = max(0.0, float(cost or 0))
    selling_price = max(0.0, float(selling_price or 0))
    ad_rate = AD_COST_RATE if ad_rate is None else max(0.0, float(ad_rate))
    fee_rate = PLATFORM_FEE_RATE if fee_rate is None else max(0.0, float(fee_rate))

    shipping_known = shipping_cost is not None
    shipping = max(0.0, float(shipping_cost or 0)) if shipping_known else 0.0
    platform_fee = selling_price * fee_rate
    ad_cost = selling_price * ad_rate
    landed_cost = cost + shipping
    net_profit = selling_price - landed_cost - platform_fee - ad_cost
    roi = (net_profit / landed_cost * 100) if landed_cost > 0 else 0.0
    net_margin = (net_profit / selling_price * 100) if selling_price > 0 else 0.0

    return {
        "shipping_cost": round(shipping, 2) if shipping_known else None,
        "shipping_known": shipping_known,
        "landed_cost": round(landed_cost, 2),
        "platform_fee": round(platform_fee, 2),
        "ad_cost": round(ad_cost, 2),
        "net_profit": round(net_profit, 2),
        "roi": round(roi, 1),
        "net_margin": round(net_margin, 1),
        "ad_rate": ad_rate,
        "fee_rate": fee_rate,
    }
