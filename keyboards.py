from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 Product Hunter", callback_data="find_product")],
        [InlineKeyboardButton("📦 Mes produits", callback_data="my_products")],
        [InlineKeyboardButton("🧠 Analyse manuelle", callback_data="analyze_product")],
        [InlineKeyboardButton("🏹 Hunter AI — Trouver des clients", callback_data="hunter_menu")],
        [InlineKeyboardButton("⚙️ Paramètres", callback_data="settings")],
    ])


def back_button(target="main_menu"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Retour", callback_data=target)]])


def analyzer_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧠 Analyser un autre", callback_data="analyze_product")],
        [InlineKeyboardButton("↩️ Retour", callback_data="main_menu")],
    ])


def hunter_menu(products=None):
    rows = []
    if products:
        for i, product in enumerate(products[:3]):
            rows.append([
                InlineKeyboardButton(f"🔍 #{i + 1}", callback_data=f"detail_live:{i}"),
                InlineKeyboardButton("💾", callback_data=f"save_live:{i}"),
            ])
    rows.extend([
        [InlineKeyboardButton("🔎 Nouvelle recherche", callback_data="find_product")],
        [InlineKeyboardButton("↩️ Retour", callback_data="main_menu")],
    ])
    return InlineKeyboardMarkup(rows)


def detail_menu(index, has_url=True):
    rows = []
    if has_url:
        rows.append([InlineKeyboardButton("🔗 Voir le produit", url="https://www.aliexpress.com/")])
    rows.extend([
        [InlineKeyboardButton("💾 Sauvegarder", callback_data=f"save_live:{index}")],
        [InlineKeyboardButton("↩️ Résultats", callback_data="back_results")],
    ])
    return InlineKeyboardMarkup(rows)


def settings_menu(country, currency, max_price):
    budget = "Sans limite" if max_price <= 0 else f"≤ ${max_price:.2f}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🌍 {country}", callback_data="settings_country")],
        [InlineKeyboardButton(f"💱 {currency}", callback_data="settings_currency")],
        [InlineKeyboardButton(f"💰 {budget}", callback_data="settings_budget")],
        [InlineKeyboardButton("↩️ Retour", callback_data="main_menu")],
    ])


def country_menu(countries):
    rows = []
    row = []
    for code, label in countries.items():
        row.append(InlineKeyboardButton(label, callback_data=f"country:{code}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("↩️ Paramètres", callback_data="settings")])
    return InlineKeyboardMarkup(rows)


def currency_menu(currencies):
    rows = [[InlineKeyboardButton(label, callback_data=f"currency:{code}")] for code, label in currencies.items()]
    rows.append([InlineKeyboardButton("↩️ Paramètres", callback_data="settings")])
    return InlineKeyboardMarkup(rows)


def budget_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("$20", callback_data="budget:20"), InlineKeyboardButton("$50", callback_data="budget:50")],
        [InlineKeyboardButton("$100", callback_data="budget:100"), InlineKeyboardButton("$200", callback_data="budget:200")],
        [InlineKeyboardButton("♾️ Sans limite", callback_data="budget:0")],
        [InlineKeyboardButton("↩️ Paramètres", callback_data="settings")],
    ])


def retry_hunt_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Réessayer", callback_data="retry_hunt")],
        [InlineKeyboardButton("↩️ Retour", callback_data="find_product")],
    ])


HUNT_CATEGORIES = {
    "fitness": "🏋️ Fitness",
    "kitchen": "🍳 Cuisine",
    "pet products": "🐶 Animaux",
    "phone accessories": "📱 Téléphone",
    "beauty": "💄 Beauté",
    "home gadgets": "🏠 Maison",
    "car accessories": "🚗 Auto",
    "gaming accessories": "🎮 Gaming",
    "baby products": "👶 Bébé",
    "travel accessories": "✈️ Voyage",
    "fashion": "👕 Mode",
    "outdoor": "🏕️ Outdoor",
}


def hunter_categories_menu():
    rows = []
    items = list(HUNT_CATEGORIES.items())
    for i in range(0, len(items), 2):
        rows.append([
            InlineKeyboardButton(label, callback_data=f"hunt:{keyword}")
            for keyword, label in items[i:i + 2]
        ])
    rows.append([InlineKeyboardButton("✏️ Autre", callback_data="hunt_custom")])
    rows.append([InlineKeyboardButton("↩️ Retour", callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)


# ---------------- HUNTER AI ----------------

def hunter_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Trouver des clients", callback_data="hunter_find")],
        [InlineKeyboardButton("👥 Mes prospects", callback_data="hunter_prospects")],
        [InlineKeyboardButton("✍️ Générer un message", callback_data="hunter_message")],
        [InlineKeyboardButton("📈 Suivi des prospects", callback_data="hunter_pipeline")],
        [InlineKeyboardButton("🧠 Mon offre / cible", callback_data="hunter_profile")],
        [InlineKeyboardButton("↩️ Retour", callback_data="main_menu")],
    ])


def hunter_prospects_menu(prospects):
    rows = []
    for p in prospects[:10]:
        rows.append([InlineKeyboardButton(
            f"#{p['id']} {p['name'][:24]} • {p['score']}/100",
            callback_data=f"prospect:{p['id']}"
        )])
    rows.append([InlineKeyboardButton("➕ Ajouter un prospect", callback_data="hunter_add")])
    rows.append([InlineKeyboardButton("↩️ Hunter AI", callback_data="hunter_menu")])
    return InlineKeyboardMarkup(rows)


def prospect_detail_menu(pid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ Générer message", callback_data=f"message:{pid}")],
        [
            InlineKeyboardButton("📨 Contacté", callback_data=f"status:{pid}:contacted"),
            InlineKeyboardButton("💬 Répondu", callback_data=f"status:{pid}:replied"),
        ],
        [
            InlineKeyboardButton("🔥 Qualifié", callback_data=f"status:{pid}:qualified"),
            InlineKeyboardButton("💰 Client", callback_data=f"status:{pid}:won"),
        ],
        [InlineKeyboardButton("↩️ Mes prospects", callback_data="hunter_prospects")],
    ])


def hunter_back_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("↩️ Hunter AI", callback_data="hunter_menu")],
    ])
