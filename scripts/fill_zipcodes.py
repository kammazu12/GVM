import csv
from extensions import db
from models import City, CityZipcode
from main import app

ALLCOUNTRIES_FILE = "./allCountries.txt"  # GeoNames postal code dump

BATCH_SIZE = 500  # commitolás batch-ekben

def update_zipcodes_from_file():
    with app.app_context():
        # Betöltjük az összes várost dictionary-be a gyors kereséshez
        cities = { (c.city_name.lower(), c.country_code): c for c in City.query.all() }
        print(f"{len(cities)} város az adatbázisban. Frissítés indul...")

        # Betöltjük az összes CityZipcode meglévőt is egy set-be
        existing_zipcodes = set(
            (cz.city_id, cz.zipcode) for cz in CityZipcode.query.all()
        )

        updated_cities = 0
        new_zipcodes = 0
        batch_counter = 0

        with open(ALLCOUNTRIES_FILE, encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            for idx, row in enumerate(reader, start=1):
                if len(row) < 3:
                    continue
                country_code = row[0]
                postal_code = row[1]
                place_name = row[2]

                key = (place_name.lower(), country_code)
                city = cities.get(key)
                if city:
                    # City táblába az első postal code
                    if not city.zipcode or city.zipcode == "0":
                        city.zipcode = postal_code
                        updated_cities += 1

                    # CityZipcode táblába minden postal code
                    if (city.id, postal_code) not in existing_zipcodes:
                        db.session.add(CityZipcode(city_id=city.id, zipcode=postal_code))
                        existing_zipcodes.add((city.id, postal_code))
                        new_zipcodes += 1

                    batch_counter += 1
                    if batch_counter >= BATCH_SIZE:
                        db.session.commit()
                        print(f"{idx} sor feldolgozva... ({updated_cities} város frissítve, {new_zipcodes} új ZIP)")
                        batch_counter = 0

            # végső commit a maradékra
            db.session.commit()
            print(f"Kész! Összesen {updated_cities} város frissítve, {new_zipcodes} új ZIP kód került a CityZipcode táblába.")


if __name__ == "__main__":
    update_zipcodes_from_file()
