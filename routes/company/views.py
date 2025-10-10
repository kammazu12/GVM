# routes/company/views.py
from flask import request, render_template, redirect, url_for, flash, jsonify, abort
from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload
from models.cargo import CargoLocation
from . import company_bp
from utils import *
from models import *
from flask_login import current_user, login_required


@company_bp.route('/companies')
@login_required
@no_cache
def companies():
    search = request.args.get('search', '').strip()

    blocked_ids = db.session.query(CompanyBlocklist.blocked_company_id).filter_by(
        blocker_company_id=current_user.company_id
    )
    blocked_by_others_ids = db.session.query(CompanyBlocklist.blocker_company_id).filter_by(
        blocked_company_id=current_user.company_id
    )
    all_blocked_ids = blocked_ids.union_all(blocked_by_others_ids).subquery()


    # --- alap query: nem tiltott cégek ---
    query = Company.query.filter(
        ~Company.company_id.in_(
            db.session.query(CompanyBlocklist.blocked_company_id).filter_by(
                blocker_company_id=current_user.company_id
            )
        )
    )

    query = query.filter(
        Company.company_id != current_user.company_id,
        ~Company.company_id.in_(all_blocked_ids)
    )

    # --- keresés, ha van ---
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Company.name.ilike(search_term),
                Company.tax_number.ilike(search_term),
                Company.country.ilike(search_term)
            )
        )

    companies = query.all()

    return render_template(
        'companies.html',
        user=current_user,
        companies=companies,
        search=search
    )


@company_bp.route('/my_company')
@login_required
@no_cache
def my_company():
    if not current_user.company_id:
        flash("Nem tartozol egyetlen céghez sem.", "warning")
        return redirect(url_for('company.companies'))

    company = Company.query.get(current_user.company_id)
    if not company:
        flash("A céged nem található.", "danger")
        return redirect(url_for('company.companies'))

    # Cég összes hirdetett fuvara
    cargos = (Cargo.query
              .filter(Cargo.company_id == company.company_id)
              .join(CargoLocation, Cargo.cargo_id == CargoLocation.cargo_id)
              .filter(CargoLocation.type == 'pickup')
              .order_by(CargoLocation.start_date.desc())
              .all())

    return render_template(
        'my_company.html',
        company=company,
        is_company_admin=current_user.is_company_admin,
        now=datetime.now(),
        current_user_role = current_user.role,  # ez kell az Owner feltételhez
        current_user_id = current_user.user_id,  # ez kell az Owner feltételhez
        cargos=cargos,
        user=current_user,
        current_year=datetime.now().year
    )


@company_bp.route("/company/<int:company_id>/promote/<int:user_id>", methods=["POST"])
@login_required
@no_cache
def promote_user(company_id, user_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"success": False, "error": "Cég nem található."}), 404

    if current_user.company_id != company_id:
        return jsonify({"success": False, "error": "Nincs jogosultságod."}), 403

    is_owner = bool(getattr(current_user, "role", None)) and str(current_user.role).lower() == "owner"
    is_company_admin = bool(getattr(current_user, "is_company_admin", False))

    if not (is_owner or is_company_admin):
        return jsonify({"success": False, "error": "Nincs jogosultságod."}), 403

    user = User.query.get(user_id)
    if not user or user.company_id != company_id:
        return jsonify({"success": False, "error": "Felhasználó nem található."}), 404

    if is_owner:
        user.is_company_admin = not bool(user.is_company_admin)
    else:
        user.is_company_admin = True

    db.session.commit()
    return jsonify({"success": True, "redirect": url_for("company.my_company")})


@company_bp.route("/company/<int:company_id>/remove/<int:user_id>", methods=["POST"])
@login_required
@no_cache
def remove_user(company_id, user_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"success": False, "error": "Cég nem található."}), 404

    if (not current_user.is_company_admin and current_user.role.lower() != "owner") or current_user.company_id != company_id:
        return jsonify({"success": False, "error": "Nincs jogosultságod."}), 403

    user = User.query.get(user_id)
    if not user or user.company_id != company_id:
        return jsonify({"success": False, "error": "Felhasználó nem található a cégnél."}), 404

    user.company_id = None
    user.is_company_admin = False
    db.session.commit()
    return jsonify({"success": True, "redirect": url_for("company.my_company")})


@company_bp.route('/upload_company_logo', methods=['POST'])
@login_required
@no_cache
def upload_company_logo():
    if not current_user.is_company_admin or not current_user.company_id:
        return {"success": False, "error": "Nincs jogosultságod."}, 403

    success, result = save_uploaded_image(
        request.files.get('logo'),
        subfolder='company_logos',
        prefix='company_',
        allowed_extensions=ALLOWED_EXTENSIONS
    )

    if not success:
        return {"success": False, "error": result}, 400

    company = Company.query.get(current_user.company_id)
    company.logo_filename = result
    db.session.commit()

    return {"success": True, "filename": result}


