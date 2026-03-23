import asyncio
from backend.api.scope_validator import _match_scope_items

scope_items = ["Login validation", "API performance", "Security testing"]
paragraphs = [
    {"index": 0, "text": "We need to perform login validation on the frontend."},
    {"index": 1, "text": "The API performance will be benchmarked."},
    {"index": 2, "text": "Unrelated paragraph about design."}
]

print("Running pure matching algorithm:")
try:
    res = _match_scope_items(scope_items, paragraphs)
    print("Success:", len(res['item_results']), "items processed.")
except Exception as e:
    import traceback
    traceback.print_exc()
