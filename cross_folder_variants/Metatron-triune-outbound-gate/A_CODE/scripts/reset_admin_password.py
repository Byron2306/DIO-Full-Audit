#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Load .env manually if python-dotenv not available
env_path = Path(__file__).resolve().parents[1] / '.env'
if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'metatron_test')

if not ADMIN_EMAIL or not ADMIN_PASSWORD:
    print('ADMIN_EMAIL or ADMIN_PASSWORD not set in .env; aborting')
    sys.exit(1)

# Import hash_password from the app
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from backend.routers.dependencies import hash_password
except Exception as e:
    print('Failed to import hash_password from backend.routers.dependencies:', e)
    print('Make sure you run this from the repository root and Python path is correct.')
    sys.exit(1)

try:
    from pymongo import MongoClient
except Exception as e:
    print('pymongo not installed. Install with: pip install pymongo')
    sys.exit(1)

hashed = hash_password(ADMIN_PASSWORD)

client = MongoClient(MONGO_URL)
db = client[DB_NAME]
normalized = ADMIN_EMAIL.strip().lower()
res = db.users.update_one({'email': normalized}, {'$set': {'password': hashed}})
if res.matched_count:
    print(f"Updated password for existing user {normalized}")
else:
    import uuid
    from datetime import datetime, timezone
    user_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    doc = {
        'id': user_id,
        'email': normalized,
        'password': hashed,
        'name': os.environ.get('ADMIN_NAME', 'Admin'),
        'role': 'admin',
        'created_at': created_at,
    }
    db.users.insert_one(doc)
    print(f"Inserted new admin user {normalized}")

print('Done')
