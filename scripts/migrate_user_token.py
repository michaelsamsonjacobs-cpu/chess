
import sqlite3

def migrate():
    conn = None
    try:
        conn = sqlite3.connect("data/server.db")
        cursor = conn.cursor()
        
        print("Listing tables...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables: {tables}")
        
        print("Migrating users_v2 table...")
        # Check if column exists strictly (SQLite doesn't support IF NOT EXISTS for columns in all versions)
        try:
            cursor.execute("ALTER TABLE users_v2 ADD COLUMN lichess_token VARCHAR(255)")
            conn.commit()
            print("Migration successful.")
        except Exception as e:
            print(f"Migration error (column likely exists): {e}")

    except Exception as e:
        print(f"Connection failed: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate()
