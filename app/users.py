import re

import mysql.connector
from autorization import (
    can_user,
)
from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    current_user,
    login_required,
)

from app import (
    db_connector,
)

bp = Blueprint('users', __name__, url_prefix='/users')


def is_valid_password(password):
    errors = {}
    if len(password) < 8 or len(password) > 128:
        errors['password'] = (
            'Пароль должен содержать от 8 до 128 символов'
        )
    if not re.search(r'[A-Z]', password):
        errors['password'] = (
            'Пароль должен содержать хотя бы одну заглавную букву'
        )
    if not re.search(r'[a-z]', password):
        errors['password'] = (
            'Пароль должен содержать хотя бы одну строчную букву'
        )
    if not re.search(r'\d', password):
        errors['password'] = (
            'Пароль должен содержать хотя бы одну цифру'
        )
    if ' ' in password:
        errors['password'] = (
            'Пароль не должен содержать пробелы'
        )
    if not re.match(
        r'^[a-zA-Zа-яА-Я\d~!@#\$%\^&\*_\-\+\(\)\[\]{}><\\/\|"\',.:;]+$',
        password,
    ):
        errors['password'] = (
            'Пароль может содержать только допустимые символы'
        )
    if len(errors) == 0:
        return (True, errors)
    return (False, errors)


def validate_user_data(login, password, first_name, last_name):
    errors = {}
    if not (login and password and first_name and last_name):
        errors['required_fields'] = (
            'Не все обязательные поля заполнены'
        )
    if not re.match(r'^[a-zA-Z0-9]{5,}$', login):
        errors['login_format'] = (
            'Логин должен состоять только из латинских букв и цифр '
            'и иметь длину не менее 5 символов'
        )

    errors.update(is_valid_password(password)[1])
    return errors


def get_roles():
    try:
        with db_connector.connect().cursor(dictionary=True) as cursor:
            cursor.execute('SELECT id, name FROM Roles')
            roles = cursor.fetchall()
    except:  # noqa: E722
        flash('Ошибка получения ролей', category='danger')
        roles = []
    return roles


@bp.route('/users-list')
@can_user('read')
def get_users_list():
    with db_connector.connect().cursor(dictionary=True) as cursor:
        query = """
            SELECT Users.id, Users.login, Users.password, 
                   Users.last_name, Users.first_name, Users.middle_name, 
                   Users.created_at, 
                   Roles.name as role_name 
            FROM Users 
            LEFT JOIN Roles ON Users.role_id = Roles.id
        """  # noqa: W291
        cursor.execute(query)
        users = cursor.fetchall()

    return render_template('users-list.html', users=users)


@bp.route('/create-user', methods=['GET', 'POST'])
# @login_required
# @can_user('create')
def create_user():
    user = {}
    if request.method == 'POST':
        login = request.form['login']
        password = request.form['password']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        middle_name = request.form.get('middle_name')
        role_id = request.form['role_id']

        user = {
            'login': login,
            'first_name': first_name,
            'last_name': last_name,
            'middle_name': middle_name,
            'role_id': role_id,
        }

        # Валидация данных пользователя
        errors = validate_user_data(login, password, first_name, last_name)

        if errors:
            return render_template('create-user.html', user=user, roles=get_roles(),
                                   errors=errors)

        try:
            # Сохранение пользователя в базу данных
            with db_connector.connect().cursor() as cursor:
                query = """
                    INSERT INTO Users (login, password, last_name, first_name,
                                    middle_name, role_id)
                    VALUES (%s, SHA2(%s, 256), %s, %s, %s, %s)
                """
                cursor.execute(query, (login, password, last_name,
                                       first_name, middle_name, role_id))
                db_connector.connect().commit()

            # Перенаправление на страницу со списком пользователей
            return redirect(url_for('users.get_users_list'))
        except mysql.connector.IntegrityError as integrity_err:
            db_connector.connect().rollback()
            if integrity_err.errno == 1062:
                errors['duplicate_login'] = (
                    'Пользователь с таким логином уже существует'
                )
            else:
                errors['database_error'] = (
                    'Ошибка создания пользователя'
                )
            return render_template('create-user.html', user=user, roles=get_roles(),
                                   errors=errors)
    return render_template('create-user.html', user=user, roles=get_roles())

@bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@can_user('update')
def edit_user(user_id):
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        middle_name = request.form.get('middle_name')
        role_id = request.form.get('role_id')

        if not (first_name and last_name):
            flash('Не все обязательные поля заполнены', category='danger')
            return redirect(url_for('users.create_user'))

        try:
            with db_connector.connect().cursor() as cursor:
                if current_user.can('assign_roles'):
                    query = """
                        UPDATE Users SET 
                        last_name = %s, first_name = %s, middle_name = %s,
                        role_id = %s WHERE id = %s
                    """  # noqa: W291
                    cursor.execute(query, (last_name, first_name,
                                           middle_name, role_id, user_id))
                    db_connector.connect().commit()
                else:
                    query = """
                        UPDATE Users SET 
                        last_name = %s, first_name = %s, middle_name = %s 
                        WHERE id = %s
                    """  # noqa: W291
                    cursor.execute(query, (last_name, first_name,
                                           middle_name, user_id))
                    db_connector.connect().commit()

            flash('Запись пользователя успешно обновлена', category='success')

            return redirect(url_for('users.get_users_list'))
        except mysql.connector.IntegrityError as integrity_err:
            db_connector.connect().rollback()
            if integrity_err.error == 1062:
                flash('Пользователь с таким логином уже существует',
                      category='danger')
            else:
                flash('Ошибка обновления пользователя',
                      category='danger')
            return redirect(url_for('users.get_users_list'))
    elif request.method == 'GET':
        query = ("""
            SELECT * FROM Users WHERE id = %s
        """)
        with db_connector.connect().cursor(dictionary=True) as cursor:
            cursor.execute(query, (user_id, ))
            user = cursor.fetchone()
    errors = {}
    return render_template('edit-user.html', user=user, errors=errors, roles=get_roles())



@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@can_user('delete')
def delete_user(user_id):
    try:
        with db_connector.connect().cursor() as cursor:
            query = """
                SELECT id FROM Users WHERE id = %s
            """
            cursor.execute(query, (user_id,))
            user = cursor.fetchone()

        if not user:
            flash('Пользователь не найден', category='danger')
            return redirect(url_for('users.get_users_list'))

        with db_connector.connect().cursor() as cursor:
            query = """
                DELETE FROM Users WHERE id = %s
            """
            cursor.execute(query, (user_id,))
            db_connector.connect().commit()

        flash('Пользователь успешно удален', category='success')
        return redirect(url_for('users.get_users_list'))

    except mysql.connector.Error as e:
        flash(f'Ошибка удаления пользователя: {e!s}', category='danger')
        return redirect(url_for('users.get_users_list'))


@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_password = request.form['old_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        cur_user_username = current_user.username

        with db_connector.connect().cursor() as cursor:
            query = """
                SELECT * FROM Users WHERE 
                password = SHA2(%s, 256) AND login = %s
            """  # noqa: W291
            cursor.execute(query, (old_password, cur_user_username))
            user = cursor.fetchone()
            if not bool(user):
                flash('Неверный старый пароль', category='danger')
                return redirect(url_for('users.change_password'))

        check_pass = is_valid_password(new_password)

        if not check_pass[0]:
            return render_template('change-password.html', errors=check_pass[1])

        if old_password == new_password:
            flash('Старый и новый пароль не должны совпадать', category='danger')
            return redirect(url_for('users.change_password'))

        if new_password != confirm_password:
            flash('Новый пароль и подтверждение пароля не совпадают',
                  category='danger')
            return redirect(url_for('users.change_password'))


        with db_connector.connect().cursor() as cursor:
            query = """
                UPDATE Users SET 
                password = SHA2(%s, 256) 
                WHERE login = %s
            """  # noqa: W291
            cursor.execute(query, (new_password, cur_user_username))
            db_connector.connect().commit()

        flash('Пароль успешно изменен', category='success')
        return redirect(url_for('index'))

    return render_template('change-password.html')
