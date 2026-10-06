from config import ADMIN_ID


def is_admin_user(user_id):
    return user_id is not None and int(user_id) == int(ADMIN_ID)


def is_admin_update(update):
    user = getattr(update, "effective_user", None)
    return bool(user and is_admin_user(user.id))
