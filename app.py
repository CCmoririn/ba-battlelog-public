import os
import cv2
import datetime
import numpy as np
import requests  # URLから画像ダウンロード用
import unicodedata  # Unicode正規化用
import subprocess
from flask import Flask, request, render_template_string

app = Flask(__name__)

# Render 上で Google Cloud の認証情報が環境変数に設定されている場合
if "credentials" in os.environ:
    # 一時的なファイルパスを指定（/tmp は Linux の一般的な一時フォルダ）
    credentials_path = "/tmp/google_credentials.json"
    # 環境変数から認証情報の内容を取得
    credentials_content = os.environ["credentials"]
    # 内容を一時ファイルに書き出す
    with open(credentials_path, "w") as cred_file:
        cred_file.write(credentials_content)
    # Google クライアントライブラリが参照する環境変数にパスを設定
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    print("Google Application Default Credentials have been set.")
else:
    print("credentials not found in environment variables.")

# HTMLテンプレート：アップロードフォーム
UPLOAD_FORM_HTML = '''
<!doctype html>
<html>
  <head><title>画像アップロード</title></head>
  <body>
    <h1>画像をアップロードしてください</h1>
    <form method="post" enctype="multipart/form-data">
      <input type="file" name="image_file" accept="image/*" required>
      <button type="submit">送信</button>
    </form>
  </body>
</html>
'''

# HTMLテンプレート：確認フォーム
CONFIRM_FORM_HTML = '''
<!doctype html>
<html>
  <head><title>内容確認</title></head>
  <body>
    <h1>認識結果を確認・編集してください</h1>
    <form method="post" action="/confirm">
      {% for idx, label in enumerate(labels) %}
        <label>{{ label }}: <input type="text" name="field{{ idx }}" value="{{ row_data[idx] }}"></label><br>
      {% endfor %}
      <button type="submit">確定</button>
    </form>
  </body>
</html>
'''

# HTMLテンプレート：結果ページ
RESULT_PAGE_HTML = '''
<!doctype html>
<html>
  <head><title>結果</title></head>
  <body>
    <h1>{{ message }}</h1>
    <a href="/">トップに戻る</a>
  </body>
</html>
'''

@app.route("/healthz")
def health_check():
    return "OK", 200

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "image_file" not in request.files:
            return "画像ファイルが選択されていません。", 400
        file = request.files["image_file"]
        if file.filename == "":
            return "画像ファイルが選択されていません。", 400
        # アップロードフォルダに保存
        uploads_dir = os.path.abspath("uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        file_path = os.path.join(uploads_dir, file.filename)
        file.save(file_path)
        try:
            # 画像処理＆OCR
            row_data = process_image(file_path)
            # 確認用フォームに渡すラベル定義
            labels = [
                "日付", "攻撃側プレイヤー", "攻撃結果",
                "攻撃キャラ1", "攻撃キャラ2", "攻撃キャラ3",
                "攻撃キャラ4", "攻撃キャラ5", "攻撃キャラ6",
                "（空白）", "防衛側プレイヤー", "防衛結果",
                "防衛キャラ1", "防衛キャラ2", "防衛キャラ3",
                "防衛キャラ4", "防衛キャラ5", "防衛キャラ6"
            ]
            return render_template_string(
                CONFIRM_FORM_HTML,
                row_data=row_data,
                labels=labels
            )
        except Exception as e:
            return render_template_string(RESULT_PAGE_HTML, message=f"エラーが発生しました: {str(e)}")
    else:
        return render_template_string(UPLOAD_FORM_HTML)

@app.route("/confirm", methods=["POST"])
def confirm():
    try:
        # フォームで送信された各フィールドの値を取得し、元のrow_dataリストに再構築
        row_data = []
        for i in range(18):
            field_value = request.form.get(f"field{i}", "")
            row_data.append(field_value)
        # Unicode 正規化で全角文字を半角に変換
        row_data = [unicodedata.normalize('NFKC', field) for field in row_data]
        # スプレッドシートを更新
        update_spreadsheet(row_data)
        # しらす式変換を即時実行
        subprocess.run(["python", "call_gas.py"], check=True)
        return render_template_string(RESULT_PAGE_HTML, message="スプレッドシートの更新に成功しました！")
    except Exception as e:
        return render_template_string(RESULT_PAGE_HTML, message=f"スプレッドシートの更新に失敗しました: {str(e)}")

if __name__ == "__main__":
    # Render環境ではPORT環境変数を使って起動
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
