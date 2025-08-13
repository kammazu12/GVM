import re
from flask import Flask, render_template, request, flash, redirect, url_for
from main import db, User

app = Flask(__name__)
app.secret_key = "valami_szupertitkos"

def is_strong_password(password):
    """Ellenőrzi a jelszó erősségét"""
    if len(password) < 8:
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        if not is_strong_password(password):
            flash("A jelszónak legalább 8 karakter hosszúnak kell lennie, tartalmaznia kell kis- és nagybetűt, számot és speciális karaktert.")
            return redirect(url_for("register"))

        # Ha erős, létrehozod a felhasználót
        new_user = User(email=email, hashed_password=password)
        db.session.add(new_user)
        db.session.commit()
        flash("Sikeres regisztráció!")
        return redirect(url_for("register"))

    return render_template("register.html")
