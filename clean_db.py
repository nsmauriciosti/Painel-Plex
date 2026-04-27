import sqlite3

conn = sqlite3.connect('config/app_data.db')
cur = conn.cursor()
tables = cur.execute('SELECT name FROM sqlite_master WHERE type="table" AND name LIKE "_alembic_tmp_%"').fetchall()

for table in tables:
    print(f"Dropping {table[0]}")
    cur.execute(f"DROP TABLE IF EXISTS {table[0]}")

# Also drop tickets if it's there
cur.execute("DROP TABLE IF EXISTS tickets")
conn.commit()
print("Cleaned up DB.")
