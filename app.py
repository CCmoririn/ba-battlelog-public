import os
import sys
import unicodedata
import subprocess
from flask import Flask, request, render_template_string
from main import process_image, call_apps_script
from spreadsheet_manager import update_spreadsheet

app = Flask(__name__)

# Google サービスアカウント認証情報を環境変数から読み込んでセット
if "credentials" in os.environ:
    credentials_content = os.environ["credentials"]
    credentials_path = "/tmp/google_credentials.json"
    with open(credentials_path, "w") as f:
        f.write(credentials_content)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    print("Google Application Default Credentials have been set.")
else:
    print("credentials not found in environment variables.")

# アップロードフォームHTML
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

# 確認・編集フォームHTML
CONFIRM_FORM_HTML = '''
<!doctype html>
<html>
  <head><title>内容確認</title></head>
  <body>
    <h1>認識結果を確認・編集してください</h1>
    <form method="post" action="/confirm">
      {% for label in labels %}
        <label>{{ label }}:
          <input type="text" name="field{{ loop.index0 }}" value="{{ row_data[loop.index0] }}">
        </label><br>
      {% endfor %}
      <button type="submit">確定</button>
    </form>
  </body>
</html>
'''

# 結果ページHTML
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

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        # 画像アップロードフォームを表示
        return render_template_string(UPLOAD_FORM_HTML)

    # POST：ファイル受け取り→OCRのみ
    file = request.files.get("image_file")
    if not file or file.filename == "":
        return "画像ファイルが選択されていません。", 400

    uploads_dir = os.path.abspath("uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    file_path = os.path.join(uploads_dir, file.filename)
    file.save(file_path)

    try:
        # OCR＋データ抽出
        row_data = process_image(file_path)

        # 確認フォーム用ラベル
        labels = [
            "日付", "攻撃側プレイヤー", "攻撃結果",
            "攻撃キャラ1", "攻撃キャラ2", "攻撃キャラ3",
            "攻撃キャラ4", "攻撃キャラ5", "攻撃キャラ6",
            "（空白）", "防衛側プレイヤー", "防衛結果",
            "防衛キャラ1", "防衛キャラ2", "防衛キャラ3",
            "防衛キャラ4", "防衛キャラ5", "防衛キャラ6"
        ]

        # 確認・編集フォームを表示
        return render_template_string(
            CONFIRM_FORM_HTML,
            row_data=row_data,
            labels=labels
        )
    except Exception as e:
        return render_template_string(
            RESULT_PAGE_HTML,
            message=f"エラーが発生しました: {e}"
        )

@app.route("/confirm", methods=["POST"])
def confirm():
    try:
        # フォームの値を取得して再構築
        row_data = [
            request.form.get(f"field{i}", "")
            for i in range(18)
        ]
        # 全角→半角正規化
        row_data = [unicodedata.normalize("NFKC", v) for v in row_data]

        # スプレッドシート更新
        update_spreadsheet(row_data)
        # しらす式変換を一度だけ実行
        subprocess.run(
            [sys.executable, "call_gas.py"],
            check=True
        )

        return render_template_string(
            RESULT_PAGE_HTML,
            message="スプレッドシートの更新に成功しました！"
        )
    except subprocess.CalledProcessError as e:
        return render_template_string(
            RESULT_PAGE_HTML,
            message=f"しらす式変換が失敗しました: {e}"
        )
    except Exception as e:
        return render_template_string(
            RESULT_PAGE_HTML,
            message=f"スプレッドシートの更新に失敗しました: {e}"
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
