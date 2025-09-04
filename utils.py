import sqlite3
import pandas as pd
import streamlit as st
import os
import hashlib
import hmac
from typing import Optional, Dict, List, Tuple, Any

DB_FILE = "MYAdb.db"

def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'

def get_table_names(conn):
    query = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
    return pd.read_sql(query, conn)["name"].tolist()

def get_table_columns(conn, table_name):
    query = f"PRAGMA table_info({quote_ident(table_name)})"
    return pd.read_sql(query, conn)

def insert_row(conn, table_name, data):
    col_names = ", ".join(quote_ident(c) for c in data.keys())
    placeholders = ", ".join(["?"] * len(data))
    query = f"INSERT INTO {quote_ident(table_name)} ({col_names}) VALUES ({placeholders})"
    conn.execute(query, list(data.values()))
    conn.commit()

def init_session_state():
    defaults = {
        "selected_table": None,
        "selected_supplier": None,
        "auth_user": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# -----------------
# Authentication
# -----------------

def _hash_password(raw_password: str, *, iterations: int = 200_000) -> str:
    """Return a salted PBKDF2 hash string: pbkdf2$<iterations>$<salt_hex>$<hash_hex>"""
    if raw_password is None:
        raw_password = ""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", raw_password.encode("utf-8"), salt, iterations)
    return f"pbkdf2${iterations}${salt.hex()}${dk.hex()}"


def _verify_password(raw_password: str, stored_value: str) -> bool:
    """Verify password supporting both PBKDF2 (preferred) and legacy SHA-256 strings."""
    if not stored_value:
        return False
    if stored_value.startswith("pbkdf2$"):
        try:
            _, iter_str, salt_hex, hash_hex = stored_value.split("$", 3)
            iterations = int(iter_str)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(hash_hex)
            dk = hashlib.pbkdf2_hmac("sha256", raw_password.encode("utf-8"), salt, iterations)
            return hmac.compare_digest(dk, expected)
        except Exception:
            return False
    # Legacy fallback: plain SHA-256
    legacy = hashlib.sha256((raw_password or "").encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy, stored_value)


def ensure_users_table() -> None:
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS Users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                role TEXT DEFAULT 'viewer'
            )
            """
        )
        conn.commit()
        # Ensure 'role' column exists for older schemas
        cols = pd.read_sql("PRAGMA table_info(Users)", conn)
        if "role" not in cols["name"].tolist():
            conn.execute("ALTER TABLE Users ADD COLUMN role TEXT DEFAULT 'viewer'")
            conn.commit()
    finally:
        conn.close()


def get_user_count() -> int:
    conn = sqlite3.connect(DB_FILE)
    try:
        row = conn.execute("SELECT COUNT(*) FROM Users").fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def create_user(username: str, raw_password: str, full_name: Optional[str] = None, role: str = "viewer") -> None:
    ensure_users_table()
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute(
            "INSERT INTO Users(username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
            (username, _hash_password(raw_password), full_name, role),
        )
        conn.commit()
    finally:
        conn.close()


def verify_user(username: str, raw_password: str) -> Optional[Dict[str, str]]:
    ensure_users_table()
    conn = sqlite3.connect(DB_FILE)
    try:
        cur = conn.execute(
            "SELECT username, password_hash, full_name, role FROM Users WHERE username = ?",
            (username,),
        )
        row = cur.fetchone()
        if not row:
            return None
        stored_hash = row[1]
        if _verify_password(raw_password, stored_hash):
            user = {"username": row[0], "full_name": row[2], "role": row[3] or "viewer"}
            # Opportunistic upgrade of legacy hashes
            if not stored_hash.startswith("pbkdf2$"):
                try:
                    new_hash = _hash_password(raw_password)
                    conn.execute("UPDATE Users SET password_hash = ? WHERE username = ?", (new_hash, username))
                    conn.commit()
                except Exception:
                    pass
            return user
        return None
    finally:
        conn.close()


def logout_current_user() -> None:
    st.session_state["auth_user"] = None


def require_login(render_sidebar_user: bool = True) -> Optional[Dict[str, str]]:
    """Gate page content behind a login.

    - If no users exist yet, prompt for creating the first admin user.
    - Otherwise, render a login form until authenticated.
    - When logged in, optionally renders user info and Logout in the sidebar.
    """
    init_session_state()
    ensure_users_table()

    # Already logged in
    current_user = st.session_state.get("auth_user")
    if current_user:
        if render_sidebar_user:
            with st.sidebar:
                # Add logo to sidebar
                show_logo()
                
                
                st.caption("Signed in")
                st.write(f"👤 {current_user.get('full_name') or current_user['username']}")
                st.write(f"🔑 Role: {current_user.get('role', 'viewer')}")
                with st.expander("Change password", expanded=False):
                    with st.form("change_pw_form"):
                        new_pw = st.text_input("New password", type="password")
                        new_pw2 = st.text_input("Confirm new password", type="password")
                        submitted_pw = st.form_submit_button("Update password")
                    if submitted_pw:
                        if not new_pw:
                            st.error("Password cannot be empty")
                        elif new_pw != new_pw2:
                            st.error("Passwords do not match")
                        else:
                            try:
                                change_password(current_user["username"], new_pw)
                                st.success("Password updated")
                            except Exception as e:
                                st.error(f"Could not update password: {e}")

                if current_user.get("role") == "admin":
                    with st.expander("Admin: Manage users", expanded=False):
                        st.markdown("**Create user**")
                        with st.form("admin_create_user"):
                            u = st.text_input("Username")
                            fn = st.text_input("Full name")
                            role = st.selectbox("Role", ["viewer", "admin"], index=0)
                            pw = st.text_input("Password", type="password")
                            pw2 = st.text_input("Confirm Password", type="password")
                            submitted_create = st.form_submit_button("Create")
                        if submitted_create:
                            if not u or not pw:
                                st.error("Username and Password are required")
                            elif pw != pw2:
                                st.error("Passwords do not match")
                            else:
                                try:
                                    create_user(u, pw, fn or None, role)
                                    st.success(f"User '{u}' created")
                                except Exception as e:
                                    st.error(f"Could not create user: {e}")

                        st.markdown("---")
                        st.markdown("**Reset user password**")
                        users = [usr for usr in list_usernames() if usr != current_user["username"]]
                        if users:
                            sel = st.selectbox("User", users)
                            with st.form("admin_reset_pw"):
                                npw = st.text_input("New password", type="password")
                                npw2 = st.text_input("Confirm new password", type="password")
                                submitted_reset = st.form_submit_button("Reset")
                            if submitted_reset:
                                if not npw:
                                    st.error("Password cannot be empty")
                                elif npw != npw2:
                                    st.error("Passwords do not match")
                                else:
                                    try:
                                        change_password(sel, npw)
                                        st.success("Password reset")
                                    except Exception as e:
                                        st.error(f"Could not reset password: {e}")

                if st.button("Logout"):
                    logout_current_user()
                    st.success("Logged out")
                    st.rerun()
        return current_user

    # First-run: create initial user if table empty
    if get_user_count() == 0:
        # Add custom CSS for title fonts
        st.markdown("""
        <style>
        h1, h2, h3, h4, h5, h6 {
            font-family: 'CormorantGaramond', serif !important;
            font-weight: 500 !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Add logo to admin setup page
        st.logo("static/Images/MYALogo.png")
        
        st.title("🔐 Set up Admin Account")
        st.info("No users found. Create the first account to continue.")
        with st.form("create_first_user"):
            username = st.text_input("Username")
            full_name = st.text_input("Full name (optional)")
            password = st.text_input("Password", type="password")
            password2 = st.text_input("Confirm Password", type="password")
            submitted = st.form_submit_button("Create Account")
        if submitted:
            if not username or not password:
                st.error("Username and Password are required.")
            elif password != password2:
                st.error("Passwords do not match.")
            else:
                try:
                    # First user becomes admin
                    create_user(username, password, full_name or None, role="admin")
                    st.success("Account created. Please log in.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not create user: {e}")
        st.stop()

    # Normal login flow
    # Add custom CSS for title fonts
    st.markdown("""
    <style>
    h1, h2, h3, h4, h5, h6 {
        font-family: 'CormorantGaramond', serif !important;
        font-weight: 500 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Add logo to login page
    st.logo("static/Images/MYALogo.png")
    
    st.title("🔒 Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")
    if submitted:
        user = verify_user(username, password)
        if user:
            st.session_state["auth_user"] = user
            st.success("Signed in")
            st.rerun()
        else:
            st.error("Invalid username or password")
    st.stop()


def change_password(username: str, new_password: str) -> None:
    ensure_users_table()
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute(
            "UPDATE Users SET password_hash = ? WHERE username = ?",
            (_hash_password(new_password), username),
        )
        conn.commit()
    finally:
        conn.close()


def list_usernames() -> List[str]:
    ensure_users_table()
    conn = sqlite3.connect(DB_FILE)
    try:
        rows = conn.execute("SELECT username FROM Users ORDER BY username").fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def is_admin() -> bool:
    user = st.session_state.get("auth_user")
    return bool(user and user.get("role") == "admin")


def list_users() -> List[Dict[str, Any]]:
    ensure_users_table()
    conn = sqlite3.connect(DB_FILE)
    try:
        rows = conn.execute(
            "SELECT username, full_name, role FROM Users ORDER BY username"
        ).fetchall()
        return [
            {"username": r[0], "full_name": r[1], "role": r[2] or "viewer"}
            for r in rows
        ]
    finally:
        conn.close()


def get_admin_count() -> int:
    ensure_users_table()
    conn = sqlite3.connect(DB_FILE)
    try:
        row = conn.execute("SELECT COUNT(*) FROM Users WHERE role = 'admin'").fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def update_user_role(username: str, new_role: str) -> None:
    ensure_users_table()
    if new_role not in ("admin", "viewer"):
        raise ValueError("Invalid role")
    current = st.session_state.get("auth_user")
    conn = sqlite3.connect(DB_FILE)
    try:
        # if demoting an admin, ensure there's at least one other admin
        row = conn.execute(
            "SELECT role FROM Users WHERE username = ?", (username,)
        ).fetchone()
        if not row:
            raise ValueError("User not found")
        old_role = row[0] or "viewer"
        if old_role == "admin" and new_role != "admin":
            if get_admin_count() <= 1:
                raise ValueError("Cannot demote the last admin")
        conn.execute(
            "UPDATE Users SET role = ? WHERE username = ?",
            (new_role, username),
        )
        conn.commit()
        # If the current user changed their own role, update session
        if current and current.get("username") == username:
            current["role"] = new_role
            st.session_state["auth_user"] = current
    finally:
        conn.close()


def update_full_name(username: str, full_name: Optional[str]) -> None:
    ensure_users_table()
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute(
            "UPDATE Users SET full_name = ? WHERE username = ?",
            (full_name, username),
        )
        conn.commit()
        current = st.session_state.get("auth_user")
        if current and current.get("username") == username:
            current["full_name"] = full_name
            st.session_state["auth_user"] = current
    finally:
        conn.close()


def delete_user(username: str) -> None:
    ensure_users_table()
    current = st.session_state.get("auth_user")
    if current and current.get("username") == username:
        raise ValueError("You cannot delete the currently signed-in user")
    conn = sqlite3.connect(DB_FILE)
    try:
        # Prevent deleting last admin
        row = conn.execute(
            "SELECT role FROM Users WHERE username = ?",
            (username,),
        ).fetchone()
        if not row:
            raise ValueError("User not found")
        role = row[0] or "viewer"
        if role == "admin" and get_admin_count() <= 1:
            raise ValueError("Cannot delete the last admin user")
        conn.execute("DELETE FROM Users WHERE username = ?", (username,))
        conn.commit()
    finally:
        conn.close()

def show_logo():
    st.logo("static/Images/MYAlogo_white.png", icon_image = "static/Images/MYAlogo.png", size = "large")
