
import os
from dotenv import load_dotenv
import psycopg2
from urllib.parse import urlparse

load_dotenv()

def test_database_connection():
    """Test database connection using DATABASE_PUBLIC_URL"""

    # Try DATABASE_PUBLIC_URL first
    db_url = os.getenv('DATABASE_PUBLIC_URL')

    if not db_url:
        print("❌ DATABASE_PUBLIC_URL not found in .env file")
        print("\nTrying individual DB environment variables instead...")

        # Fallback to individual variables
        db_user = os.getenv('DB_USER', 'postgres')
        db_password = os.getenv('DB_PASSWORD', '')
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'postgres')

        print(f"\nDB_USER: {db_user}")
        print(f"DB_HOST: {db_host}")
        print(f"DB_PORT: {db_port}")
        print(f"DB_NAME: {db_name}")
        print(f"DB_PASSWORD: {'*' * len(db_password) if db_password else '(empty)'}")

        try:
            conn = psycopg2.connect(
                user=db_user,
                password=db_password,
                host=db_host,
                port=db_port,
                database=db_name
            )
            print("\n✅ Successfully connected using individual environment variables!")
            conn.close()
        except Exception as e:
            print(f"\n❌ Connection failed: {e}")
        return

    print(f"Found DATABASE_PUBLIC_URL: {db_url[:20]}...{db_url[-20:]}")

    # Parse the URL
    try:
        parsed = urlparse(db_url)
        print(f"\nParsed connection details:")
        print(f"  Scheme: {parsed.scheme}")
        print(f"  Host: {parsed.hostname}")
        print(f"  Port: {parsed.port}")
        print(f"  Database: {parsed.path[1:]}")  # Remove leading slash
        print(f"  Username: {parsed.username}")
        print(f"  Password: {'*' * len(parsed.password) if parsed.password else '(empty)'}")
    except Exception as e:
        print(f"❌ Failed to parse URL: {e}")
        return

    # Test connection
    print("\nAttempting to connect...")
    try:
        conn = psycopg2.connect(db_url)
        print("✅ Successfully connected to the database!")

        # Test a simple query
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()
        print(f"\n✅ PostgreSQL version: {db_version[0]}")

        # List tables
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
            LIMIT 10;
        """)
        tables = cursor.fetchall()
        print(f"\n✅ Found {len(tables)} tables (showing first 10):")
        for table in tables:
            print(f"  - {table[0]}")

        cursor.close()
        conn.close()
        print("\n✅ Connection test successful!")

    except psycopg2.OperationalError as e:
        print(f"\n❌ Operational Error: {e}")
        print("\nPossible issues:")
        print("  - Wrong hostname or port")
        print("  - Database server not running")
        print("  - Network/firewall issues")
        print("  - SSL/TLS requirements not met")
    except psycopg2.ProgrammingError as e:
        print(f"\n❌ Programming Error: {e}")
        print("\nPossible issues:")
        print("  - Wrong database name")
    except psycopg2.Error as e:
        print(f"\n❌ Database Error: {e}")
        print("\nPossible issues:")
        print("  - Wrong username or password")
        print("  - Insufficient permissions")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    test_database_connection()
