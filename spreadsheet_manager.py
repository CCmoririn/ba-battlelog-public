import os
import gspread
from google.oauth2.service_account import Credentials

def update_spreadsheet(data):
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        raise Exception("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    client = gspread.authorize(creds)
    SPREADSHEET_ID = "1U3lnPymCu4o0VPQgW02ybkq6tGzz7UHYLmDlXmpl9_s"  # 戦闘ログ
    worksheet = client.open_by_key(SPREADSHEET_ID).worksheet("戦闘ログ")
    worksheet.insert_row(data, 3)
    print("スプレッドシートを更新しました:", data)

def get_striker_list_from_sheet():
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        raise Exception("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    client = gspread.authorize(creds)
    SPREADSHEET_ID = "1rDQbwsNtNVaSmX04tZaf7AOX0AnPNhKSee1wv4myVTQ"  # キャラデータ管理
    worksheet = client.open_by_key(SPREADSHEET_ID).worksheet("STRIKER")
    records = worksheet.get_all_records()
    char_list = []
    for row in records:
        name = row.get("キャラ名")
        icon_url = row.get("アイコン")
        if name and icon_url:
            char_list.append({"name": name, "image": icon_url})
    return char_list

def get_special_list_from_sheet():
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        raise Exception("GOOGLE_APPLICATIONS_CREDENTIALS environment variable is not set.")
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    client = gspread.authorize(creds)
    SPREADSHEET_ID = "1rDQbwsNtNVaSmX04tZaf7AOX0AnPNhKSee1wv4myVTQ"  # キャラデータ管理
    worksheet = client.open_by_key(SPREADSHEET_ID).worksheet("SPECIAL")
    records = worksheet.get_all_records()
    char_list = []
    for row in records:
        name = row.get("キャラ名")
        icon_url = row.get("アイコン")
        if name and icon_url:
            char_list.append({"name": name, "image": icon_url})
    return char_list

# ========== その他アイコンのキャッシュ ==========
_OTHER_ICON_SPREADSHEET_ID = "1rDQbwsNtNVaSmX04tZaf7AOX0AnPNhKSee1wv4myVTQ"
_OTHER_ICON_SHEET = "その他アイコン"
_other_icon_cache = {}

def load_other_icon_cache():
    global _other_icon_cache
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        raise Exception("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    client = gspread.authorize(creds)
    ws = client.open_by_key(_OTHER_ICON_SPREADSHEET_ID).worksheet(_OTHER_ICON_SHEET)
    records = ws.get_all_records()
    cache = {}
    for row in records:
        key = row.get('種別', '').strip()
        url = row.get('アイコン', '').strip()
        if key and url:
            cache[key] = url
    _other_icon_cache = cache

def get_other_icon(key):
    return _other_icon_cache.get(key, "")

def reload_other_icon_cache():
    load_other_icon_cache()

# ========== 空欄・重複ヘッダーでも安全な取得関数 ==========
def get_sheet_records_with_empty_safe(worksheet, head_row=2):
    rows = worksheet.get_all_values()
    headers = rows[head_row - 1]
    seen = {}
    uniq_headers = []
    for h in headers:
        base = h.strip() if h.strip() else "空欄"
        count = seen.get(base, 0)
        if count > 0:
            uniq_headers.append(f"{base}_{count+1}")
        else:
            uniq_headers.append(base)
        seen[base] = count + 1

    data = []
    for row in rows[head_row:]:
        record = {}
        for idx, val in enumerate(row):
            if idx < len(uniq_headers):
                record[uniq_headers[idx]] = val
        data.append(record)
    return data

# ========== 「出力結果」シートの完全一致検索（空セル安全対応・デバッグprint入り） ==========
def search_battlelog_output_sheet(query, search_side):
    SPREADSHEET_ID = "1ix6hz4s0AinsepfSHNZ6CMAsNSRW-3l8nJUMBR2DpLQ"
    SHEET_NAME = "出力結果"
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_path = os.environ.get("GOOGLE_APPLICATIONS_CREDENTIALS", os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))
    if not creds_path:
        raise Exception("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    client = gspread.authorize(creds)
    worksheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

    # ★空セル安全な取得
    all_records = get_sheet_records_with_empty_safe(worksheet, head_row=2)

    # デバッグ：列名（キー一覧）を一度だけ出力
    if all_records:
        print("データのキー一覧:", all_records[0].keys())
        print("最初の行サンプル:", all_records[0])

    # キー名対応
    if search_side == "attack":
        char_cols = ["A1", "A2", "A3", "A4", "ASP1", "ASP2"]
    else:
        char_cols = ["D1", "D2", "D3", "D4", "DSP1", "DSP2"]

    result = []
    for row in all_records:
        match = True
        for idx, name in enumerate(query):
            target = row.get(char_cols[idx], "")
            if name and name != target:
                match = False
                break
        if match:
            result.append(row)
    return result
