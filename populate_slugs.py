# populate_slugs.py
from main import app, db, Company
import unicodedata, re
from sqlalchemy import inspect, text

def slugify(value: str) -> str:
    if not value:
        return ''
    value = str(value)
    value = unicodedata.normalize('NFKD', value)
    value = ''.join([c for c in value if not unicodedata.combining(c)])
    value = value.lower()
    value = re.sub(r'[^a-z0-9]+', '-', value)
    value = value.strip('-')
    return value or 'company'

def generate_unique_slug(name: str):
    base = slugify(name)
    candidate = base
    i = 2
    # add loop to guarantee uniqueness
    while Company.query.filter_by(slug=candidate).first() is not None:
        candidate = f"{base}-{i}"
        i += 1
    return candidate

with app.app_context():
    inspector = inspect(db.engine)
    cols = [c['name'] for c in inspector.get_columns('company')]
    if 'slug' not in cols:
        try:
            print("Adding 'slug' column to company table...")
            # SQLAlchemy 2.x safe execute using connection.begin()
            with db.engine.begin() as conn:
                conn.execute(text("ALTER TABLE company ADD COLUMN slug VARCHAR;"))
            print("Added 'slug' column.")
        except Exception as e:
            print("Failed to add slug column:", e)
            raise

    companies = Company.query.all()
    updated = 0
    for c in companies:
        # if slug missing or empty, generate one
        current = getattr(c, 'slug', None)
        if not current:
            new_slug = generate_unique_slug(c.name or f"company-{c.company_id}")
            c.slug = new_slug
            db.session.add(c)
            updated += 1
            print(f"Set slug for {c.name!r} -> {new_slug}")
    if updated:
        db.session.commit()
        print(f"Committed {updated} slug updates.")
    else:
        print("No slugs needed updating (all present).")

    # Attempt to create unique index if possible
    try:
        print("Creating unique index on company.slug (IF NOT EXISTS)...")
        with db.engine.begin() as conn:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_company_slug ON company(slug);"))
        print("Unique index created (or already existed).")
    except Exception as e:
        print("Could not create unique index (duplicates?):", e)

    print("Done.")
