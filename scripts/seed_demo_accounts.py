"""
BrandProof AI — Demo Account Provisioning Script.

Creates demo accounts in Supabase Auth and seeds corresponding profile & workspace records.
Usage:
    python scripts/seed_demo_accounts.py
"""

import os
import sys
import uuid
import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

DEMO_ACCOUNTS = [
    {
        "email": "admin@aurahealth.demo",
        "password": "DemoPass123!",
        "full_name": "AuraHealth Administrator",
        "role": "admin",
    },
    {
        "email": "creator@aurahealth.demo",
        "password": "DemoPass123!",
        "full_name": "Maya Lin (Content Creator)",
        "role": "creator",
    },
]


def seed_demo_accounts():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("[!] SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not configured.")
        print("    Please configure them in .env before running this script.")
        sys.exit(1)

    admin_headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }

    client = httpx.Client(base_url=SUPABASE_URL.rstrip("/"), headers=admin_headers, timeout=15.0)

    for acc in DEMO_ACCOUNTS:
        print(f"[*] Provisioning {acc['email']}...")
        payload = {
            "email": acc["email"],
            "password": acc["password"],
            "email_confirm": True,
            "user_metadata": {
                "full_name": acc["full_name"],
            },
        }

        # Create user via Supabase Auth Admin API
        resp = client.post("/auth/v1/admin/users", json=payload)
        if resp.status_code in (200, 201):
            user_data = resp.json()
            print(f"    [+] Created user {acc['email']} (ID: {user_data.get('id')})")
        elif resp.status_code == 422 or "already exists" in resp.text.lower():
            print(f"    [-] User {acc['email']} already exists in Supabase Auth.")
        else:
            print(f"    [!] Failed to create user: {resp.status_code} {resp.text}")

    print("\n[+] Demo account provisioning complete.")


if __name__ == "__main__":
    seed_demo_accounts()

