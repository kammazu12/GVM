# seed_random_data.py
from main import app, db, User, Company
from datetime import date
from werkzeug.security import generate_password_hash
import random


with app.app_context():
    # Cégek listája és random adatok
    company_names = [
        "Alpha Logistics", "Beta Transport", "Gamma Freight", "Delta Movers",
        "Epsilon Cargo", "Zeta Shipping", "Eta Forwarding", "Theta Delivery",
        "Iota Haulage", "Kappa Transport"
    ]

    countries = ["Hungary", "Germany", "France", "Italy", "Poland"]
    streets = ["Fő utca", "Kis utca", "Nagykörút", "Rákóczi út", "Petőfi utca"]

    companies = []

    # Cégek létrehozása
    for name in company_names:
        company = Company(
            name=name,
            subscription_type=random.choice(["free", "basic", "pro"]),
            country=random.choice(countries),
            post_code=str(random.randint(1000, 9999)),
            street=random.choice(streets),
            house_number=str(random.randint(1, 50)),
            tax_number=f"{random.randint(10000000,99999999)}-{random.randint(1,9)}-{random.randint(10,99)}",
            created_at=date.today()
        )
        db.session.add(company)
        companies.append(company)

    db.session.commit()

    # Felhasználók létrehozása cégenként
    first_names = ["Alice", "Bob", "Charlie", "David", "Eva", "Frank", "Grace", "Hannah"]
    last_names = ["Smith", "Johnson", "Brown", "Taylor", "Miller", "Davis", "Wilson", "Moore"]

    for company in companies:
        num_users = random.randint(3, 5)
        admin_index = random.randint(0, num_users-1)  # admin kiválasztása
        for i in range(num_users):
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            email = f"{first_name.lower()}.{last_name.lower()}@{company.name.replace(' ', '').lower()}.com"
            is_admin = (i == admin_index)
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone_number=f"+36{random.randint(200000000, 999999999)}",
                hashed_password=generate_password_hash("Jelszo12"),
                role="freight_forwarder",
                is_company_admin=is_admin,
                common_user=not is_admin,
                company=company,
                created_at=date.today()
            )
            db.session.add(user)

    db.session.commit()
    print("Random companies and users have been added to the database!")
