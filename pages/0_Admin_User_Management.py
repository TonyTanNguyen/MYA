import streamlit as st
from utils import require_login, is_admin, list_users, update_user_role, update_full_name, delete_user, change_password, create_user, show_logo

# Add custom CSS for title fonts
st.markdown("""
<style>
h1, h2, h3, h4, h5, h6 {
    font-family: 'CormorantGaramond', serif !important;
    font-weight: 500 !important;
}
</style>
""", unsafe_allow_html=True)

require_login()

st.title("🛡️ Admin • User Management")
show_logo()
if not is_admin():
    st.error("You do not have permission to view this page.")
    st.stop()

st.markdown("Manage application users, roles, and passwords.")

st.markdown("---")

with st.expander("Create new user", expanded=False):
    with st.form("admin_create_user_full"):
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("Username")
            role = st.selectbox("Role", ["viewer", "admin"], index=0)
        with col2:
            full_name = st.text_input("Full name")
        pw = st.text_input("Password", type="password")
        pw2 = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create user")
    if submitted:
        if not username or not pw:
            st.error("Username and Password are required")
        elif pw != pw2:
            st.error("Passwords do not match")
        else:
            try:
                create_user(username, pw, full_name or None, role)
                st.success(f"User '{username}' created")
            except Exception as e:
                st.error(f"Could not create user: {e}")

st.markdown("---")

st.subheader("Users")
users = list_users()
if not users:
    st.info("No users found.")
else:
    for user in users:
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
            with col1:
                st.markdown(f"**Username:** {user['username']}")
                st.caption(f"Full name: {user.get('full_name') or '—'}")
            with col2:
                new_full_name = st.text_input(
                    "Edit full name",
                    value=user.get("full_name") or "",
                    key=f"full_{user['username']}"
                )
                if st.button("Save name", key=f"save_name_{user['username']}"):
                    try:
                        update_full_name(user["username"], new_full_name or None)
                        st.success("Saved")
                    except Exception as e:
                        st.error(str(e))
            with col3:
                new_role = st.selectbox(
                    "Role",
                    ["viewer", "admin"],
                    index=0 if user.get("role") != "admin" else 1,
                    key=f"role_{user['username']}"
                )
                if st.button("Update role", key=f"role_btn_{user['username']}"):
                    try:
                        update_user_role(user["username"], new_role)
                        st.success("Role updated")
                    except Exception as e:
                        st.error(str(e))
            with col4:
                with st.popover("Password/Deletion"):
                    st.caption(f"Actions for {user['username']}")
                    npw = st.text_input("New password", type="password", key=f"npw_{user['username']}")
                    npw2 = st.text_input("Confirm new password", type="password", key=f"npw2_{user['username']}")
                    if st.button("Reset password", key=f"rst_{user['username']}"):
                        if not npw:
                            st.error("Password cannot be empty")
                        elif npw != npw2:
                            st.error("Passwords do not match")
                        else:
                            try:
                                change_password(user["username"], npw)
                                st.success("Password reset")
                            except Exception as e:
                                st.error(str(e))
                    st.markdown("---")
                    if st.button("Delete user", key=f"del_{user['username']}"):
                        try:
                            delete_user(user["username"])
                            st.success("User deleted")
                        except Exception as e:
                            st.error(str(e))


