# routes/profile/views.py
import traceback
from flask_login import login_required, current_user
from flask import request, render_template, redirect, url_for, flash, jsonify
from . import profile_bp
from utils import *
from models import *
from extensions import *

@profile_bp.route('/change_password', methods=['GET', 'POST'])
@login_required
@no_cache
def change_password():
    message = None

    if request.method == 'POST':
        current_pwd = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not bcrypt.check_password_hash(current_user.hashed_password, current_pwd):
            message = "Current password is incorrect."
            return render_template('change_password.html', message=message)

        if new_password != confirm_password:
            message = "Passwords do not match."
            return render_template('change_password.html', message=message)

        valid, msg = is_valid_password(new_password)
        if not valid:
            message = msg
            return render_template('change_password.html', message=message)

        current_user.hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        db.session.commit()

        flash("Your password has been updated.", "success")
        return redirect(url_for('profile'))

    return render_template('change_password.html', message=message)


@profile_bp.route("/profile")
@login_required
@no_cache
def profile():
    user = current_user
    # Csak bejövő, még nem látott ajánlatok
    unseen_incoming_offers_count = Offer.query.join(Cargo)\
        .filter(Offer.offer_user_id == user.user_id, Offer.seen==0, Cargo.user_id != user.user_id)\
        .count()
    return render_template("profile.html", user=user, unseen_incoming_offers_count=unseen_incoming_offers_count)


@profile_bp.route("/edit_profile", methods=["GET", "POST"])
@login_required
@no_cache
def edit_profile():
    user = current_user
    if request.method == "POST":
        # Űrlap adatainak beolvasása
        user.first_name = request.form.get("first_name").strip()
        user.last_name = request.form.get("last_name").strip()
        user.phone_number = request.form.get("phone_number").strip()
        new_email = request.form.get("email").strip()

        # Ha email változott, ellenőrizzük hogy nincs-e már foglalt
        if new_email != user.email:
            if User.query.filter_by(email=new_email).first():
                flash("Ez az e-mail cím már használatban van!", "error")
                return redirect(url_for("edit_profile"))
            user.email = new_email

        db.session.commit()
        flash("Profil sikeresen frissítve!", "success")
        return redirect(url_for("profile"))

    return render_template("edit_profile.html", user=user)


@profile_bp.route('/upload_profile_picture', methods=['POST'])
@login_required
@no_cache
def upload_profile_picture():
    success, result = save_uploaded_image(
        request.files.get('profile_picture'),
        subfolder='profile_pictures',
        prefix=f"user_{current_user.user_id}_",
        allowed_extensions=ALLOWED_EXTENSIONS
    )

    if not success:
        return {"success": False, "error": result}, 400

    # régi kép törlése, ha nem default
    old_path = os.path.join(current_app.root_path, 'static/uploads/profile_pictures', current_user.profile_picture or "")
    if current_user.profile_picture and os.path.exists(old_path) and current_user.profile_picture != "default.png":
        try:
            os.remove(old_path)
        except Exception:
            pass

    current_user.profile_picture = result
    db.session.commit()

    return {"success": True, "filename": result}


