#!/usr/bin/env python3
"""
Generate a bcrypt hash for a password (same as used in auth).
Use this to set a known demo password: run the script, then update
the user's password_hash in MongoDB with the output.
"""
import bcrypt
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: python hash_password.py <password>")
        print("Example: python hash_password.py demo123")
        sys.exit(1)
    password = sys.argv[1]
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    print(hashed)

if __name__ == "__main__":
    main()
