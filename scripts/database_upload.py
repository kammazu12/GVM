import csv
from extensions import db
from models import City, AlterName
from main import app

BATCH_SIZE = 5000  # egyszerre hány rekordot commit-olunk

with app.app_context():
    # Törlés
    db.session.query(City).delete()
    db.session.query(AlterName).delete()
    db.session.commit()

    # ---------------------
    # CITIES
    # ---------------------
    cities_batch = []
    with open("cities1000.txt", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for i, row in enumerate(reader, start=1):
            geonameid = int(row[0])
            name = row[1]
            lat = float(row[4])
            lon = float(row[5])
            country_code = row[8]

            city = City(
                id=geonameid,
                city_name=name,
                latitude=lat,
                longitude=lon,
                zipcode=0,
                country_code=country_code
            )
            cities_batch.append(city)

            # batch commit
            if i % BATCH_SIZE == 0:
                db.session.bulk_save_objects(cities_batch)
                db.session.commit()
                cities_batch = []
                print(f"{i} city records committed...")

        # maradék mentése
        if cities_batch:
            db.session.bulk_save_objects(cities_batch)
            db.session.commit()
            print(f"All {i} city records committed ✅")

    # ---------------------
    # ALTERNATE NAMES
    # ---------------------
    alt_batch = []
    with open("alternateNamesV2.txt", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for j, row in enumerate(reader, start=1):
            geonameid = int(row[1])
            altname = row[3]

            # csak akkor mentsük, ha van city
            if db.session.get(City, geonameid):
                alt = AlterName(city_id=geonameid, alternames=altname)
                alt_batch.append(alt)

                if j % BATCH_SIZE == 0:
                    db.session.bulk_save_objects(alt_batch)
                    db.session.commit()
                    alt_batch = []
                    print(f"{j} alternate names committed...")

        # maradék mentése
        if alt_batch:
            db.session.bulk_save_objects(alt_batch)
            db.session.commit()
            print(f"All {j} alternate names committed ✅")

    print("GeoNames data imported 🚀")
