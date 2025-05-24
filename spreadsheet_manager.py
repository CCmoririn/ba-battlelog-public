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
        raise Exception("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
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

# ========== 表記ゆれを吸収して一致判定 ==========
def normalize(s):
    if s is None:
        return ""
    s = s.replace(" ", "").replace("　", "").replace("＊", "*")
    s = s.replace("（", "(").replace("）", ")").replace("(", "(").replace(")", ")")
    return s.strip()

# ========== 「出力結果」シートの完全一致検索（SP枠順不同対応） ==========
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

    all_records = get_sheet_records_with_empty_safe(worksheet, head_row=2)

    if all_records:
        print("データのキー一覧:", all_records[0].keys())
        print("最初の行サンプル:", all_records[0])

    if search_side == "attack":
        char_cols = ["A1", "A2", "A3", "A4", "ASP1", "ASP2"]
    else:
        char_cols = ["D1", "D2", "D3", "D4", "DSP1", "DSP2"]

    def split_main_and_sp(lst):
        """[main4, sp1, sp2]のリストを(main4, sorted(sp1,sp2))で返す"""
        return lst[:4], sorted(lst[4:6])

    result = []
    for row in all_records:
        match = True
        debug_compare = []
        # クエリとデータを正規化
        query_norm = [normalize(x) for x in query]
        target = [normalize(row.get(c, "")) for c in char_cols]
        # メイン枠とSP枠で分けて比較
        q_main, q_sp = split_main_and_sp(query_norm)
        t_main, t_sp = split_main_and_sp(target)
        for i in range(4):
            debug_compare.append(f"{char_cols[i]}: '{q_main[i]}' vs '{t_main[i]}'")
            if q_main[i] != t_main[i]:
                match = False
                break
        if match and q_sp != t_sp:
            debug_compare.append(f"SP: {q_sp} vs {t_sp}（順不同一致）")
            match = False
        print("比較:", debug_compare)
        if match:
            result.append(row)
    return result
