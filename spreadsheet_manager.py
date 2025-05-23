import os
import gspread
from google.oauth2.service_account import Credentials

def update_spreadsheet(data):
    """
    スプレッドシートに認識結果を記録（常に3行目に追加）
    """
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    
    # 環境変数から認証情報ファイルのパスを取得
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        raise Exception("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
    
    # 取得した認証情報ファイルのパスを使って資格情報を作成
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    client = gspread.authorize(creds)

    SPREADSHEET_ID = "1U3lnPymCu4o0VPQgW02ybkq6tGzz7UHYLmDlXmpl9_s"
    worksheet = client.open_by_key(SPREADSHEET_ID).worksheet("戦闘ログ")

    worksheet.insert_row(data, 3)
    print("スプレッドシートを更新しました:", data)

def get_character_list_from_sheet():
    """
    スプレッドシート「キャラデータ管理」シートからキャラ名とアイコンURLだけを取得してリスト化
    """
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        raise Exception("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")

    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    client = gspread.authorize(creds)

    # ご主人のキャラデータ管理シートID
    SPREADSHEET_ID = "1rDQbwsNtNVaSmX04tZaf7AOX0AnPNhKSee1wv4myVTQ"
    worksheet = client.open_by_key(SPREADSHEET_ID).worksheet("キャラデータ管理")

    # 全行を辞書型で取得
    records = worksheet.get_all_records()
    char_list = []
    for row in records:
        name = row.get("キャラ名")
        icon_url = row.get("アイコン")
        if name and icon_url:
            char_list.append({"name": name, "image": icon_url})
    return char_list