@company_bp.route('/generate_invite', methods=['POST'])
@login_required
@no_cache
def generate_invite():
    if not current_user.is_company_admin or not current_user.company_id:
        flash("Nincs jogosultságod meghívó létrehozásához.", "danger")
        return redirect(url_for('company.my_company'))

    i = 0
    invites_created = []

    # Dinamikus form feldolgozása
    while f"invites[{i}][email]" in request.form:
        email = request.form.get(f"invites[{i}][email]")
        if not email:
            i += 1
            continue

        role = request.form.get(f"invites[{i}][role]", "user")
        for_admin = bool(request.form.get(f"invites[{i}][for_admin]"))

        # Egyedi kód generálása
        while True:
            code = secrets.token_urlsafe(8)
            if not InviteCode.query.filter_by(code=code).first():
                break

        # Meghívó objektum létrehozása
        invite = InviteCode(
            code=code,
            company_id=current_user.company_id,
            role=role,
            for_admin=for_admin,
            expires_at=datetime.now() + timedelta(hours=1),
            is_used=False
        )
        db.session.add(invite)
        invites_created.append((email, code))
        i += 1

    db.session.commit()

    for email, code in invites_created:
        try:
            send_invite_email(email, code)
        except Exception as e:
            print(f"Hiba az e-mail küldéskor {email}: {e} {datetime.now()}")

    flash(f"{len(invites_created)} meghívó létrehozva.", "success")
    return redirect(url_for('company.my_company'))


@company_bp.route('/search_companies')
@login_required
@no_cache
def search_companies():
    query_text = request.args.get('q', '').strip()

    # --- lekérdezzük, kiket tiltottunk és kik tiltottak minket ---
    blocked_ids = db.session.query(CompanyBlocklist.blocked_company_id).filter_by(
        blocker_company_id=current_user.company_id
    )

    blocked_by_others_ids = db.session.query(CompanyBlocklist.blocker_company_id).filter_by(
        blocked_company_id=current_user.company_id
    )

    # összes tiltott ID = akiket mi tiltottunk VAGY akik minket tiltottak
    all_blocked_ids = blocked_ids.union_all(blocked_by_others_ids).subquery()

    # --- alap query ---
    query = Company.query.options(joinedload(Company.users)).filter(
        Company.company_id != current_user.company_id,  # saját cég sose szerepeljen
        ~Company.company_id.in_(all_blocked_ids)        # sem a tiltottak
    )

    # --- keresés ---
    if query_text:
        query = query.outerjoin(User).filter(
            or_(
                Company.name.ilike(f'%{query_text}%'),
                Company.tax_number.ilike(f'%{query_text}%'),
                Company.country.ilike(f'%{query_text}%'),
                func.concat(User.first_name, ' ', User.last_name).ilike(f'%{query_text}%')
            )
        ).distinct()

    results = query.all()

    # --- adatok JSON-ra alakítása ---
    companies_data = []
    for c in results:
        emp_count = len(c.users) if hasattr(c, 'users') and c.users is not None else 0
        companies_data.append({
            'company_id': c.company_id,
            'name': c.name,
            'slug': c.slug or make_unique_slug(c.name, c.company_id),
            'country': c.country,
            'post_code': c.post_code,
            'street': c.street,
            'house_number': c.house_number,
            'tax_number': c.tax_number,
            'created_at': c.created_at.strftime('%Y-%m-%d') if c.created_at else '',
            'employee_count': emp_count,
            'picture': c.logo_filename
        })

    return jsonify(companies_data)


@company_bp.route('/company/<slug>')
@login_required
@no_cache
def company_profile(slug):
    # Slug/fallback lekérdezések (ahogy eddig)
    company = None
    if slug.isdigit():
        company = Company.query.get(int(slug))
    if not company:
        company = Company.query.filter_by(slug=slug).first()
    if not company:
        import re
        m = re.search(r'-(\d+)$', slug)
        if m:
            company = Company.query.get(int(m.group(1)))
    if not company:
        abort(404)

    # Cég összes hirdetett fuvara
    cargos = (Cargo.query
              .filter(Cargo.company_id == company.company_id)
              .join(CargoLocation, Cargo.cargo_id == CargoLocation.cargo_id)
              .filter(CargoLocation.type == 'pickup')
              .order_by(CargoLocation.start_date.desc())
              .all())

    return render_template('company_profile.html', company=company, cargos=cargos, user=current_user, current_year = datetime.now().year)


@company_bp.route("/company/<company_slug>/<email>")
@login_required
@no_cache
def user_profile(company_slug, email):
    # Cég lekérése a slug alapján
    company = Company.query.filter_by(slug=company_slug).first_or_404()

    # Felhasználó lekérése a cégből az email alapján
    user = User.query.filter_by(email=email, company_id=company.company_id).first_or_404()

    # Nincs szerkesztés
    return render_template("user_profile.html", user=user, current_year=datetime.now().year)


