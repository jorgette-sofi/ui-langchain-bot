import gspread
import os
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Cache for every 5mins
_cache = {"users": set(), "last_updated": None}
CACHE_TTL_MINUTES = 5

# def _load_sheet():
#     creds = Credentials.from_service_account_file("google_credentials.json", scopes=SCOPES)
#     client = gspread.authorize(creds)
#     sheet = client.open_by_key(os.getenv("GOOGLE_SHEET_ID")).sheet2
#     names = sheet.col_values(2)
#     return {name.strip().lower() for name in names if name.strip()}
#     print(f"[Access Control] Loaded {len(result)} users: {sorted(result)}")=
#     return result

def _load_sheet():
    creds = Credentials.from_service_account_file("google_credentials.json", scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(os.getenv("GOOGLE_SHEET_ID")).worksheet("Telegram Accounts")
    names = sheet.col_values(2)[1:]  # skip header row
    result = {name.strip().lower() for name in names if name.strip()}
    print(f"GSheets Allowed Users: {sorted(result)}")
    return result


def allowedUsers(firstName: str, lastName: str = None) -> bool:
    global _cache
    now = datetime.now()

    # Refresh cache every 5mins
    if not _cache["last_updated"] or now - _cache["last_updated"] > timedelta(minutes=CACHE_TTL_MINUTES):
        _cache["users"] = _load_sheet()
        _cache["last_updated"] = now

    # Clean missing names
    fname = firstName.strip() if firstName else ""
    lname = lastName.strip() if lastName else ""

    full_name = f"{fname} {lname}".strip().lower()
    print("TG Name:", full_name)
    return full_name in _cache["users"]