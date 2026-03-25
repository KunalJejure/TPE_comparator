import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

try:
    supabase = create_client(url, key)
    print("Testing insertion into comparisons...")
    test_data = {
        "original_filename": "test_orig.pdf",
        "revised_filename": "test_rev.pdf",
        "total_pages": 1,
        "status": "PASS",
        "report_url": "test_url"
    }
    res = supabase.table("comparisons").insert(test_data).execute()
    print(f"SUCCESS! Inserted row ID: {res.data[0]['id']}")
except Exception as e:
    print(f"ERROR: {e}")
