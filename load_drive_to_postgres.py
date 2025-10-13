import os
import io
import pandas as pd
import psycopg2
import gdown

# ============================================================
# 🔧 KONFIGURÁCIÓ
# ============================================================

FILE_IDS = {
    "cities": "12hYD2xgfPR2lB4X7wwUmp4uggUJEWK0q",
    "alt_names": "1203x6RunopUNJL9q5ZIeI-qrtrl9qg5d",
    "all_countries": "1ndBCWXe17JBKRvUkTcgl4lKiSx7K3kkz"
}

DB_URL = "postgresql://freight_166g_user:oGP8kBqOmS6KsefJedLSIkbyA0KSu15n@dpg-d3m9usp5pdvs73b2ufe0-a/freight_166g"

BATCH_SIZE = 5000
PREVIEW = 5


# ============================================================
# 🧩 SEGÉDFÜGGVÉNYEK
# ============================================================

def download_file_from_drive(file_id, file_name):
    """Letölti a Google Drive fájlt a /tmp mappába, és megnyitja olvasásra."""
    print(f"\n⬇ Letöltés a Drive-ról: {file_name}")
    url = f"https://drive.google.com/uc?id={file_id}"
    out_path = f"/tmp/{file_name}"

    gdown.download(url, out_path, quiet=False)

    if not os.path.exists(out_path):
        raise FileNotFoundError(f"Hiba: a fájl nem található a letöltés után: {out_path}")

    print(f"✔ Letöltve: {out_path}")
    return open(out_path, 'rb')


def copy_df_to_postgres(conn, df, table_name, preview=PREVIEW):
    """Batch-enként feltölti a DataFrame tartalmát a megadott Postgres táblába."""
    print(f"\n➡ Feltöltés indul: {table_name} ({len(df)} rekord)")

    cur = conn.cursor()
    batch_count = 0
    inserted_total = 0

    for start in range(0, len(df), BATCH_SIZE):
        end = start + BATCH_SIZE
        batch = df.iloc[start:end]
        batch_count += 1

        print(f"  🟡 Batch {batch_count}: {len(batch)} sor beszúrása...")

        output = io.StringIO()
        batch.to_csv(output, sep='\t', header=False, index=False)
        output.seek(0)

        cur.copy_from(output, table_name, null="", sep='\t')
        conn.commit()
        inserted_total += len(batch)

    print(f"✅ {inserted_total} rekord feltöltve a(z) {table_name} táblába.")

    if len(df) > 0:
        print(f"📋 Első {preview} rekord mintaként:")
        print(df.head(preview).to_string(index=False))

    cur.close()


# ============================================================
# 🚀 FŐ FÜGGVÉNY
# ============================================================

def main():
    print("📡 Kapcsolódás az adatbázishoz...")
    conn = psycopg2.connect(DB_URL)
    print("✔ Kapcsolódva.\n")

    # --------------------------------------------------------
    # 1️⃣ Városok (cities1000.txt)
    # --------------------------------------------------------
    cities_file = download_file_from_drive(FILE_IDS["cities"], "cities1000.txt")
    cities_df = pd.read_csv(
        io.TextIOWrapper(cities_file, encoding='utf-8'),
        sep='\t', header=None,
        usecols=[0, 1, 4, 5, 8],
        names=['id', 'city_name', 'latitude', 'longitude', 'country_code']
    )
    cities_df['zipcode'] = 0  # ideiglenes default

    # 💡 Itt szűrjük ki az érvénytelen országkódokat:
    print("\n🔎 Országkódok ellenőrzése az adatbázisban...")
    with conn.cursor() as cur:
        cur.execute("SELECT code FROM countries")
        valid_codes = {row[0] for row in cur.fetchall()}

    before_count = len(cities_df)
    cities_df = cities_df[cities_df['country_code'].isin(valid_codes)]
    after_count = len(cities_df)

    print(f"✅ {before_count - after_count} város kihagyva (nem EU-s ország).")
    print(f"📍 Maradt {after_count} város, amelyek érvényes országkódhoz tartoznak.")

    copy_df_to_postgres(conn, cities_df, 'city')

    # --------------------------------------------------------
    # 2️⃣ Alternate Names
    # --------------------------------------------------------
    alt_file = download_file_from_drive(FILE_IDS["alt_names"], "alternateNamesV2.txt")
    alt_df = pd.read_csv(
        io.TextIOWrapper(alt_file, encoding='utf-8'),
        sep='\t', header=None,
        usecols=[1, 3],
        names=['city_id', 'alternames']
    )
    copy_df_to_postgres(conn, alt_df, 'altername')

    # --------------------------------------------------------
    # 3️⃣ Zipkódok (allCountries.txt)
    # --------------------------------------------------------
    zip_file = download_file_from_drive(FILE_IDS["all_countries"], "allCountries.txt")
    zip_df = pd.read_csv(
        io.TextIOWrapper(zip_file, encoding='utf-8'),
        sep='\t', header=None,
        usecols=[0, 1, 2],
        names=['country_code', 'zipcode', 'place_name']
    )
    copy_df_to_postgres(conn, zip_df, 'cityzipcode')

    conn.close()
    print("\n🎉 Minden adat sikeresen feltöltve az adatbázisba!")


# ============================================================
# 🏁 INDÍTÁS
# ============================================================

if __name__ == "__main__":
    main()
