import os
import sys
import unicodedata
import subprocess
from flask import Flask, request, render_template_string

from main import process_image, call_apps_script
from spreadsheet_manager import update_spreadsheet

app = Flask(__name__)

# Google 認証情報を環境変数から受け取り
if "credentials" in os.environ:
    cred_content = os.environ["credentials"]
    tmp = "/tmp/google_credentials.json"
    with open(tmp, "w") as f:
        f.write(cred_content)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp

# テンプレート定義は省略せずそのまま
UPLOAD_FORM_HTML = '''…'''
CONFIRM_FORM_HTML = '''…'''  # loop.index0 使用済み
RESULT_PAGE_HTML  = '''…'''

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template_string(UPLOAD_FORM_HTML)

    # POST：画像を受け取って認識のみ
    file = request.files.get("image_file")
    if not file or file.filename == "":
        return "画像が選択されていません。", 400

    dir_ = os.path.abspath("uploads")
    os.makedirs(dir_, exist_ok=True)
    path = os.path.join(dir_, file.filename)
    file.save(path)

    try:
        row_data = process_image(path)  # ← ここでは更新しない
        labels = [  # 略
        ]
        return render_template_string(
            CONFIRM_FORM_HTML,
            row_data=row_data,
            labels=labels
        )
    except Exception as e:
        return render_template_string(RESULT_PAGE_HTML, message=f"エラー: {e}")

@app.route("/confirm", methods=["POST"])
def confirm():
    try:
        # フォーム値取得
        rd = [request.form.get(f"field{i}", "") for i in range(18)]
        rd = [unicodedata.normalize("NFKC", v) for v in rd]

        # 一回だけ更新＆変換
        update_spreadsheet(rd)
        # 同じ interpreter で呼び出し
        subprocess.run([sys.executable, "call_gas.py"], check=True)

        return render_template_string(RESULT_PAGE_HTML, message="完了しました！")
    except Exception as e:
        return render_template_string(RESULT_PAGE_HTML, message=f"失敗しました: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
