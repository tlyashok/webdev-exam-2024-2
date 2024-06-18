from functools import wraps

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from users_policy import UsersPolicy

from app import db_connector

bp = Blueprint('auth', __name__, url_prefix='/auth')


class User(UserMixin):
    def __init__(self, user_id, user_login, role_id):
        self.id = user_id
        self.user_login = user_login
        self.role_id = role_id

    def is_admin(self):
        return self.role_id == current_app.config['ADMIN_ROLE_ID']

    def is_moderator(self):
        return self.role_id == current_app.config['MODERATOR_ROLE_ID']

    def can(self, action, user=None):
        self.policy = UsersPolicy(user)
        return getattr(self.policy, action, lambda: 1/0)()


def init_login_manager(app):
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Авторизируйтесь для доступа на эту страницу.'
    login_manager.login_message_category = 'warning'
    login_manager.user_loader(load_user)


def load_user(user_id):
    with db_connector.connect().cursor(dictionary=True) as cursor:
        query = 'SELECT * FROM Users WHERE id = %s'
        cursor.execute(query, (user_id,))
        user = cursor.fetchone()
    return User(user['id'], user['login'], user['role_id']) if user else None


def can_user(action):
    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            user = None
            if 'user_id' in kwargs:
                with db_connector.connect().cursor(dictionary=True) as cursor:
                    cursor.execute('SELECT * FROM Users WHERE id = %s;', (kwargs.get('user_id'),))
                    user = cursor.fetchone()
            if current_user.is_authenticated and not current_user.can(action, user):
                flash('Недостаточно прав для выполнения данного действия', 'warning')
                return redirect(url_for('users.get_users_list'))
            return function(*args, **kwargs)
        return wrapper
    return decorator


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = bool(request.form.get('remember'))

        with db_connector.connect().cursor(dictionary=True) as cursor:
            query = 'SELECT * FROM Users WHERE login = %s AND password = SHA2(%s, 256)'
            cursor.execute(query, (username, password))
            user = cursor.fetchone()

        if user:
            user_obj = User(user['id'], user['login'], user['role_id'])
            login_user(user_obj, remember=remember)
            flash('Успешная авторизация!', category='success')
            ref_url = request.form.get('next')
            return redirect(ref_url) if ref_url else redirect(url_for('index'))

        flash('Неверный логин или пароль!', category='danger')
    return render_template('login.html')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