@profile_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    message = None
    prt = PasswordResetToken.query.filter_by(token=token).first()
    if prt is None or prt.expires_at < datetime.now():
        flash("The password reset link is invalid or has expired.", "danger")
        return redirect(url_for('login.login'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if new_password != confirm_password:
            message = "Passwords do not match."
            return render_template('reset_password.html', message=message)
        valid, msg = is_valid_password(new_password)
        if not valid:
            message = msg
            return render_template('reset_password.html', message=message)

        user = prt.user
        user.hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        db.session.delete(prt)  # token egyszeri használat
        db.session.commit()
        flash("Your password has been reset. Please log in with your new password.", "success")
        return redirect(url_for('login.login'))

    return render_template('reset_password.html', message=message)


@profile_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    message = None
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        # Biztonság: mindig ugyanazt az üzenetet küldjük vissza
        if user:
            token = PasswordResetToken.generate_for_user(user, hours_valid=1)
            reset_link = url_for('profile.reset_password', token=token, _external=True)
            body = (
                f"Hello {user.first_name},\n\n"
                f"Kattints erre a linkre a jelszavad visszaállításához (a link 1 óráig érvényes):\n\n"
                f"{reset_link}\n\n"
                "Ha nem te kérted ezt, kérjük, hagyd figyelmen kívül ezt az üzenetet."
            )
            send_email(to_email=user.email, subject="Password Reset Request", body=body)
        message = "Password reset link has been sent to your email (if the address exists)."
    return render_template('forgot_password.html', message=message)


@profile_bp.route('/get_user_offers')
@login_required
@no_cache
def get_user_offers():
    try:
        # --- Bejövő ajánlatok ---
        incoming_query = (
            db.session.query(Offer, Cargo, User)
            .join(Cargo, Offer.cargo_id == Cargo.cargo_id)
            .join(User, Offer.offer_user_id == User.user_id)
            .filter(Cargo.user_id == current_user.user_id)
            .order_by(Offer.created_at.desc())
            .all()
        )

        result_in = []
        for offer, cargo, user in incoming_query:
            pickups = [loc.city for loc in cargo.locations if loc.type == 'pickup']
            dropoffs = [loc.city for loc in cargo.locations if loc.type == 'dropoff']

            origin_display = pickups[0] if pickups else ''
            origin_extra = len(pickups) - 1 if len(pickups) > 1 else 0

            destination_display = dropoffs[-1] if dropoffs else ''
            destination_extra = len(dropoffs) - 1 if len(dropoffs) > 1 else 0

            result_in.append({
                'offer_id': offer.offer_id,
                'cargo_id': cargo.cargo_id,
                'offer_user_id': offer.offer_user_id,  # <<< ide kell!
                'from_user': f"{user.first_name} {user.last_name}",
                'user_company': user.company.name if user.company else '',
                'profile_picture': url_for('static', filename='uploads/profile_pictures/' + (
                            user.profile_picture or 'default.png')),
                'origin': origin_display,
                'origin_extra_count': origin_extra,
                'destination': destination_display,
                'destination_extra_count': destination_extra,
                'price': offer.price,
                'currency': offer.currency,
                'note': offer.note,
                'pickup_date': offer.pickup_date.strftime('%Y-%m-%d') if offer.pickup_date else '',
                'arrival_date': offer.arrival_date.strftime('%Y-%m-%d') if offer.arrival_date else '',
                'date': offer.created_at.strftime('%Y-%m-%d %H:%M'),
                'direction': "in",
                'cargo_owner_id': cargo.user_id,
                'seen': bool(offer.seen),
                'status': offer.status
            })

        # --- Kimenő ajánlatok ---
        outgoing_query = (
            db.session.query(Offer, Cargo, User)
            .join(Cargo, Offer.cargo_id == Cargo.cargo_id)
            .join(User, Cargo.user_id == User.user_id)
            .filter(Offer.offer_user_id == current_user.user_id)
            .order_by(Offer.created_at.desc())
            .all()
        )

        result_out = []
        for offer, cargo, user in outgoing_query:
            pickups = [loc.city for loc in cargo.locations if loc.type == 'pickup']
            dropoffs = [loc.city for loc in cargo.locations if loc.type == 'dropoff']

            origin_display = pickups[0] if pickups else ''
            origin_extra = len(pickups) - 1 if len(pickups) > 1 else 0

            destination_display = dropoffs[-1] if dropoffs else ''
            destination_extra = len(dropoffs) - 1 if len(dropoffs) > 1 else 0

            result_out.append({
                'offer_id': offer.offer_id,
                'cargo_id': cargo.cargo_id,
                'offer_user_id': offer.offer_user_id,  # <<< ide is kell!
                'from_user': f"{current_user.first_name} {current_user.last_name}",
                'to_user': f"{user.first_name} {user.last_name}",
                'partner_company': user.company.name if user.company else '',
                'profile_picture': url_for('static', filename='uploads/profile_pictures/' + (
                            user.profile_picture or 'default.png')),
                'origin': origin_display,
                'origin_extra_count': origin_extra,
                'destination': destination_display,
                'destination_extra_count': destination_extra,
                'price': offer.price,
                'currency': offer.currency,
                'note': offer.note,
                'pickup_date': offer.pickup_date.strftime('%Y-%m-%d') if offer.pickup_date else '',
                'arrival_date': offer.arrival_date.strftime('%Y-%m-%d') if offer.arrival_date else '',
                'date': offer.created_at.strftime('%Y-%m-%d %H:%M'),
                'direction': "out",
                'cargo_owner_id': cargo.user_id,
                'seen': bool(offer.seen),
                'status': offer.status
            })

        return jsonify({"incoming": result_in, "outgoing": result_out})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@profile_bp.route("/settings")
@login_required
@no_cache
def settings():
    return render_template("settings.html", user=current_user)


@profile_bp.route("/save_settings", methods=["POST"])
@login_required
@no_cache
def save_settings():
    settings = current_user.settings
    if not settings:
        settings = UserSettings(user_id=current_user.user_id)
        db.session.add(settings)

    settings.dark_mode = bool(request.form.get("dark_mode"))
    settings.colorblind = bool(request.form.get("colorblind"))
    settings.low_quality = bool(request.form.get("low_quality"))
    lang = request.form.get("language")
    if lang in ["hu", "en", "de"]:
        settings.language = lang
    db.session.commit()
    # flash("Beállítások elmentve!", "success")
    return redirect(url_for("profile.settings"))


@profile_bp.route("/set_language", methods=["POST"])
@login_required
@no_cache
def set_language():
    language = request.json.get("language")
    if language not in ["hu", "en", "de"]:
        return jsonify({"success": False, "error": "Invalid language"}), 400

    current_user.language = language
    db.session.commit()
    return jsonify({"success": True})


@profile_bp.route('/subscription', methods=['GET', 'POST'])
@login_required
@no_cache
def subscription():
    if not current_user.company:
        flash("Nincs céged, nem tudsz előfizetést módosítani.", "warning")
        return redirect(url_for('profile.settings'))

    company = current_user.company

    if request.method == 'POST':
        if not current_user.is_company_admin:
            flash("Nincs jogosultságod az előfizetés módosításához.", "danger")
            return redirect(url_for('profile.subscription'))

        plan = request.form.get('plan')
        if plan not in ['basic', 'advanced', 'pro']:
            flash("Érvénytelen csomag.", "danger")
            return redirect(url_for('profile.subscription'))

        company.subscription_type = plan
        db.session.commit()
        flash(f"A cég előfizetése sikeresen módosítva: {plan}", "success")
        return redirect(url_for('profile.subscription'))

    return render_template(
        'subscriptions.html',
        company=company,
        user=current_user
    )
