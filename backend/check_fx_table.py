import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

db_url = os.getenv('DATABASE_PUBLIC_URL')
conn = psycopg2.connect(db_url)
cursor = conn.cursor()

# Check FX rate table columns
cursor.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'portfolio_fxrate'
    ORDER BY ordinal_position;
""")
print("portfolio_fxrate columns:")
for col in cursor.fetchall():
    print(f"  {col[0]}: {col[1]}")

cursor.close()
conn.close()