@company_bp.route("/offer_info/<int:offer_id>")
@login_required
@no_cache
def offer_info(offer_id):
    offer = Offer.query.get(offer_id)
    if not offer:
        return jsonify({"error": "Offer not found"}), 404

    cargo = Cargo.query.get(offer.cargo_id)
    if not cargo:
        return jsonify({"error": "Cargo not found"}), 404

    # Only allow the offer creator or the cargo owner to access the chat info
    if current_user.user_id not in (offer.offer_user_id, cargo.user_id):
        return jsonify({"error": "Forbidden"}), 403

    from_user = User.query.get(offer.offer_user_id)
    to_user = User.query.get(cargo.user_id)

    from_profile = (from_user.profile_picture if from_user and from_user.profile_picture else 'default.png')
    from_profile_url = url_for('static', filename='uploads/profile_pictures/' + from_profile)
    to_profile = (to_user.profile_picture if to_user and to_user.profile_picture else 'default.png')
    to_profile_url = url_for('static', filename='uploads/profile_pictures/' + to_profile)

    data = {
        'offer_id': offer.offer_id,
        'cargo_id': cargo.cargo_id,
        'from_user_id': offer.offer_user_id,
        'to_user_id': cargo.user_id,
        'from_user': f"{from_user.first_name} {from_user.last_name}" if from_user else '',
        'from_user_company': from_user.company.name if from_user and from_user.company else '',
        'from_user_profile_picture': from_profile_url,
        'to_user': f"{to_user.first_name} {to_user.last_name}" if to_user else '',
        'to_user_company': to_user.company.name if to_user and to_user.company else '',
        'to_user_profile_picture': to_profile_url,
        'price': offer.price,
        'currency': offer.currency,
        'note': offer.note,
        'origin': cargo.origin_city,
        'destination': cargo.destination_city,
        'pickup_date': offer.pickup_date.strftime('%Y-%m-%d') if offer.pickup_date else '',
        'arrival_date': offer.arrival_date.strftime('%Y-%m-%d') if offer.arrival_date else ''
    }
    return jsonify(data)


@company_bp.route('/block_company/<int:company_id>', methods=['POST'])
@login_required
@no_cache
def block_company(company_id):
    handle_company_block_fast(current_user.company_id, company_id)

    if not getattr(current_user, 'is_company_admin', False):
        return jsonify({'success': False, 'error': 'Nincs jogosultság'}), 403

    # Saját cég tiltásának tiltása
    if current_user.company_id == company_id:
        return jsonify({'success': False, 'error': 'Saját céget nem lehet tiltani'}), 400

    company = Company.query.get(company_id)
    if not company:
        return jsonify({'success': False, 'error': 'Cég nem található'}), 404

    # Ha már tiltva van, ne duplikáljuk
    existing = CompanyBlocklist.query.filter_by(
        blocker_company_id=current_user.company_id,
        blocked_company_id=company_id
    ).first()

    if existing:
        return jsonify({'success': True, 'blocked': True})

    # Új tiltás létrehozása
    block = CompanyBlocklist(
        blocker_company_id=current_user.company_id,
        blocked_company_id=company_id
    )
    db.session.add(block)
    db.session.commit()

    return jsonify({'success': True, 'blocked': True})


@company_bp.route('/blocked_companies')
@login_required
@no_cache
def blocked_companies():
    if not current_user.is_company_admin:
        return jsonify([])  # üres lista, nincs jogosultság

    blocked_list = CompanyBlocklist.query.filter_by(
        blocker_company_id=current_user.company_id
    ).join(Company, Company.company_id == CompanyBlocklist.blocked_company_id).add_columns(
        Company.company_id, Company.name, Company.logo_filename, Company.country,
        Company.street, Company.post_code, Company.tax_number, Company.house_number
    ).all()

    data = [{"company_id": b.company_id, "name": b.name, "logo_filename": b.logo_filename, "country": b.country,
             "street": b.street, "post_code": b.post_code, "tax_number": b.tax_number, "house_number": b.house_number} for b in blocked_list]
    return jsonify(data)


@company_bp.route('/unblock_company/<int:blocked_company_id>', methods=['POST'])
@login_required
@no_cache
def unblock_company(blocked_company_id):
    # csak a saját cég adminja tud engedélyezni
    if not current_user.is_company_admin:
        return jsonify({"success": False, "error": "Nincs jogosultságod!"}), 403

    block = CompanyBlocklist.query.filter_by(
        blocker_company_id=current_user.company_id,
        blocked_company_id=blocked_company_id
    ).first()

    if block:
        db.session.delete(block)
        db.session.commit()
        return jsonify({"success": True, "message": "A tiltás visszavonva."})
    else:
        return jsonify({"success": False, "error": "Tiltás nem található."})
