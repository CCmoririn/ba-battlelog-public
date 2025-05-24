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
    search_battlelog_output_sheet,
    get_other_icon,
    load_other_icon_cache
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

# キャッシュ初期化
load_other_icon_cache()

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("index.html")
    file = request.files.get("image_file")
    if not file or file.filename == "":
        return "画像ファイルが選択されていません。", 400
    uploads_dir = os.path.abspath("uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    file_path = os.path.join(uploads_dir, file.filename)
    file.save(file_path)
    try:
        row_data = process_image(file_path)
        labels = [
            "日付", "攻撃側プレイヤー", "攻撃結果",
            "攻撃キャラ1", "攻撃キャラ2", "攻撃キャラ3",
            "攻撃キャラ4", "攻撃キャラ5", "攻撃キャラ6",
            "（空白）", "防衛側プレイヤー", "防衛結果",
            "防衛キャラ1", "防衛キャラ2", "防衛キャラ3",
            "防衛キャラ4", "防衛キャラ5", "防衛キャラ6"
        ]
        return render_template(
            "confirm.html",
            row_data=row_data,
            labels=labels
        )
    except Exception as e:
        print(f"render_template失敗: {e}")
        return render_template(
            "complete.html",
            message=f"エラーが発生しました: {e}"
        )

@app.route("/confirm", methods=["POST"])
def confirm():
    try:
        row_data = [
            request.form.get(f"field{i}", "")
            for i in range(18)
        ]
        row_data = [unicodedata.normalize("NFKC", v) for v in row_data]
        update_spreadsheet(row_data)
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

@app.route("/api/search", methods=["POST"])
def api_search():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data received"}), 400
        side = data.get("side")
        characters = data.get("characters")
        if side not in ["attack", "defense"] or not isinstance(characters, list) or len(characters) != 6:
            return jsonify({"error": "Invalid parameters"}), 400
        matched_rows = search_battlelog_output_sheet(characters, side)
        response = []
        # 攻撃側・防衛側・勝ち負けのアイコンURLを取得
        win_icon = get_other_icon("勝ち")
        lose_icon = get_other_icon("負け")
        attack_icon = get_other_icon("攻撃側")
        defense_icon = get_other_icon("防衛側")
        for row in matched_rows:
            if side == "attack":
                if row.get("勝敗_2", "") != "Win":
                    continue
                response.append({
                    "winner_type": "defense",
                    "winner_icon": defense_icon,
                    "winner_winlose_icon": win_icon,
                    "winner_player": row.get("プレイヤー名_2", ""),
                    "winner_characters": [
                        row.get("D1", ""),
                        row.get("D2", ""),
                        row.get("D3", ""),
                        row.get("D4", ""),
                        row.get("DSP1", ""),
                        row.get("DSP2", ""),
                    ],
                    "loser_type": "attack",
                    "loser_icon": attack_icon,
                    "loser_winlose_icon": lose_icon,
                    "loser_player": row.get("プレイヤー名", ""),
                    "loser_characters": [
                        row.get("A1", ""),
                        row.get("A2", ""),
                        row.get("A3", ""),
                        row.get("A4", ""),
                        row.get("ASP1", ""),
                        row.get("ASP2", ""),
                    ],
                    "date": row.get("日付", ""),
                })
            else:
                if row.get("勝敗", "") != "Win":
                    continue
                response.append({
                    "winner_type": "attack",
                    "winner_icon": attack_icon,
                    "winner_winlose_icon": win_icon,
                    "winner_player": row.get("プレイヤー名", ""),
                    "winner_characters": [
                        row.get("A1", ""),
                        row.get("A2", ""),
                        row.get("A3", ""),
                        row.get("A4", ""),
                        row.get("ASP1", ""),
                        row.get("ASP2", ""),
                    ],
                    "loser_type": "defense",
                    "loser_icon": defense_icon,
                    "loser_winlose_icon": lose_icon,
                    "loser_player": row.get("プレイヤー名_2", ""),
                    "loser_characters": [
                        row.get("D1", ""),
                        row.get("D2", ""),
                        row.get("D3", ""),
                        row.get("D4", ""),
                        row.get("DSP1", ""),
                        row.get("DSP2", ""),
                    ],
                    "date": row.get("日付", ""),
                })
        print("API返却データ:", response)
        return jsonify({"results": response})
    except Exception as e:
        print(f"/api/search エラー: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
