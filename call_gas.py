from google_auth_oauthlib.flow import InstalledAppFlow
import requests

# スコープを定義（警告に合わせて "openid" 追加してもOK）
SCOPES = ['https://www.googleapis.com/auth/userinfo.email', 'openid']

# OAuth2 認証の流れ
flow = InstalledAppFlow.from_client_secrets_file(
    'shirasu_credentials.json', SCOPES)
creds = flow.run_local_server(port=0)

# アクセストークン取得
access_token = creds.token

# GASのウェブアプリURL（GET用）
url = 'https://script.google.com/macros/s/AKfycby6jamSogeLKTtla3A90hnweRLyRc-E3XryNXeA07nVsJAQy2Dj1pRNfce6WaSm2dwb/exec'

# GETリクエスト送信
response = requests.get(url, headers={
    'Authorization': f'Bearer {access_token}'
})

# 応答を表示
print("Response status:", response.status_code)
print("Response text:", response.text)
