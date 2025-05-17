import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
import requests

# スコープを定義（警告に合わせて "openid" を追加）
SCOPES = ['https://www.googleapis.com/auth/userinfo.email', 'openid']

# 環境変数から認証情報（OAuth クライアントID JSON文字列）を取得
credentials_content = os.environ.get("GOOGLE_CREDENTIALS")
if not credentials_content:
    raise Exception("Environment variable 'GOOGLE_CREDENTIALS' is not set or empty.")

# 一時ファイルパスを設定し、JSONを書き出し
credentials_path = "/tmp/shirasu_credentials.json"
with open(credentials_path, "w") as f:
    f.write(credentials_content)

# OAuth2 のフローを実行
flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
creds = flow.run_local_server(port=0)

# アクセストークン取得
access_token = creds.token

# GASウェブアプリのエンドポイントURL
url = 'https://script.google.com/macros/s/AKfycby6jamSogeLKTtla3A90hnweRLyRc-E3XryNXeA07nVsJAQy2Dj1pRNfce6WaSm2dwb/exec'

# GETリクエスト送信時のヘッダー
headers = {
    'Authorization': f'Bearer {access_token}',
    # 必要であれば 'Content-Type': 'application/json' などを追加してください
}

response = requests.get(url, headers=headers)

# 応答結果を表示
print("Response status:", response.status_code)
print("Response text:", response.text)

# 一時ファイルの削除
os.remove(credentials_path)

