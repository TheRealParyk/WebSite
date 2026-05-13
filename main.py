from flask import Flask, render_template, request, redirect, url_for
import sqlite3

from werkzeug.security import generate_password_hash, check_password_hash

from flask_login import (
    LoginManager, UserMixin, login_user,
    logout_user, login_required, current_user
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Change this in production

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Global DB connection (simple setup)
connection = sqlite3.connect("sqlite.db", check_same_thread=False)
cursor = connection.cursor()


# ❌ Do not close global connection per request
@app.teardown_appcontext
def close_connection(exception):
    pass


class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    user = cursor.execute(
        'SELECT * FROM user WHERE id = ?',
        (int(user_id),)
    ).fetchone()
    if user:
        return User(user[0], user[1], user[2])
    return None


@app.route("/")
def index():
    cursor.execute("""
        SELECT 
            post.id,
            post.title,
            post.content,
            post.author_id,
            user.username,
            COUNT("like".id) AS likes
        FROM post
        JOIN user ON post.author_id = user.id
        LEFT JOIN "like" ON post.id = "like".post_id
        GROUP BY post.id
    """)
    result = cursor.fetchall()

    posts = []
    for post in reversed(result):
        post_data = {
            'id': post[0],
            'title': post[1],
            'content': post[2],
            'author_id': post[3],
            'username': post[4],
            'likes': post[5],
            'liked_posts': []
        }

        if current_user.is_authenticated:
            cursor.execute(
                'SELECT post_id FROM "like" WHERE user_id = ?',
                (current_user.id,)
            )
            post_data['liked_posts'] = [row[0] for row in cursor.fetchall()]

        posts.append(post_data)

    return render_template('index.html', posts=posts)


@app.route('/add/', methods=['GET', 'POST'])
@login_required
def add_post():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')

        if not title or not content:
            return "Title and content are required", 400

        cursor.execute(
            'INSERT INTO post (title, content, author_id) VALUES (?, ?, ?)',
            (title, content, current_user.id)
        )
        connection.commit()
        return redirect(url_for('index'))

    return render_template('add_post.html')


@app.route('/post/<int:post_id>')
def post(post_id):
    result = cursor.execute(
        'SELECT * FROM post JOIN user ON post.author_id = user.id WHERE post.id = ?',
        (post_id,)
    ).fetchone()

    if not result:
        return "Post not found", 404

    post_dict = {
        'id': result[0],
        'title': result[1],
        'content': result[2],
        'author_id': result[3],
        'username': result[5]
    }

    return render_template('post.html', post=post_dict)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            cursor.execute(
                'INSERT INTO user (username, password_hash) VALUES (?, ?)',
                (
                    request.form.get('username'),
                    generate_password_hash(request.form.get('password'))
                )
            )
            connection.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template(
                'register.html',
                message='Username already exists!'
            )

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = cursor.execute(
            'SELECT * FROM user WHERE username = ?',
            (request.form.get('username'),)
        ).fetchone()

        if user and User(user[0], user[1], user[2]).check_password(
            request.form.get('password')
        ):
            login_user(User(user[0], user[1], user[2]))
            return redirect(url_for('index'))

        return render_template(
            'login.html',
            message='Invalid username or password'
        )

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/delete/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = cursor.execute(
        'SELECT * FROM post WHERE id = ?',
        (post_id,)
    ).fetchone()

    if post and post[3] == current_user.id:
        cursor.execute('DELETE FROM post WHERE id = ?', (post_id,))
        connection.commit()

    return redirect(url_for('index'))


def user_is_liking(user_id, post_id):
    return cursor.execute(
        'SELECT 1 FROM "like" WHERE user_id = ? AND post_id = ?',
        (user_id, post_id)
    ).fetchone() is not None


@app.route('/like/<int:post_id>')
@login_required
def like_post(post_id):
    post = cursor.execute(
        'SELECT * FROM post WHERE id = ?',
        (post_id,)
    ).fetchone()

    if not post:
        return 'Post not found', 404

    if user_is_liking(current_user.id, post_id):
        cursor.execute(
            'DELETE FROM "like" WHERE user_id = ? AND post_id = ?',
            (current_user.id, post_id)
        )
    else:
        cursor.execute(
            'INSERT INTO "like" (user_id, post_id) VALUES (?, ?)',
            (current_user.id, post_id)
        )

    connection.commit()
    return redirect(url_for('index'))


if __name__ == "__main__":
    app.run(debug=True)





