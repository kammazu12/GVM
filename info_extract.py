import google.genai as genai

# Gemini kliens inicializálás
client = genai.Client(api_key="AIzaSyByu3AatMxSafp8eKCBeON4DYTjm8ZfiYw")

# E-mail szöveg
email_text = '''Preduzeće: DELIVERY MASTER DOO
Sagovornik: Gospodin Srdjan Stojanov
Telefon: +381 64 0242445

Ponuđivač: 207359, GVM Europe Kft., Gospodin Viktor Toth

Teret ponuditi:
Dana: 12.08.2025
Mesto: DE, 70178 Stuttgart

Istovariti: 13.08.2025
Mesto: NL, 5018 Tilburg

Rastojanje u km: 531

Razmena utovarne opreme: Ne
Dužina: 0.8 m
Težina/t: 0.25 t
Mesta utovara: 1
Mesta istovara: 1
Dodatna informacija: Zbirni prevoz
Vrsta robe: ---
Cena prevoza:
Rok plaćanja:

Potreban tip vozila: Vozilo do 3,5 t
Nadgradnja: Sandučar, Cerada
Osobine:
TIMOCOM Moguće je praćenje pošiljki: Ne

Napomene:
'''

# JSON séma a kinyerendő adatokhoz
schema = {
    "type": "object",
    "properties": {
        # Loading / unloading
        "loading_places_amount": {"type": "number"},
        "unloading_places_amount": {"type": "number"},
        "loading_location": {"type": "string"},
        "loading_date_from": {"type": "string"},
        "loading_date_to": {"type": "string"},
        "loading_time_from": {"type": "string"},
        "loading_time_to": {"type": "string"},
        "unloading_location": {"type": "string"},
        "unloading_date_from": {"type": "string"},
        "unloading_date_to": {"type": "string"},
        "unloading_time_from": {"type": "string"},
        "unloading_time_to": {"type": "string"},
        # Freight
        "shipment_size": {"type": "string"},
        "shipment_weight": {"type": "string"},
        "palette_exchange": {"type": "boolean"},
        # Vehicle
        "vehicle_type": {"type": "string"},
        "vehicle_body": {"type": "string"},
        "vehicle_certificates": {"type": "string"},

        # Hide
        # "hidden" : {"type": "boolean"} - ha lesz adatb
    },
    "required": ["loading_date_from", "loading_date_to", "loading_location",
                 "unloading_date_from", "unloading_date_to", "unloading_location",
                 "shipment_size", "shipment_weight", "vehicle_type", "vehicle_body"]
}

# Kérés a Gemini modellhez
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=f"Extract info a json from this email. Dates can be intervals and has to be YYYY-MM-DD. "
             f"If no loading or unload time interval added, both should be left empty. "
             f"Vehicle type can be truck(+ tons it can carry), rigid truck, articulated truck, van etc. "
             f"Default should be rigid truck."
             f"Multiple loading or unloading places can occur. "
             f"If that is the case, make a 2nd, 3rd etc. (un)loading place, date etc. as well. "
             f"Freight size means length. "
             f"Vehicle body can be curtain, box, mega, jumbo, refrigerator etc. Defualt should be curtain. "
             f"Everything must be in English. The text:\n\n{email_text}",
    config={
        "response_mime_type": "application/json",
        "response_schema": schema
    }
)

# Eredmény feldolgozása
data = response.parsed  # Python dict
print(data)
