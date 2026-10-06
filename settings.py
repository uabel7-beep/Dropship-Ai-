from database import get_settings, set_setting

COUNTRIES = {
    "CD": "🇨🇩 RDC",
    "FR": "🇫🇷 France",
    "BE": "🇧🇪 Belgique",
    "CA": "🇨🇦 Canada",
    "US": "🇺🇸 USA",
    "GB": "🇬🇧 Royaume-Uni",
}

CURRENCIES = {
    "USD": "💵 USD",
    "EUR": "💶 EUR",
}

DEFAULTS = {
    "country": "CD",
    "currency": "USD",
    "max_price": "0",
}


def get_user_settings(user_id):
    values = get_settings(user_id)
    for key, default in DEFAULTS.items():
        values.setdefault(key, default)
    return values


def set_user_setting(user_id, key, value):
    if key not in DEFAULTS:
        raise ValueError("Paramètre inconnu")
    set_setting(user_id, key, str(value))


def country_label(code):
    return COUNTRIES.get(code, f"🌍 {code}")


def currency_label(code):
    return CURRENCIES.get(code, code)
