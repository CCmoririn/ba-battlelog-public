import gspread
from google.oauth2.service_account import Credentials

def update_spreadsheet(data):
    """
    スプレッドシートに認識結果を記録（常に3行目に追加）
    """
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    client = gspread.authorize(creds)

    SPREADSHEET_ID = "1YF4mz5kCL0VVXPNwmkq6pCppm5IR6V_5fZbVLh0Ne9M"
    worksheet = client.open_by_key(SPREADSHEET_ID).worksheet("戦闘ログ")

    worksheet.insert_row(data, 3)
    print("スプレッドシートを更新しました:", data)
