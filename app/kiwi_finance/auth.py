import bcrypt
from functools import wraps
from flask import session, redirect, url_for, request

from kiwi_finance.database import create_user, get_user_by_email


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login_page", next=request.path))
        return f(*args, **kwargs)
    return decorated


def register_user(email: str, password: str):
    """Returns (user_id, error). error is None on success."""
    if not email or not password:
        return None, "Email and password are required."
    if len(password) < 8:
        return None, "Password must be at least 8 characters."
    if get_user_by_email(email):
        return None, "An account with that email already exists."
    user_id = create_user(email, hash_password(password))
    return user_id, None


def authenticate_user(email: str, password: str):
    """Returns (user, error). error is None on success."""
    user = get_user_by_email(email)
    if not user or not check_password(password, user["password_hash"]):
        return None, "Invalid email or password."
    return user, None
