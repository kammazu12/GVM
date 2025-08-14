from fix import db  # importáld a Flask app db példányát

with db.engine.connect() as conn:
    conn.execute(
        "ALTER TABLE user ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
    )
