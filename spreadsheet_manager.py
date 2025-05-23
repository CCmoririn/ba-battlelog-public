import os
import gspread
from google.oauth2.service_account import Credentials

def update_spreadsheet(data):
    """
    スプレッドシートに認識結果を記録（常に3行目に追加）
    """
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
    """
    スプレッドシート「STRIKER」シートからキャラ名とアイコンURLを取得
    """
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
    """
    スプレッドシート「SPECIAL」シートからキャラ名とアイコンURLを取得
    """
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
_OTHER_ICON_SPREADSHEET_ID = "1rDQbwsNtNVaSmX04tZaf7AOX0AnPNhKSee1wv4myVTQ"  # キャラデータ管理
_OTHER_ICON_SHEET = "その他アイコン"
_other_icon_cache = {}

def load_other_icon_cache():
    """
    その他アイコンシートを読み込みキャッシュに保存（アプリ起動時 or 明示的に再読込時用）
    """
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
    """
    種別（攻撃側／防衛側 など）からアイコンURLを取得
    """
    return _other_icon_cache.get(key, "")

def reload_other_icon_cache():
    """
    その他アイコンキャッシュを明示的に再読込
    """
    load_other_icon_cache()

# ========== 「出力結果」シートの完全一致検索 ==========
def search_battlelog_output_sheet(query, search_side):
    """
    「P_Blue-Archive-Battlelog-collect」スプレッドシートの「出力結果」シートを
    指定キャラ6体完全一致（空欄はワイルドカード）＆攻撃/防衛側の切替で検索。
    query: 検索キャラ名リスト（6枠、STRIKER4+SPECIAL2の順、空欄は無視）
    search_side: 'attack' または 'defense'（どちら側を指定するか）
    戻り値: 該当行のリスト（dict形式）
    """
    SPREADSHEET_ID = "1ix6hz4s0AinsepfSHNZ6CMAsNSRW-3l8nJUMBR2DpLQ"  # P_Blue-Archive-Battlelog-collect
    SHEET_NAME = "出力結果"
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_path = os.environ.get("GOOGLE_APPLICATIONS_CREDENTIALS", os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))
    if not creds_path:
        raise Exception("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    client = gspread.authorize(creds)
    worksheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    all_records = worksheet.get_all_records()

    result = []
    for row in all_records:
        if search_side == "attack":
            char_cols = [f"攻撃キャラ{i+1}" for i in range(6)]
        else:
            char_cols = [f"防衛キャラ{i+1}" for i in range(6)]
        match = True
        for idx, name in enumerate(query):
            target = row.get(char_cols[idx], "")
            if name and name != target:
                match = False
                break
        if match:
            result.append(row)
    return result
