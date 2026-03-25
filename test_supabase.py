import os
from dotenv import load_dotenv
from supabase import create_client

# Load .env
load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

print(f"URL: {url}")
print(f"Key: {key[:10]}...") # Only print first 10 for safety

if not url or not key:
    print("ERROR: SUPABASE_URL or SUPABASE_KEY missing in .env")
    exit(1)

try:
    supabase = create_client(url, key)
    res = supabase.table("comparisons").select("*", count="exact").execute()
    print("SUCCESS: Connection established.")
    print(f"Total entries in 'comparisons': {res.count if hasattr(res, 'count') else 'N/A'}")
    print(f"Data received: {res.data}")
except Exception as e:
    print(f"ERROR: {e}")
