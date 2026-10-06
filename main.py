import asyncio
import logging
from functools import wraps

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from config import BOT_TOKEN, ADMIN_ID, MAX_PRODUCTS_TO_SHOW
from database import init_db, add_user, save_product, get_products, get_stats
from live_hunter import hunt_live, load_product_detail, format_live_products, format_product_detail
from hunter import get_prospects, get_prospect, add_prospect, update_prospect_status, get_hunter_stats, get_hunter_profile, set_hunter_profile, build_outreach_message, prospect_card
from product_analyzer import analyze_product
from security import is_admin_update
from keyboards import main_menu, back_button, analyzer_menu, hunter_menu, settings_menu, country_menu, currency_menu, budget_menu, hunter_categories_menu, HUNT_CATEGORIES, retry_hunt_button, hunter_main_menu, hunter_prospects_menu, prospect_detail_menu, hunter_back_menu
from settings import COUNTRIES, CURRENCIES, get_user_settings, set_user_setting, country_label, currency_label

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


def admin_only(func):
    @wraps(func)
    async def wrapper(update, context):
        if not is_admin_update(update):
            message = update.effective_message
            if message:
                await message.reply_text("🔒 Accès refusé. Ce bot est privé.")
            elif update.callback_query:
                await update.callback_query.answer("🔒 Accès refusé.", show_alert=True)
            return
        return await func(update, context)
    return wrapper


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_update(update):
        await update.effective_message.reply_text("🔒 **ACCÈS REFUSÉ**\n\nCe bot est privé.", parse_mode=ParseMode.MARKDOWN)
        return
    user = update.effective_user
    add_user(user.id, user.username, user.first_name)
    context.user_data.clear()
    await update.effective_message.reply_text(
        f"🤖 **DROPSHIP AI**\n\nSalut {user.first_name} 👋\n\nChoisis :",
        reply_markup=main_menu(), parse_mode=ParseMode.MARKDOWN,
    )


