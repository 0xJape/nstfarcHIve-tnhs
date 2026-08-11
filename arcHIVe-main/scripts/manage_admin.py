from getpass import getpass
import sqlite3
import sys

from src.phase2_runtime_api import AUTH_DB, init_auth_db, password_hash


def main() -> int:
    username = sys.argv[1] if len(sys.argv) > 1 else input("Username: ").strip()
    password = getpass("Password: ")
    if not username or not password:
        print("Username and password required")
        return 1
    init_auth_db()
    with sqlite3.connect(AUTH_DB) as connection:
        connection.execute(
            "INSERT INTO admin_users (username, password_hash) VALUES (?, ?) "
            "ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash, active=1",
            (username, password_hash(password)),
        )
    print(f"Admin account saved: {username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
