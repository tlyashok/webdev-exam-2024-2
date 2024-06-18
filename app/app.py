import os

import bleach
import config
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import (
    UserMixin,
    current_user,
    login_required,
)
from mysqldb import (
    DBConnector,
)
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config.update(
    MYSQL_USER=config.MYSQL_USER,
    MYSQL_PASSWORD=config.MYSQL_PASSWORD,
    MYSQL_HOST=config.MYSQL_HOST,
    MYSQL_DATABASE=config.MYSQL_DATABASE,
    SECRET_KEY=config.SECRET_KEY,
    ADMIN_ROLE_ID=config.ADMIN_ROLE_ID,
    MODERATOR_ROLE_ID=config.MODERATOR_ROLE_ID,
)

application = app


with app.app_context():
    db_connector = DBConnector(app)
    from autorization import bp as auth_bp
    from autorization import init_login_manager
    from users import bp as users_bp

app.register_blueprint(auth_bp)
app.register_blueprint(users_bp)
init_login_manager(app)


if __name__ == '__main__':
    app.run(debug=True)


@app.route('/')
@app.route('/page/<int:page>')
def index(page=1):
    per_page = 10
    offset = (page - 1) * per_page

    conn = db_connector.connect()
    cursor = conn.cursor(dictionary=True)

    # Обновленный запрос для получения средней оценки, количества рецензий и жанров
    query = """
        SELECT Books.*, 
               AVG(Reviews.rating) AS avg_rating, 
               COUNT(Reviews.id) AS review_count,
               GROUP_CONCAT(Genres.name SEPARATOR ', ') AS genres
        FROM Books
        LEFT JOIN Reviews ON Books.id = Reviews.book_id
        LEFT JOIN Book_genre ON Books.id = Book_genre.book_id
        LEFT JOIN Genres ON Book_genre.genre_id = Genres.id
        GROUP BY Books.id
        ORDER BY year DESC
        LIMIT %s OFFSET %s
    """
    cursor.execute(query, (per_page, offset))
    books = cursor.fetchall()

    cursor.execute('SELECT COUNT(*) AS count FROM Books')
    total_books = cursor.fetchone()['count']
    conn.close()

    total_pages = (total_books + per_page - 1) // per_page

    return render_template('index.html', books=books, page=page,
                           total_pages=total_pages, per_page=per_page)



@app.route('/books/<int:book_id>')
def view_book(book_id):
    conn = db_connector.connect()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM Books WHERE id = %s', (book_id,))
    book = cursor.fetchone()

    # Получение жанров книги
    cursor.execute('SELECT Genres.name FROM Genres JOIN Book_genre ON Genres.id = Book_genre.genre_id WHERE Book_genre.book_id = %s', (book_id,))
    genres = cursor.fetchall()
    book['genres'] = [genre['name'] for genre in genres]

    # Получение рецензий и имён пользователей
    cursor.execute('SELECT Reviews.*, Users.login AS user_name FROM Reviews JOIN Users ON Reviews.user_id = Users.id WHERE book_id = %s', (book_id,))
    reviews = cursor.fetchall()

    # Получение пути к обложке книги
    cursor.execute('SELECT file_name FROM Covers WHERE id = %s', (book['cover_id'],))
    cover = cursor.fetchone()
    book['cover_image'] = cover['file_name'] if cover else None

    has_user_reviewed = False
    if current_user.is_authenticated:
        cursor.execute('SELECT * FROM Reviews WHERE book_id = %s AND user_id = %s', (book_id, current_user.id))
        user_review = cursor.fetchone()
        has_user_reviewed = user_review is not None

    conn.close()
    return render_template('view_book.html', book=book, reviews=reviews, has_user_reviewed=has_user_reviewed)




@app.route('/books/create', methods=['GET', 'POST'])
@login_required
def create_book():
    if not current_user.is_admin():
        flash('У вас недостаточно прав для выполнения данного действия.')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            title = request.form['title']
            short_description = request.form['description']  # Добавлено получение краткого описания
            year = request.form['year']
            publisher = request.form['publisher']  # Добавлено получение издательства
            author = request.form['author']  # Добавлено получение автора
            page_count = request.form['pages']  # Добавлено получение объема (в страницах)
            genres = request.form.getlist('genres')
            cover_image = request.files['cover_image']

            if cover_image and cover_image.filename:
                image_hash = generate_md5_hash(cover_image.read())
                cover_image.seek(0)
                cover_image_filename = secure_filename(cover_image.filename)  # Использование secure_filename

                with db_connector.connect() as conn:  # Использование контекстного менеджера
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute('SELECT * FROM Covers WHERE md5_hash = %s', (image_hash,))
                    existing_image = cursor.fetchone()

                    if existing_image:
                        cover_id = existing_image['id']
                    else:
                        cover_image_directory = os.path.join('static', 'images')
                        if not os.path.exists(cover_image_directory):
                            os.makedirs(cover_image_directory)
                        cover_image_path = os.path.join(cover_image_directory,
                                                        cover_image_filename)

                        cursor.execute('INSERT INTO Covers '
                                       '(file_name, mime_type, md5_hash) '
                                       'VALUES (%s, %s, %s)',
                                       (cover_image_filename, cover_image.content_type,
                                        image_hash))
                        cover_id = cursor.lastrowid
                        cover_image.save(cover_image_path)

                    # Транзакция для добавления книги и жанров
                    cursor.execute('INSERT INTO Books (title, short_description, '
                                   'year, publisher, author, pages, cover_id) '
                                   'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                                   (title, short_description, year,
                                    publisher, author, page_count, cover_id))
                    book_id = cursor.lastrowid

                    for genre_id in genres:
                        cursor.execute('INSERT INTO Book_genre (book_id, genre_id) '
                                       'VALUES (%s, %s)',
                                       (book_id, genre_id))
                    conn.commit()  # Одно подтверждение транзакции

            flash('Книга успешно добавлена.')
            return redirect(url_for('index'))
        except Exception as e:
            flash(f'Произошла ошибка: {e}')
            return redirect(url_for('create_book'))

    # Получение жанров вынесено за пределы POST запроса для их отображения в форме
    with db_connector.connect() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT id, name FROM Genres')
        genres = cursor.fetchall()
    return render_template('create_book.html', genres=genres)


