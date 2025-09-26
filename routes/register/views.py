# routes/register/views.py
from datetime import datetime
from flask import request, render_template, redirect, url_for, flash, jsonify
from . import register_bp
from models import *
from extensions import db, bcrypt
from utils import is_valid_password, make_unique_slug, send_email

@register_bp.route('/create', endpoint='register_create', methods=['GET', 'POST'])
def register_create():
    form_data = {}
    message = None

    if request.method == 'POST':
        form_data = request.form.to_dict()
        email = form_data.get('email')
        phone = form_data.get('phone_number')
        first_name = form_data.get('first_name')
        last_name = form_data.get('last_name')
        password = form_data.get('password')
        confirm_password = form_data.get('confirm_password')

        if password != confirm_password:
            message = "Passwords do not match."
        else:
            valid, msg = is_valid_password(password)
            if not valid:
                message = msg
            elif User.query.filter_by(email=email).first():
                message = "This email is already registered."
            else:
                # Ellenőrizzük backend oldalon is az adószámot — ha létezik, figyelmeztetünk, de engedjük regisztrálni:
                existing_company = Company.query.filter_by(tax_number=form_data.get('tax_number')).first()
                if existing_company:
                    # flash üzenet a felhasználónak — a frontend is jelzi
                    flash('Ez az adószám már regisztrálva van.', 'error')
                    return render_template('register_create.html', message='Ez az adószám már regisztrálva van.',
                                           form_data=form_data)

                # amikor új company-t hozol létre:
                company = Company(
                    name=form_data.get('company_name'),
                    country=form_data.get('country'),
                    post_code=form_data.get('post_code'),
                    street=form_data.get('street'),
                    house_number=form_data.get('house_number'),
                    tax_number=form_data.get('tax_number'),
                    subscription_type=form_data.get('subscription_type')
                )
                db.session.add(company)
                db.session.flush()  # <-- ekkor kap company.company_id-t

                # most állítsd be a slugot garantáltan egyedire:
                company.slug = make_unique_slug(company.name, company.company_id)

                hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
                user = User(
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    phone_number=phone,
                    hashed_password=hashed_pw,
                    company_id=company.company_id,
                    is_company_admin=True
                )


                db.session.add(user)
                db.session.commit()

                send_email(
                    to_email=email,
                    subject="Registration Successful",
                    body=f"Hello {first_name},\n\nYou have successfully registered the company {company.name}\nThank you for joining us!"
                )

                return redirect(url_for('login.login'))

    return render_template('register_create.html', message=message, form_data=form_data)


@register_bp.route('/choice', endpoint='register_choice')
def register_choice():
    return render_template('register_choice.html')


@register_bp.route('/join', endpoint='register_join', methods=['GET', 'POST'])
def register_join():
    warning = None

    if request.method == 'POST':
        email = request.form.get('email')
        phone = request.form.get('phone_number')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        invite_code_input = request.form.get('invite_code')

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            warning = "Ezzel az e-mail címmel már van regisztrált felhasználó."
            return render_template('register_join.html', warning=warning)

        # Jelszó ellenőrzés
        if password != confirm_password:
            warning = "A jelszavak nem egyeznek."
            return render_template('register_join.html', warning=warning)

        if len(password) < 8 or not any(c.isdigit() for c in password) or not any(c.islower() for c in password) or not any(c.isupper() for c in password):
            warning = "A jelszó nem felel meg a szabályoknak."
            return render_template('register_join.html', warning=warning)

        # Meghívó ellenőrzése
        invite = InviteCode.query.filter_by(code=invite_code_input).first()
        if not invite:
            warning = "A meghívó kód érvénytelen."
            return render_template('register_join.html', warning=warning)

        if invite.is_used:
            warning = "Ez a meghívó kód már felhasználásra került."
            return render_template('register_join.html', warning=warning)

        if invite.expires_at < datetime.now():
            warning = "Ez a meghívó kód lejárt."
            return render_template('register_join.html', warning=warning)

        # Felhasználó létrehozása
        new_user = User(
            email=email,
            phone_number=phone,
            first_name=first_name,
            last_name=last_name,
            hashed_password=bcrypt.generate_password_hash(password).decode('utf-8'),
            company_id=invite.company_id,
            role=invite.role,
            is_company_admin = invite.for_admin
        )

        db.session.add(new_user)

        # Meghívó jelzése felhasználtként
        invite.is_used = True
        db.session.commit()

        flash("Sikeresen csatlakoztál a céghez!", "success")
        return redirect(url_for('login.login'))  # vagy hová szeretnéd irányítani

    return render_template('register_join.html', warning=warning)


@register_bp.route('/check_tax_number')
def check_tax_number():
    tax = request.args.get('tax_number', '').strip()
    if not tax:
        return jsonify({'exists': False})
    exists = Company.query.filter_by(tax_number=tax).first() is not None
    return jsonify({'exists': exists})
