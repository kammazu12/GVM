from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

# --- Adatbázis URL-ek ---
LOCAL_DB_URL = "sqlite:///C:/Users/Alex/GVM_apps/instance/app.db"
SERVER_DB_URL = "postgresql://alexgvmszallitmanyozashu:OmIUDWLt66MJ3v9YeaInU9s6Z6Dqo4Ln@dpg-d3mg8gu3jp1c73fun68g-a.frankfurt-postgres.render.com/freight_v76h"

# --- Engine-ek ---
local_engine = create_engine(LOCAL_DB_URL)
server_engine = create_engine(SERVER_DB_URL)

# --- Sessionök ---
LocalSession = sessionmaker(bind=local_engine)
ServerSession = sessionmaker(bind=server_engine)

local_session = LocalSession()
server_session = ServerSession()

# --- MetaData lekérése a lokális DB-ből ---
local_meta = MetaData()
local_meta.reflect(bind=local_engine)

# --- Betöltési sorrend (foreign key függőségek miatt) ---
table_order = ['countries', 'city', 'alter_names']
other_tables = [t for t in local_meta.tables.keys() if t not in table_order]
table_order.extend(other_tables)

# --- Adatok másolása ---
for table_name in table_order:
    print(f"Másolás: {table_name}")
    table = local_meta.tables[table_name]

    rows = local_session.execute(table.select()).fetchall()
    if not rows:
        continue

    data_to_insert = [dict(row._mapping) for row in rows]

    server_table = Table(table_name, MetaData(), autoload_with=server_engine)

    try:
        # --- EU országok beszúrása, 0.5 másodperces várakozással ---
        if table_name == 'countries':
            for country in data_to_insert:
                if country.get('region') != 'EU':
                    continue
                # Ne küldjük az id mezőt
                if 'id' in country:
                    del country['id']

                # print(f"Beszúrásra kerülő ország: {country.get('name')} ({country.get('code')})")
                try:
                    server_session.execute(server_table.insert().values(**country))
                    server_session.commit()
                    print("Beszúrva.")
                except IntegrityError as e:
                    server_session.rollback()
                    print(f"Hiba az ország beszúrásánál: {e}")
                except Exception as e:
                    server_session.rollback()
                    print(f"Ismeretlen hiba az ország beszúrásánál: {e}")
        else:
            # többi tábla normál beszúrása
            server_session.execute(server_table.insert(), data_to_insert)
            server_session.commit()
    except IntegrityError as e:
        server_session.rollback()
        print(f"Hiba a '{table_name}' táblánál: {e}")
    except Exception as e:
        server_session.rollback()
        print(f"Ismeretlen hiba a '{table_name}' táblánál: {e}")

print("Átviteli folyamat kész!")
