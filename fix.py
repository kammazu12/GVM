import os
import geopandas as gpd

# --- Beállítások ---
INPUT_SHP = "ne_10m_admin_0_countries.shp"   # ide tedd a shapefile fő fájl nevét
OUTPUT_DIR = os.path.join("static", "geojson", "countries")

# --- Könyvtár létrehozása ---
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Shapefile betöltése ---
print("[INFO] Shapefile betöltése...")
gdf = gpd.read_file(INPUT_SHP)

# Ellenőrizzük, hogy van-e ISO_A2 kód (országkód)
if "ISO_A2" not in gdf.columns:
    raise ValueError("A shapefile nem tartalmaz 'ISO_A2' oszlopot! Ellenőrizd a fájlt.")

# --- Országokra bontás és mentés ---
print("[INFO] Országonkénti GeoJSON fájlok mentése...")
for _, row in gdf.iterrows():
    iso = row["ISO_A2"]

    if not iso or iso == "-99":  # érvénytelen országkód
        continue

    country_gdf = gdf[gdf["ISO_A2"] == iso]
    output_path = os.path.join(OUTPUT_DIR, f"{iso}.geojson")

    country_gdf.to_file(output_path, driver="GeoJSON")
    print(f"[OK] {iso}.geojson mentve.")

print("[DONE] Minden ország feldolgozva!")
