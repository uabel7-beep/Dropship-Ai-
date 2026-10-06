from datetime import datetime, timezone
from contextlib import closing
from database import get_connection


def set_hunter_profile(user_id, offer, target):
    now = datetime.now(timezone.utc).isoformat()
    with closing(get_connection()) as conn:
        conn.execute("""
            INSERT INTO hunter_settings(user_id, offer, target, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                offer=excluded.offer, target=excluded.target,
                updated_at=excluded.updated_at
        """, (user_id, offer.strip(), target.strip(), now, now))
        conn.commit()


def get_hunter_profile(user_id):
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT offer, target FROM hunter_settings WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else {"offer": "", "target": ""}


def add_prospect(user_id, name, platform, contact="", niche="", need="", score=0, notes="", **meta):
    now = datetime.now(timezone.utc).isoformat()
    score = max(0, min(100, int(score or 0)))
    with closing(get_connection()) as conn:
        cur = conn.execute("""
            INSERT INTO prospects(
                user_id, name, platform, contact, niche, need, status, score, notes,
                created_at, updated_at, website, address, phone, source, external_id,
                rating, review_count, maps_url
            ) VALUES (?, ?, ?, ?, ?, ?, 'new', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, name.strip(), platform.strip(), contact.strip(), niche.strip(), need.strip(),
              score, notes.strip(), now, now, meta.get("website", ""), meta.get("address", ""),
              meta.get("phone", ""), meta.get("source", "manual"), meta.get("external_id", ""),
              meta.get("rating"), meta.get("review_count"), meta.get("maps_url", "")))
        conn.commit()
        return cur.lastrowid


def get_prospects(user_id, limit=20, status=None):
    with closing(get_connection()) as conn:
        if status:
            rows = conn.execute("SELECT * FROM prospects WHERE user_id = ? AND status = ? ORDER BY score DESC, id DESC LIMIT ?", (user_id, status, int(limit))).fetchall()
        else:
            rows = conn.execute("SELECT * FROM prospects WHERE user_id = ? ORDER BY score DESC, id DESC LIMIT ?", (user_id, int(limit))).fetchall()
        return [dict(r) for r in rows]


def get_prospect(user_id, prospect_id):
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT * FROM prospects WHERE user_id = ? AND id = ?", (user_id, int(prospect_id))).fetchone()
        return dict(row) if row else None


def prospect_exists(user_id, external_id):
    if not external_id:
        return False
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT 1 FROM prospects WHERE user_id = ? AND external_id = ? LIMIT 1", (user_id, external_id)).fetchone()
        return bool(row)


def update_prospect_status(user_id, prospect_id, status):
    allowed = {"new", "contacted", "replied", "qualified", "won", "lost"}
    if status not in allowed:
        raise ValueError("Statut invalide")
    now = datetime.now(timezone.utc).isoformat()
    with closing(get_connection()) as conn:
        conn.execute("UPDATE prospects SET status = ?, updated_at = ? WHERE user_id = ? AND id = ?", (status, now, user_id, int(prospect_id)))
        conn.commit()


def get_hunter_stats(user_id):
    with closing(get_connection()) as conn:
        row = conn.execute("""
            SELECT COUNT(*) AS total,
            COALESCE(SUM(CASE WHEN status='new' THEN 1 ELSE 0 END),0) AS new_count,
            COALESCE(SUM(CASE WHEN status='contacted' THEN 1 ELSE 0 END),0) AS contacted,
            COALESCE(SUM(CASE WHEN status='replied' THEN 1 ELSE 0 END),0) AS replied,
            COALESCE(SUM(CASE WHEN status='qualified' THEN 1 ELSE 0 END),0) AS qualified,
            COALESCE(SUM(CASE WHEN status='won' THEN 1 ELSE 0 END),0) AS won
            FROM prospects WHERE user_id = ?
        """, (user_id,)).fetchone()
        return dict(row)


def build_outreach_message(profile, prospect):
    offer = profile.get("offer") or "mon service"
    target = profile.get("target") or prospect.get("niche") or "votre activité"
    name = prospect.get("name") or "Bonjour"
    need = prospect.get("need")
    if need:
        need_line = f"J’ai remarqué : {need}."
    elif prospect.get("website"):
        need_line = "J’ai regardé rapidement votre présence en ligne et j’ai une idée qui pourrait vous être utile."
    else:
        need_line = "Je pense pouvoir vous aider sur un point précis."
    return (f"Bonjour {name},\n\nJe travaille sur {offer} et j’aide {target}.\n"
            f"{need_line}\n\nJe peux vous montrer rapidement ce que je pourrais améliorer pour vous, sans engagement. Ça vous intéresse ?")


def prospect_card(p):
    status_labels = {"new":"🆕 Nouveau","contacted":"📨 Contacté","replied":"💬 A répondu","qualified":"🔥 Qualifié","won":"💰 Client","lost":"❌ Perdu"}
    extra = f"⭐ {p['rating']:.1f}" if p.get('rating') else ""
    return (f"#{p['id']} **{p['name']}**\n📍 {p['platform']} {extra} • 🧠 {p['score']}/100\n"
            f"🎯 {status_labels.get(p['status'], p['status'])}\n📝 {p.get('need') or p.get('niche') or 'Besoin à qualifier'}")
