from functools import wraps
from flask import Flask, render_template, redirect, url_for, flash, abort, request
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
import smtplib
import os


def send_mail(name, email, phonenum, message):
    MAIL = os.environ.get('MAIL')
    PASSWORD_MAIL = os.environ.get('PASSWORD_MAIL')

    with smtplib.SMTP("smtp.gmail.com") as connection:
        connection.starttls()
        connection.login(user=MAIL, password=PASSWORD_MAIL)
        connection.sendmail(from_addr=MAIL, to_addrs=MAIL, msg=f"Subject: New Login to Blog \n\n Name: {name}\nEmail: {email}\nPhone Number: {phonenum}\nMessage: {message}")


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
ckeditor = CKEditor(app)
Bootstrap(app)

gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False, base_url=None)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL",  "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


##CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)

    posts = relationship("BlogPost", back_populates="author")

    comments = relationship("Comment", back_populates="comment_author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    author = relationship("User", back_populates="posts")
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    comment_author = relationship("User", back_populates='comments')

    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))
    parent_post = relationship("BlogPost", back_populates="comments")


db.create_all()


def admin_only(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if current_user.id != 1:
            return about(403)
        return function(*args, **kwargs)
    return wrapper


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, current_user=current_user)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        name = form.name.data.title()

        if User.query.filter_by(email=email).first():
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))
        else:
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)
            new_user = User(email=email, password=hashed_password, name=name)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=form, current_user=current_user)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        user = User.query.filter_by(email=email).first()

        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
        else:
            hashed_password = user.password
            if not check_password_hash(hashed_password, password):
                flash('Password incorrect, please try again.')
                return redirect(url_for('login'))

            else:
                login_user(user)
                return redirect(url_for('get_all_posts'))

    return render_template("login.html", form=form, current_user=current_user)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    form = CommentForm()
    requested_post = BlogPost.query.get(post_id)

    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment")
            return redirect(url_for('login'))
        else:
            comment_text = form.comment.data
            comment_author = current_user
            parent_post = requested_post

            new_comment = Comment(text=comment_text, comment_author=comment_author, parent_post=parent_post)
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for('show_post', post_id=post_id))
    else:
        return render_template("post.html", post=requested_post, current_user=current_user, form=form)


@app.route("/about")
def about():
    return render_template("about.html", current_user=current_user)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form['name']
        email = request.form['email']
        phonenum = request.form['phonenum']
        msg = request.form['msg']
        send_mail(name, email, phonenum, msg)

        return render_template("contact.html", msg_sent=True)

    if request.method == "GET":
        return render_template("contact.html", msg_sent=False)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data.title(),
            subtitle=form.subtitle.data.title(),
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, current_user=current_user)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data.title()
        post.subtitle = edit_form.subtitle.data.title()
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, current_user=current_user)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>/<int:comment_id>")
@admin_only
def delete_comment(post_id, comment_id):
    comment_to_delete = Comment.query.get(comment_id)
    db.session.delete(comment_to_delete)
    db.session.commit()
    return redirect(url_for('show_post', post_id=post_id))


if __name__ == "__main__":
    app.run()