@app.route('/books/<int:book_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_book(book_id):
    if not current_user.is_admin() and not current_user.is_moderator():
        flash('У вас недостаточно прав для выполнения данного действия.')
        return redirect(url_for('index'))

    conn = db_connector.connect()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM Books WHERE id = %s', (book_id,))
    book = cursor.fetchone()

    # Получение текущих жанров книги для отображения в форме
    cursor.execute('SELECT genre_id FROM Book_genre WHERE book_id = %s', (book_id,))
    book['genres'] = [genre['genre_id'] for genre in cursor.fetchall()]

    cursor.execute('SELECT id, name FROM Genres')
    genres = cursor.fetchall()

    if request.method == 'POST':
        try:
            title = request.form['title']
            genres = request.form.getlist('genres')
            year = request.form['year']
            description = request.form['description']
            publisher = request.form['publisher']
            author = request.form['author']
            pages = request.form['pages']

            cursor.execute('UPDATE Books SET title = %s, '
                           'year = %s, short_description = %s, '
                           'publisher = %s, author = %s, '
                           'pages = %s WHERE id = %s',
                           (title, year, description, publisher, author, pages, book_id))
            conn.commit()

            # Удаление всех текущих жанров для этой книги
            cursor.execute('DELETE FROM Book_genre WHERE book_id = %s', (book_id,))
            conn.commit()

            # Вставка выбранных жанров для этой книги
            for genre_id in genres:
                cursor.execute('INSERT INTO Book_genre (book_id, genre_id) VALUES (%s, %s)', (book_id, genre_id))
                conn.commit()

            flash('Книга успешно обновлена.')
            return redirect(url_for('view_book', book_id=book_id))
        except Exception as e:
            flash(f'Произошла ошибка при редактировании книги: {e}')
            return redirect(url_for('edit_book', book_id=book_id))
        finally:
            conn.close()

    conn.close()
    return render_template('edit_book.html', book=book, genres=genres)





@app.route('/books/<int:book_id>/delete', methods=['GET'])
@login_required
def delete_book(book_id):
    if not current_user.is_admin():
        flash('У вас недостаточно прав для выполнения данного действия.')
        return redirect(url_for('index'))

    conn = db_connector.connect()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute('SET foreign_key_checks = 0')
        cursor.execute('SELECT * FROM Books WHERE id = %s', (book_id,))
        book = cursor.fetchall()

        if len(book) == 1:
            book = book[0]
            if book['cover_id']:
                cursor.execute('SELECT file_name FROM Covers WHERE id = %s',
                            (book['cover_id'],))
                cover = cursor.fetchone()
                if cover:
                    cursor.execute('DELETE FROM Covers WHERE id = %s',
                            (book['cover_id'],))
                    conn.commit()
                    cover_image_path = os.path.join('static', 'images', cover['file_name'])
                    if os.path.exists(cover_image_path):
                        os.remove(cover_image_path)

            cursor.execute('DELETE FROM Reviews WHERE book_id = %s', (book_id,))
            cursor.execute('DELETE FROM Book_genre WHERE book_id = %s', (book_id,))
            cursor.execute('DELETE FROM Books WHERE id = %s', (book_id,))
            conn.commit()
            flash('Книга и связанные записи успешно удалены.')
        else:
            flash('Книга не найдена.')
    except Exception as e:
        conn.rollback()
        flash(f'Произошла ошибка при удалении книги: {e}')
    finally:
        cursor.execute('SET foreign_key_checks = 1')
        cursor.close()
        conn.close()

    return redirect(url_for('index'))


def generate_md5_hash(file_data):
    import hashlib
    hash_md5 = hashlib.md5()
    hash_md5.update(file_data)
    return hash_md5.hexdigest()


@app.route('/books/<int:book_id>/review', methods=['GET', 'POST'])
@login_required
def write_review(book_id):
    if request.method == 'POST':
        rating = request.form['rating']
        review_text = request.form['text']

        review_text = bleach.clean(review_text)

        conn = db_connector.connect()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO Reviews (book_id, user_id, rating, review_text) VALUES (%s, %s, %s, %s)',
                           (book_id, current_user.id, rating, review_text))
            conn.commit()
            flash('Рецензия успешно добавлена.')
            return redirect(url_for('view_book', book_id=book_id))
        except Exception as e:
            flash(f'Произошла ошибка при добавлении рецензии: {e}')
            return redirect(url_for('review_book', book_id=book_id))
        finally:
            conn.close()

    conn = db_connector.connect()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT title FROM Books WHERE id = %s', (book_id,))
    book = cursor.fetchone()
    conn.close()
    return render_template('write_review.html', book=book)