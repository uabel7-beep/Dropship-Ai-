from product_analyzer import analyze_product


def find_products():
    """Demo dataset used until a real product source/API is connected."""
    raw_products = [
        ("Mini Projecteur Portable", 18, 49, 1500, 4.7),
        ("Lampe LED avec détecteur", 7, 24, 900, 4.6),
        ("Support téléphone magnétique", 5, 19, 350, 4.4),
    ]

    products = []
    for item in raw_products:
        products.append(analyze_product(*item))

    return sorted(products, key=lambda p: p["score"], reverse=True)


def format_products(products):
    if not products:
        return "🔎 **PRODUITS TROUVÉS**\n\nAucun produit trouvé."

    text = "🔎 **PRODUITS TROUVÉS**\n\n"
    for i, product in enumerate(products, 1):
        text += (
            f"🏆 **#{i} {product['name']}**\n"
            f"💰 Coût : ${product['cost']:.2f}\n"
            f"🏷️ Prix conseillé : ${product['selling_price']:.2f}\n"
            f"💵 Bénéfice brut : ${product['profit']:.2f}\n"
            f"📈 Marge : {product['margin']:.1f}%\n"
            f"🛒 Commandes : {product['orders']}\n"
            f"⭐ Note : {product['rating']:.1f}/5\n"
            f"🧠 Score : {product['score']}/100\n"
            f"🎯 {product['verdict']}\n\n"
        )
    text += "⚠️ Données de démonstration : pas encore une source live."
    return text