async def show_settings(query, user_id):
    s = get_user_settings(user_id)
    max_price = float(s.get("max_price", "0") or 0)
    await query.edit_message_text(
        "⚙️ **PARAMÈTRES**\n\n"
        f"🌍 **{country_label(s['country'])}**\n"
        f"💱 **{currency_label(s['currency'])}**\n"
        f"💰 **{'Sans limite' if max_price <= 0 else '$' + format(max_price, '.2f')}**",
        reply_markup=settings_menu(country_label(s['country']), currency_label(s['currency']), max_price),
        parse_mode=ParseMode.MARKDOWN,
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("🔒 Accès refusé.", show_alert=True)
        return
    await query.answer()
    data = query.data
    uid = query.from_user.id

    if data == "hunter_menu":
        context.user_data.clear()
        await query.edit_message_text(
            "🏹 **HUNTER AI**\n\nJe t’aide à organiser ta prospection et à transformer des prospects en clients.",
            reply_markup=hunter_main_menu(), parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "hunter_find":
        context.user_data["hunter_waiting_find"] = True
        context.user_data["waiting_for_hunt"] = False
        context.user_data["waiting_for_product"] = False
        await query.edit_message_text(
            "🎯 **TROUVER DES CLIENTS**\n\n"
            "Décris ce que tu vends et le type de client recherché.\n\n"
            "Exemple : `montage TikTok | restaurants et petites entreprises`",
            reply_markup=hunter_back_menu(), parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "hunter_add":
        context.user_data["hunter_waiting_add"] = True
        await query.edit_message_text(
            "➕ **AJOUTER UN PROSPECT**\n\n"
            "Envoie : `Nom | plateforme | contact | niche | besoin | score`\n\n"
            "Exemple : `ABC Store | Instagram | @abcstore | mode | veut plus de vidéos | 85`",
            reply_markup=hunter_back_menu(), parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "hunter_prospects":
        prospects = get_prospects(uid)
        text = "👥 **MES PROSPECTS**\n\n"
        text += "\n\n".join(prospect_card(p) for p in prospects) if prospects else "Aucun prospect pour le moment."
        await query.edit_message_text(text, reply_markup=hunter_prospects_menu(prospects), parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("prospect:"):
        try:
            pid = int(data.split(":", 1)[1])
        except ValueError:
            await query.answer("Prospect invalide.", show_alert=True)
            return
        p = get_prospect(uid, pid)
        if not p:
            await query.answer("Prospect introuvable.", show_alert=True)
            return
        text = (
            f"👤 **{p['name']}**\n\n"
            f"📍 Plateforme : {p['platform']}\n"
            f"📞 Contact : {p.get('contact') or '—'}\n"
            f"🎯 Niche : {p.get('niche') or '—'}\n"
            f"📝 Besoin : {p.get('need') or '—'}\n"
            f"🧠 Score : **{p['score']}/100**\n"
            f"📈 Statut : **{p['status']}**"
        )
        await query.edit_message_text(text, reply_markup=prospect_detail_menu(pid), parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("status:"):
        parts = data.split(":")
        if len(parts) != 3:
            await query.answer("Action invalide.", show_alert=True)
            return
        try:
            pid = int(parts[1])
        except ValueError:
            await query.answer("Prospect invalide.", show_alert=True)
            return
        update_prospect_status(uid, pid, parts[2])
        p = get_prospect(uid, pid)
        await query.answer("Statut mis à jour.")
        await query.edit_message_text(
            f"👤 **{p['name']}**\n\n📈 Statut : **{p['status']}**\n🧠 Score : **{p['score']}/100**",
            reply_markup=prospect_detail_menu(pid), parse_mode=ParseMode.MARKDOWN
        )

    elif data == "hunter_message":
        prospects = get_prospects(uid, 10)
        if not prospects:
            await query.edit_message_text(
                "✍️ **GÉNÉRER UN MESSAGE**\n\nAjoute d’abord un prospect.",
                reply_markup=hunter_back_menu(), parse_mode=ParseMode.MARKDOWN
            )
        else:
            text = "✍️ **CHOISIS UN PROSPECT**\n\n" + "\n\n".join(prospect_card(p) for p in prospects)
            await query.edit_message_text(text, reply_markup=hunter_prospects_menu(prospects), parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("message:"):
        try:
            pid = int(data.split(":", 1)[1])
        except ValueError:
            await query.answer("Prospect invalide.", show_alert=True)
            return
        p = get_prospect(uid, pid)
        if not p:
            await query.answer("Prospect introuvable.", show_alert=True)
            return
        profile = get_hunter_profile(uid)
        msg = build_outreach_message(profile, p)
        safe_msg = msg.replace("`", "'")
        await query.edit_message_text(
            f"✍️ **MESSAGE PERSONNALISÉ**\n\n`{safe_msg}`",
            reply_markup=prospect_detail_menu(pid), parse_mode=ParseMode.MARKDOWN
        )

    elif data == "hunter_pipeline":
        stats = get_hunter_stats(uid)
        text = (
            "📈 **SUIVI DES PROSPECTS**\n\n"
            f"👥 Total : {stats['total']}\n"
            f"🆕 Nouveaux : {stats['new_count']}\n"
            f"📨 Contactés : {stats['contacted']}\n"
            f"💬 Réponses : {stats['replied']}\n"
            f"🔥 Qualifiés : {stats['qualified']}\n"
            f"💰 Clients : {stats['won']}"
        )
        await query.edit_message_text(text, reply_markup=hunter_back_menu(), parse_mode=ParseMode.MARKDOWN)

    elif data == "hunter_profile":
        profile = get_hunter_profile(uid)
        context.user_data["hunter_waiting_profile"] = True
        await query.edit_message_text(
            "🧠 **MON OFFRE / CIBLE**\n\n"
            f"Offre actuelle : `{profile.get('offer') or 'non définie'}`\n"
            f"Cible actuelle : `{profile.get('target') or 'non définie'}`\n\n"
            "Envoie : `ton offre | ton client cible`",
            reply_markup=hunter_back_menu(), parse_mode=ParseMode.MARKDOWN
        )

    elif data == "main_menu":
        context.user_data.clear()
        await query.edit_message_text("🤖 **DROPSHIP AI**\n\nChoisis :", reply_markup=main_menu(), parse_mode=ParseMode.MARKDOWN)

    elif data == "find_product":
        context.user_data["waiting_for_hunt"] = False
        context.user_data["waiting_for_product"] = False
        await query.edit_message_text(
            "🔎 **PRODUCT HUNTER**\n\nChoisis une niche :",
            reply_markup=hunter_categories_menu(),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data.startswith("hunt:"):
        keyword = data.split(":", 1)[1].strip()
        context.user_data["waiting_for_hunt"] = False
        context.user_data["waiting_for_product"] = False
        s = get_user_settings(uid)
        max_price = float(s.get("max_price", "0") or 0)
        context.user_data["last_hunt_keyword"] = keyword
        await query.edit_message_text("⏳ **Recherche...**", parse_mode=ParseMode.MARKDOWN)
        products, error = await hunt_live(
            keyword,
            ship_to_country=s["country"],
            target_currency=s["currency"],
            max_price=max_price if max_price > 0 else None,
        )
        if error:
            logger.warning("Product Hunter error: %s", error)
            await query.edit_message_text(
                "⚠️ **Recherche indisponible.**",
                reply_markup=retry_hunt_button(),
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        context.user_data["last_hunt_results"] = products
        await query.edit_message_text(
            format_live_products(products),
            reply_markup=hunter_menu(products),
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )

    elif data == "hunt_custom":
        context.user_data["waiting_for_hunt"] = True
        context.user_data["waiting_for_product"] = False
        await query.edit_message_text(
            "✏️ **MOT-CLÉ**\n\nEnvoie un seul mot-clé.",
            reply_markup=back_button("find_product"),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "analyze_product":
        context.user_data["waiting_for_product"] = True
        context.user_data["waiting_for_hunt"] = False
        await query.edit_message_text(
            "🧠 **ANALYSER UN PRODUIT**\n\n`Nom | coût | prix de vente | commandes | note`",
            reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "my_products":
        products = get_products(uid, MAX_PRODUCTS_TO_SHOW)
        if not products:
            text = "📦 **MES PRODUITS**\n\nAucun produit enregistré pour le moment."
        else:
            chunks = ["📦 **MES PRODUITS**\n"]
            for p in products:
                chunks.append(
                    f"• **{p['name']}** — {p['score']}/100 — {p['verdict']}\n"
                    f"  📈 {p.get('signal_level') or 'N/A'} | 💰 {p['margin']:.1f}% | 💵 net {p.get('net_profit') or 0:.2f}\n"
                )
            text = "\n".join(chunks)
        await query.edit_message_text(text, reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)

    elif data == "dashboard":
        stats = get_stats(uid)
        text = ("📊 **DASHBOARD**\n\n"
                f"👤 Administrateur : `{uid}`\n"
                f"🛒 Produits analysés : {stats['products']}\n"
                f"🟢 À tester : {stats['testable']}\n"
                f"🧠 Score moyen : {stats['avg_score']:.1f}/100\n"
                f"💵 Brut cumulé : ${stats['potential_profit']:.2f}\n"                f"💵 Net estimé : ${stats['net_profit']:.2f}")
        await query.edit_message_text(text, reply_markup=back_button(), parse_mode=ParseMode.MARKDOWN)

    elif data == "settings":
        await show_settings(query, uid)

    elif data == "settings_country":
        await query.edit_message_text("🌍 **CHOISIS TON PAYS CIBLE**\n\nLe pays choisi sera utilisé pour les recherches live.", reply_markup=country_menu(COUNTRIES), parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("country:"):
        code = data.split(":", 1)[1]
        if code not in COUNTRIES:
            await query.answer("Pays invalide.", show_alert=True)
            return
        set_user_setting(uid, "country", code)
        await query.answer(f"Pays cible : {country_label(code)}")
        await show_settings(query, uid)

    elif data == "settings_currency":
        await query.edit_message_text("💱 **CHOISIS LA DEVISE**", reply_markup=currency_menu(CURRENCIES), parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("currency:"):
        code = data.split(":", 1)[1]
        if code not in CURRENCIES:
            await query.answer("Devise invalide.", show_alert=True)
            return
        set_user_setting(uid, "currency", code)
        await query.answer(f"Devise : {code}")
        await show_settings(query, uid)

    elif data == "settings_budget":
        await query.edit_message_text("💰 **PRIX FOURNISSEUR MAXIMUM**\n\nChoisis une limite ou aucune limite.", reply_markup=budget_menu(), parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("budget:"):
        value = data.split(":", 1)[1]
        try:
            amount = float(value)
        except ValueError:
            await query.answer("Budget invalide.", show_alert=True)
            return
        set_user_setting(uid, "max_price", amount)
        await query.answer("Budget mis à jour.")
        await show_settings(query, uid)

    elif data == "retry_hunt":
        keyword = context.user_data.get("last_hunt_keyword")
        if not keyword:
            await query.edit_message_text("🔎 **PRODUCT HUNTER**", reply_markup=hunter_categories_menu(), parse_mode=ParseMode.MARKDOWN)
            return
        s = get_user_settings(uid)
        max_price = float(s.get("max_price", "0") or 0)
        await query.edit_message_text("⏳ **Recherche...**", parse_mode=ParseMode.MARKDOWN)
        products, error = await hunt_live(keyword, ship_to_country=s["country"], target_currency=s["currency"], max_price=max_price if max_price > 0 else None)
        if error:
            await query.edit_message_text("⚠️ **Recherche indisponible.**", reply_markup=retry_hunt_button(), parse_mode=ParseMode.MARKDOWN)
            return
        context.user_data["last_hunt_results"] = products
        await query.edit_message_text(format_live_products(products), reply_markup=hunter_menu(products), parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

    elif data.startswith("detail_live:"):
        try:
            index = int(data.split(":", 1)[1])
            results = context.user_data.get("last_hunt_results", [])
            result = results[index]
        except (ValueError, IndexError):
            await query.answer("Résultat introuvable.", show_alert=True)
            return

        if not result.get("detail_loaded"):
            await query.edit_message_text("🔎 **Analyse du produit...**", parse_mode=ParseMode.MARKDOWN)
            s = get_user_settings(uid)
            enriched, error = await load_product_detail(result, ship_to_country=s["country"], target_currency=s["currency"])
            if error:
                logger.warning("Product detail error: %s", error)
                await query.edit_message_text(
                    format_product_detail(result, index),
                    reply_markup=product_detail_menu(index, result.get("url"), retry=True),
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True,
                )
                return
            results[index] = enriched
            result = enriched
            context.user_data["last_hunt_results"] = results

        await query.edit_message_text(
            format_product_detail(result, index),
            reply_markup=product_detail_menu(index, result.get("url")),
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )

    elif data == "back_results":
        results = context.user_data.get("last_hunt_results", [])
        if not results:
            await query.edit_message_text("🔎 **PRODUCT HUNTER**", reply_markup=hunter_categories_menu(), parse_mode=ParseMode.MARKDOWN)
            return
        await query.edit_message_text(
            format_live_products(results),
            reply_markup=hunter_menu(results),
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )

    elif data.startswith("save_live:"):
        try:
            index = int(data.split(":", 1)[1])
            results = context.user_data.get("last_hunt_results", [])
            result = results[index]
        except (ValueError, IndexError):
            await query.answer("Produit introuvable. Relance une recherche.", show_alert=True)
            return
        save_product(uid, result, source=result.get("source", "reefapi_aliexpress"))
        await query.answer("💾 Produit sauvegardé !", show_alert=True)
        await query.edit_message_text(format_live_products(results), reply_markup=hunter_menu(results), parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

    else:
        await query.edit_message_text("❌ Option inconnue.", reply_markup=back_button())


def product_detail_menu(index, url=None, retry=False):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    rows = []
    if url:
        rows.append([InlineKeyboardButton("🔗 Voir le produit", url=url)])
    if retry:
        rows.append([InlineKeyboardButton("🔄 Réessayer", callback_data=f"detail_live:{index}")])
    rows.extend([
        [InlineKeyboardButton("💾 Sauvegarder", callback_data=f"save_live:{index}")],
        [InlineKeyboardButton("↩️ Résultats", callback_data="back_results")],
    ])
    return InlineKeyboardMarkup(rows)


async def product_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_update(update):
        return
    raw = (update.effective_message.text or "").strip()

    if context.user_data.get("hunter_waiting_find"):
        context.user_data["hunter_waiting_find"] = False
        parts = [p.strip() for p in raw.split("|", 1)]
        offer = parts[0] if parts else raw
        target = parts[1] if len(parts) > 1 else "clients potentiels"
        set_hunter_profile(update.effective_user.id, offer, target)
        await update.effective_message.reply_text(
            "🏹 **PLAN DE CHASSE PRÊT**\n\n"
            f"💼 Offre : **{offer}**\n"
            f"🎯 Cible : **{target}**\n\n"
            "Hunter AI va utiliser cette offre/cible pour qualifier tes prospects et personnaliser les messages.\n\n"
            "⚠️ Cette V1 ne contacte personne automatiquement : ajoute/importes les prospects que tu as le droit de contacter.",
            reply_markup=hunter_back_menu(), parse_mode=ParseMode.MARKDOWN
        )
        return

    if context.user_data.get("hunter_waiting_add"):
        context.user_data["hunter_waiting_add"] = False
        parts = [p.strip() for p in raw.split("|")]
        if len(parts) < 2:
            await update.effective_message.reply_text(
                "❌ Format incorrect.\n\n`Nom | plateforme | contact | niche | besoin | score`",
                reply_markup=hunter_back_menu(), parse_mode=ParseMode.MARKDOWN
            )
            return
        name = parts[0]
        platform = parts[1]
        contact = parts[2] if len(parts) > 2 else ""
        niche = parts[3] if len(parts) > 3 else ""
        need = parts[4] if len(parts) > 4 else ""
        try:
            score = int(parts[5]) if len(parts) > 5 and parts[5] else 50
        except ValueError:
            score = 50
        pid = add_prospect(update.effective_user.id, name, platform, contact, niche, need, score)
        await update.effective_message.reply_text(
            f"✅ Prospect **#{pid}** ajouté.\n\n{prospect_card(get_prospect(update.effective_user.id, pid))}",
            reply_markup=hunter_back_menu(), parse_mode=ParseMode.MARKDOWN
        )
        return

    if context.user_data.get("hunter_waiting_profile"):
        context.user_data["hunter_waiting_profile"] = False
        parts = [p.strip() for p in raw.split("|", 1)]
        if len(parts) != 2:
            await update.effective_message.reply_text(
                "❌ Format incorrect : `ton offre | ton client cible`",
                reply_markup=hunter_back_menu(), parse_mode=ParseMode.MARKDOWN
            )
            return
        set_hunter_profile(update.effective_user.id, parts[0], parts[1])
        await update.effective_message.reply_text(
            "✅ **Profil Hunter enregistré.**",
            reply_markup=hunter_back_menu(), parse_mode=ParseMode.MARKDOWN
        )
        return

    if context.user_data.get("waiting_for_hunt"):
        context.user_data["waiting_for_hunt"] = False
        s = get_user_settings(update.effective_user.id)
        context.user_data["last_hunt_keyword"] = raw
        max_price = float(s.get("max_price", "0") or 0)
        await update.effective_message.reply_text("🔎 Recherche en cours...", parse_mode=ParseMode.MARKDOWN)
        products, error = await hunt_live(raw, ship_to_country=s["country"], target_currency=s["currency"], max_price=max_price if max_price > 0 else None)
        if error:
            logger.warning("Product Hunter error: %s", error)
            await update.effective_message.reply_text(
                "⚠️ **Recherche indisponible.**",
                reply_markup=retry_hunt_button(),
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        context.user_data["last_hunt_results"] = products
        context.user_data["last_hunt_keyword"] = raw
        await update.effective_message.reply_text(format_live_products(products), reply_markup=hunter_menu(products), parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        return

    if not context.user_data.get("waiting_for_product"):
        return

    parts = [part.strip() for part in raw.split("|")]
    if len(parts) != 5:
        await update.effective_message.reply_text("❌ Format incorrect.\n\n`Nom | coût | prix de vente | commandes | note`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        result = analyze_product(parts[0], float(parts[1]), float(parts[2]), int(parts[3]), float(parts[4]))
    except (ValueError, TypeError) as exc:
        await update.effective_message.reply_text(f"❌ Données invalides : {exc}")
        return
    save_product(uid := update.effective_user.id, result, source="manual")
    context.user_data["waiting_for_product"] = False
    text = ("🧠 **ANALYSE DU PRODUIT**\n\n"
            f"🛍️ **{result['name']}**\n\n💰 Coût : ${result['cost']:.2f}\n"
            f"🏷️ Prix de vente : ${result['selling_price']:.2f}\n💵 Bénéfice brut : ${result['profit']:.2f}\n"
            f"📈 Marge : {result['margin']:.1f}%\n🛒 Commandes : {result['orders']}\n⭐ Note : {result['rating']:.1f}/5\n\n"
            f"🧠 **Score : {result['score']}/100**\n🎯 **Verdict : {result['verdict']}**\n"
            f"📈 Signal : **{result.get('signal_level', 'N/A')}**\n"
            f"\n✅ **Pourquoi :**\n" + "\n".join(f"• {r}" for r in result.get('reasons', [])[:5]) +
            ("\n\n" + "\n".join(f"{w}" for w in result.get('warnings', [])[:3]) if result.get('warnings') else "") +
            f"\n\n_ℹ️ {result.get('signal_note', '')}_")
    await update.effective_message.reply_text(text, reply_markup=analyzer_menu(), parse_mode=ParseMode.MARKDOWN)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Erreur pendant le traitement d'une mise à jour", exc_info=context.error)


def main():
    init_db()
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN introuvable")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, product_message))
    app.add_error_handler(error_handler)
    print("🤖 DROPSHIP AI démarré...")
    app.run_polling()


if __name__ == "__main__":
    main()
