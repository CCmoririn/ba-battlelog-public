import os
import sys
import unicodedata
import subprocess
from flask import Flask, request, render_template, jsonify
from main import process_image, call_apps_script
from spreadsheet_manager import (
    update_spreadsheet,
    get_striker_list_from_sheet,
    get_special_list_from_sheet,
    search_battlelog_output_sheet,   # ←★ 追加
    get_other_icon                  # ←★ アイコン取得も利用可能
)

app = Flask(__name__)

# Google サービスアカウント認証情報を環境変数の内容から一時ファイルに書き出す
if "credentials" in os.environ:
    credentials_content = os.environ["credentials"]
    credentials_path = "/tmp/google_credentials.json"
    os.makedirs("/tmp", exist_ok=True)
    with open(credentials_path, "w") as f:
        f.write(credentials_content)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    print("Google Application Default Credentials have been set.")
else:
    print("credentials not found in environment variables.")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        # 画像アップロードフォームを表示
        return render_template("index.html")

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
        return render_template(
            "confirm.html",
            row_data=row_data,
            labels=labels
        )
    except Exception as e:
        print(f"render_template失敗: {e}")  # デバッグ用
        return render_template(
            "complete.html",
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

        return render_template(
            "complete.html",
            message="アップロードが完了しました"
        )
    except subprocess.CalledProcessError as e:
        print(f"しらす式変換エラー: {e}")
        return render_template(
            "complete.html",
            message=f"しらす式変換が失敗しました: {e}"
        )
    except Exception as e:
        print(f"スプレッドシート更新エラー: {e}")
        return render_template(
            "complete.html",
            message=f"スプレッドシートの更新に失敗しました: {e}"
        )

# ★★★ ここから編成検索ページ用ルート（STRIKER/SPECIAL対応） ★★★
@app.route("/search")
def search():
    try:
        striker_list = get_striker_list_from_sheet()
        special_list = get_special_list_from_sheet()
    except Exception as e:
        print(f"キャラリスト取得エラー: {e}")
        striker_list = []
        special_list = []
    return render_template("db.html", striker_list=striker_list, special_list=special_list)

# ★★★ ここから検索API新設 ★★★
@app.route("/api/search", methods=["POST"])
def api_search():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data received"}), 400

        side = data.get("side")         # "attack" または "defense"
        characters = data.get("characters")  # 6キャラ名リスト

        if side not in ["attack", "defense"] or not isinstance(characters, list) or len(characters) != 6:
            return jsonify({"error": "Invalid parameters"}), 400

        # スプレッドシートから検索
        matched_rows = search_battlelog_output_sheet(characters, side)

        # 結果を加工して返却（例：勝ち側・負け側・キャラ・プレイヤー名・種別アイコンURL付き）
        response = []
        for row in matched_rows:
            if side == "attack":
                # 攻撃側を指定した場合、勝った防衛側だけ出す
                if row.get("防衛結果", "") != "Win":
                    continue
                response.append({
                    "winner_type": "defense",
                    "winner_icon": get_other_icon("防衛側"),
                    "winner_player": row.get("防衛側プレイヤー", ""),
                    "winner_characters": [row.get(f"防衛キャラ{i+1}", "") for i in range(6)],
                    "loser_type": "attack",
                    "loser_icon": get_other_icon("攻撃側"),
                    "loser_player": row.get("攻撃側プレイヤー", ""),
                    "loser_characters": [row.get(f"攻撃キャラ{i+1}", "") for i in range(6)],
                    "date": row.get("日付", ""),
                })
            else:
                # 防衛側を指定した場合、勝った攻撃側だけ出す
                if row.get("攻撃結果", "") != "Win":
                    continue
                response.append({
                    "winner_type": "attack",
                    "winner_icon": get_other_icon("攻撃側"),
                    "winner_player": row.get("攻撃側プレイヤー", ""),
                    "winner_characters": [row.get(f"攻撃キャラ{i+1}", "") for i in range(6)],
                    "loser_type": "defense",
                    "loser_icon": get_other_icon("防衛側"),
                    "loser_player": row.get("防衛側プレイヤー", ""),
                    "loser_characters": [row.get(f"防衛キャラ{i+1}", "") for i in range(6)],
                    "date": row.get("日付", ""),
                })
        return jsonify({"results": response})
    except Exception as e:
        print(f"/api/search エラー: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
