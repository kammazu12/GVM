#!/usr/bin/env python3
import subprocess
import sys

def run_script(path):
    print(f"\n==== Futtatás: {path} ====")
    result = subprocess.run([sys.executable, path], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("Hiba:", result.stderr)

if __name__ == "__main__":
    run_script("scripts/database_upload.py")
    run_script("scripts/fill_zipcodes.py")
    run_script("scripts/upload_nearby_cities_for_vehicle.py")
    print("\nMinden script lefutott ✅")
