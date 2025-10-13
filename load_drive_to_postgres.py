import os
import io
import pandas as pd
import psycopg2
import gdown

# ----------------------
# KONFIG
# ----------------------
# Google Drive file IDs
FILE_IDS = {
    "cities": "YOUR_CITIES1000_FILE_ID",
    "alt_names": "YOUR_ALTERNATENAMES_FILE_ID",
    "all_countries": "YOUR_ALLCOUNTRIES_FILE_ID",
}

# PostgreSQL connection
DB_URL = "postgresql://freight_166g_user:oGP8kBqOmS6KsefJedLSIkbyA0KSu15n@dpg-d3m9usp5pdvs73b2ufe0-a/freight_166g"

# Batch size
BATCH_SIZE = 5000
PREVIEW = 100  # első N rekord részletes logolása

# ----------------------
# SEGÉDFÜGGVÉNYEK
# ----------------------
def download_file_from_drive(file_id, file_name):
    """Drive-ról letöltés memória-ba"""
    print(f"Letöltés: {file_name} ...")
    url = f"https://drive.google.com/uc?id={file_id}"
    out = io.BytesIO()
    gdown.download(url, output=out, quiet=False, fuzzy=True)
    out.seek(0)
    return out

def copy_df_to_postgres(conn, df, table_name, preview=PREVIEW):
    """Batch-esen másoljuk a DataFrame-et PostgreSQL-be részletes loggal"""
    cur = conn.cursor()
    total_rows = len(df)
    batch_count = 0

    for start in range(0, total_rows, BATCH_SIZE):
        batch = df.iloc[start:start+BATCH_SIZE]

        # Preview log az első N rekordhoz
        if start < preview:
            for idx, row in batch.head(preview-start).iterrows():
                print(f"[{table_name}] beszúrt rekord: {row.to_dict()}")

        # CSV-ba bufferelve COPY
        buffer = io.StringIO()
        batch.to_csv(buffer, sep='\t', header=False, index=False, na_rep='', quoting=3)
        buffer.seek(0)

        cur.copy_from(buffer, table_name, sep='\t', null='')
        conn.commit()
        batch_count += 1
        print(f"[{table_name}] {min(start+BATCH_SIZE, total_rows)} / {total_rows} rekord feldolgozva, commit #{batch_count}")

    print(f"[{table_name}] Összesen {total_rows} rekord commit-olva ✅")
    cur.close()

# ----------------------
# FŐ FÜGGVÉNY
# ----------------------
def main():
    conn = psycopg2.connect(DB_URL)

    # 1️⃣ Cities
    cities_file = download_file_from_drive(FILE_IDS["cities"], "cities1000.txt")
    cities_df = pd.read_csv(io.TextIOWrapper(cities_file, encoding='utf-8'), sep='\t', header=None,
                            usecols=[0,1,4,5,8], names=['id','city_name','latitude','longitude','country_code'])
    cities_df['zipcode'] = 0  # default
    copy_df_to_postgres(conn, cities_df, 'city')

    # 2️⃣ Alternate Names
    alt_file = download_file_from_drive(FILE_IDS["alt_names"], "alternateNamesV2.txt")
    alt_df = pd.read_csv(io.TextIOWrapper(alt_file, encoding='utf-8'), sep='\t', header=None,
                         usecols=[1,3], names=['city_id','alternames'])
    copy_df_to_postgres(conn, alt_df, 'altername')

    # 3️⃣ All Countries (ZIP)
    zip_file = download_file_from_drive(FILE_IDS["all_countries"], "allCountries.txt")
    zip_df = pd.read_csv(io.TextIOWrapper(zip_file, encoding='utf-8'), sep='\t', header=None,
                         usecols=[0,1,2], names=['country_code','zipcode','place_name'])
    copy_df_to_postgres(conn, zip_df, 'cityzipcode')

    conn.close()
    print("Minden adat feltöltve ✅")

if __name__ == "__main__":
    main()
