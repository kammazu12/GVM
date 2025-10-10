from datetime import datetime
from models import *
from utils import haversine, parse_time, parse_date

# pontszám súlyok
LOCATION_POINTS = {
    "exact_match": 50,
    "on_route": 25,
}

TIME_POINTS = {
    "in_time": 40,
    "late_penalty": 10,   # naponta ennyit vonunk le
}

CAPACITY_POINTS = {
    "equal_or_10_less": 25,
    "much_smaller": 15,
    "slightly_bigger": 0,
    "too_big": -30,
}


def get_vehicle_route_cities(vehicle_id):
    """Lekéri a jármű útvonalán szereplő településeket stop_number szerint"""
    routes = VehicleRoute.query.filter_by(vehicle_id=vehicle_id).order_by(VehicleRoute.stop_number).all()
    return [r.city for r in routes]


def city_in_route_or_nearby(vehicle, cargo_city, ref_type):
    """
    Ellenőrzi, hogy a cargo_city benne van-e a jármű útvonalán vagy NearbyCity-ben
    a vehicle origin_diff / destination_diff figyelembevételével.
    ref_type: 'origin' vagy 'destination'
    """
    full_route = [vehicle.origin_city] + get_vehicle_route_cities(vehicle.vehicle_id) + [vehicle.destination_city]

    # Pontos match
    if cargo_city in full_route:
        return True, "exact"

    # NearbyCity match, csak ha van diff
    diff = getattr(vehicle, f"{ref_type}_diff")
    if not diff or diff == 0:
        return False, None  # jármű nem hajlandó eltérni, skip

    # Lekérjük a NearbyCity-ket a stopokhoz
    for stop in full_route:
        nearby_cities = NearbyCity.query.filter_by(
            reference_country=getattr(vehicle, f"{ref_type}_country"),
            reference_postcode=getattr(vehicle, f"{ref_type}_postcode"),
            reference_city=stop
        ).all()

        for nc in nearby_cities:
            # Hány km-re van a stop-tól?
            if nc.city_name == cargo_city and nc.radius_km <= diff:
                return True, "nearby"

    return False, None


def find_matches_for_cargo(cargo: Cargo):
    """
    Előszűrés helyszín alapján:
    - pickup és dropoff városnak szerepelnie kell a jármű útvonalában vagy NearbyCity-ben
    - sorrend: pickup -> dropoff
    Utána idő és kapacitás pontozás.
    """
    matches = []

    vehicles = Vehicle.query.all()

    for vehicle in vehicles:
        cargo_origin = next((loc for loc in cargo.locations if loc.type == "pickup"), None)
        cargo_dest = next((loc for loc in cargo.locations if loc.type == "dropoff"), None)

        if not cargo_origin or not cargo_dest:
            continue  # nincs pickup/dropoff -> nem értelmezhető

        # --- Előszűrés: pickup és dropoff benne van a jármű útvonalában vagy NearbyCity-ben ---
        ok_origin, origin_type = city_in_route_or_nearby(vehicle, cargo_origin.city, "origin")
        ok_dest, dest_type = city_in_route_or_nearby(vehicle, cargo_dest.city, "destination")

        if not (ok_origin and ok_dest):
            continue  # jármű nem tudja vállalni a cargo-t

        # sorrendellenőrzés az útvonalon (exact vagy nearby)
        full_route = [vehicle.origin_city] + get_vehicle_route_cities(vehicle.vehicle_id) + [vehicle.destination_city]
        try:
            if full_route.index(cargo_origin.city) >= full_route.index(cargo_dest.city):
                continue
        except ValueError:
            # ha nearby volt, előfordulhat, hogy nincs pontosan benne az útvonalban
            pass

        # --- PONTOZÁS ---
        score = 0

        # Város pontozás
        if origin_type == "exact":
            score += LOCATION_POINTS["exact_match"]
        elif origin_type == "nearby":
            score += LOCATION_POINTS["on_route"]

        if dest_type == "exact":
            score += LOCATION_POINTS["exact_match"]
        elif dest_type == "nearby":
            score += LOCATION_POINTS["on_route"]

        # Időpontozás
        time_score = 0
        if vehicle.available_from and cargo_origin.start_date:
            if vehicle.available_until is None:
                delta_days = max(0, (vehicle.available_from - cargo_origin.start_date).days)
                time_score += max(0, 40 - delta_days * 10)
            else:
                if vehicle.available_from <= cargo_origin.start_date <= vehicle.available_until:
                    time_score += 40
                else:
                    if cargo_origin.start_date < vehicle.available_from:
                        delta = (vehicle.available_from - cargo_origin.start_date).days
                    else:
                        delta = (cargo_origin.start_date - vehicle.available_until).days
                    time_score += max(0, 40 - delta * 10)
        score += time_score

        # Kapacitás pontozás
        capacity_score = 0
        if vehicle.capacity_t and cargo.weight:
            ratio = cargo.weight / vehicle.capacity_t
            if 0.9 <= ratio <= 1.0:
                capacity_score += 25
            elif ratio < 0.9:
                capacity_score += 15
            elif 1.0 < ratio <= 1.1:
                capacity_score += 0
            else:
                capacity_score += -30
        score += capacity_score

        # --- Találat hozzáadása ---
        matches.append({
            "vehicle_id": vehicle.vehicle_id,
            "origin_country": vehicle.origin_country,
            "origin_postcode": vehicle.origin_postcode,
            "origin_city": vehicle.origin_city,
            "available_from": vehicle.available_from,
            "destination_country": vehicle.destination_country,
            "destination_postcode": vehicle.destination_postcode,
            "destination_city": vehicle.destination_city,
            "available_until": vehicle.available_until,
            "vehicle_type": vehicle.vehicle_type,
            "structure": vehicle.structure,
            "equipment": vehicle.equipment,
            "cargo_securement": vehicle.cargo_securement,
            "description": vehicle.description,
            "capacity_t": vehicle.capacity_t,
            "volume_m3": vehicle.volume_m3,
            "price": vehicle.price,
            "currency": vehicle.currency,
            "company": vehicle.company.name if vehicle.company else None,
            "score": score
        })

    # --- Rendezés pontszám szerint ---
    matches.sort(key=lambda m: m["score"], reverse=True)
    return matches
