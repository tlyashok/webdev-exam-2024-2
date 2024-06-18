from flask import current_app
from flask_login import current_user


class UsersPolicy:
    def __init__(self, user):
        self.user = user

    def create(self):
        return current_user.is_admin()

    def read(self):
        return True

    def update(self):
        if self.user is not None:  # noqa: SIM102
            if current_user.is_admin() or current_user.is_moderator() and self.user['role_id'] != current_app.config['ADMIN_ROLE_ID']:  # noqa: E501
                return True
        return False

    def delete(self):
        return current_user.is_admin()

    def assign_roles(self):
        return current_user.is_admin()
