from extensions import db
from models import Vehicle, NearbyCity, City
from utils import haversine
import math

def fill_nearby_cities():
    vehicles = Vehicle.query.all()
    print(f"Feltöltés kezdete: {len(vehicles)} járműhöz")

    for v in vehicles:
        for ref_type in ['origin', 'destination']:
            ref_country = getattr(v, f"{ref_type}_country")
            ref_postcode = getattr(v, f"{ref_type}_postcode")
            ref_city = getattr(v, f"{ref_type}_city")
            radius_km = getattr(v, f"{ref_type}_diff", 0)
            ref_lat = getattr(v, f"{ref_type}_lat", None)
            ref_lon = getattr(v, f"{ref_type}_lon", None)

            # Ha nincs radius, skip
            if not radius_km or radius_km <= 0:
                continue

            # Ha nincs lat/lon, próbáljuk a City táblából
            if not ref_lat or not ref_lon:
                city_obj = City.query.filter_by(
                    country_code=ref_country,
                    city_name=ref_city,
                    zipcode=ref_postcode
                ).first()
                if city_obj:
                    ref_lat = city_obj.latitude
                    ref_lon = city_obj.longitude
                else:
                    print(f"[SKIP] Vehicle {v.vehicle_id} {ref_type}: nincs koordináta és City sincs")
                    continue

            # Bounding box (approximate, gyorsabb mint minden várost végig ellenőrizni)
            lat_min = ref_lat - radius_km / 110
            lat_max = ref_lat + radius_km / 110
            lon_min = ref_lon - radius_km / (111 * math.cos(math.radians(ref_lat)))
            lon_max = ref_lon + radius_km / (111 * math.cos(math.radians(ref_lat)))

            cities = City.query.filter(
                City.country_code == ref_country,
                City.latitude.between(lat_min, lat_max),
                City.longitude.between(lon_min, lon_max)
            ).all()

            for c in cities:
                dist = haversine(ref_lat, ref_lon, c.latitude, c.longitude)
                if dist <= radius_km:
                    exists = NearbyCity.query.filter_by(
                        reference_country=ref_country,
                        reference_postcode=ref_postcode,
                        reference_city=ref_city,
                        city_name=c.city_name,
                        radius_km=radius_km
                    ).first()
                    if not exists:
                        nearby = NearbyCity(
                            country_code=c.country_code,
                            zipcode=c.zipcode,
                            city_name=c.city_name,
                            lat=c.latitude,
                            lon=c.longitude,
                            reference_country=ref_country,
                            reference_postcode=ref_postcode,
                            reference_city=ref_city,
                            radius_km=radius_km
                        )
                        db.session.add(nearby)
            print(f"[OK] Vehicle {v.vehicle_id} {ref_type}: {len(cities)} város feldolgozva")

    db.session.commit()
    print("NearbyCity feltöltés kész.")


if __name__ == "__main__":
    from main import app
    with app.app_context():
        fill_nearby_cities()
