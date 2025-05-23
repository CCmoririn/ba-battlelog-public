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

    SPREADSHEET_ID = "1U3lnPymCu4o0VPQgW02ybkq6tGzz7UHYLmDlXmpl9_s"
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

    SPREADSHEET_ID = "1rDQbwsNtNVaSmX04tZaf7AOX0AnPNhKSee1wv4myVTQ"
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

    SPREADSHEET_ID = "1rDQbwsNtNVaSmX04tZaf7AOX0AnPNhKSee1wv4myVTQ"
    worksheet = client.open_by_key(SPREADSHEET_ID).worksheet("SPECIAL")

    records = worksheet.get_all_records()
    char_list = []
    for row in records:
        name = row.get("キャラ名")
        icon_url = row.get("アイコン")
        if name and icon_url:
            char_list.append({"name": name, "image": icon_url})
    return char_list
