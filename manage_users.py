from main import db, User, app  # app importálva, hogy legyen context

def list_users():
    with app.app_context():  # Flask app context
        users = User.query.all()
        if not users:
            print("Nincsenek felhasználók az adatbázisban.")
            return
        print("---- Users in Database ----")
        for u in users:
            print(f"ID: {u.user_id}, Email: {u.email}, Company ID: {u.company_id}")

def delete_user_by_email(email):
    with app.app_context():  # Flask app context
        user = User.query.filter_by(email=email).first()
        if user:
            db.session.delete(user)
            db.session.commit()
            print(f"Törölve: {email}")
        else:
            print("Nem található ilyen felhasználó.")

def main_menu():
    while True:
        print("\n1. Listázás")
        print("2. Törlés email alapján")
        print("3. Kilépés")
        choice = input("Választás: ")

        if choice == "1":
            list_users()
        elif choice == "2":
            email = input("Add meg a törlendő felhasználó emailjét: ")
            delete_user_by_email(email)
        elif choice == "3":
            print("Kilépés...")
            break
        else:
            print("Érvénytelen választás.")

if __name__ == "__main__":
    main_menu()
