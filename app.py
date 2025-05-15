import os
import cv2
import datetime
import numpy as np
import requests  # URLから画像ダウンロード用
import unicodedata  # Unicode正規化用
from flask import Flask, request, render_template_string
# 必要に応じてGoogle Sheets API用のライブラリ（例：gspread）をインポートしてください
from ocr_processing import perform_google_vision_ocr
from spreadsheet_manager import update_spreadsheet

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Health check 用エンドポイント（Render のヘルスチェック設定に対応）
@app.route("/healthz")
def health_check():
    return "OK", 200

def get_template_urls():
    """
    テンプレート画像のURLを返します。
      - 攻撃側（剣アイコン）のURL（セルB2）
      - 防衛側（盾アイコン）のURL（セルB3、今回は未使用）
    ※ 実際は認証済みのGoogle Sheets API等で取得してください。
    """
    attack_url = "https://drive.google.com/uc?export=download&id=1fvs35cCs0aKtxNZ1hX_myjiA_RrPufmB"
    defense_url = "https://drive.google.com/uc?export=download&id=17AdY1q9ZynxTNlBVUvJTmZMd220uC_bs"
    return attack_url, defense_url

def load_template(url):
    """
    URLからテンプレート画像をダウンロードし、カラー画像として取得後、
    80×80 にリサイズして返します。グレースケール変換は行いません。
    デバッグ用に "debug_template_resized.jpg" として保存します。
    """
    response = requests.get(url)
    response.raise_for_status()
    img_array = np.asarray(bytearray(response.content), dtype=np.uint8)
    template = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    template = cv2.resize(template, (80, 80))
    cv2.imwrite("debug_template_resized.jpg", template)
    print("Resized template image saved as 'debug_template_resized.jpg'.")
    return template

def match_icon(roi_img, template_img, thresh=0.4):
    """
    ROI画像とテンプレート画像（いずれもカラー画像）でテンプレートマッチングを実施し、
    結果の最大類似度が thresh 以上なら True を返します。
    """
    res = cv2.matchTemplate(roi_img, template_img, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    print("Template match max value:", max_val)
    return max_val >= thresh

def clean_text(text):
    """
    OCRで得られたテキストについて、まず "*" を削除し、
    改行およびすべての空白を削除（連結）します。
    例: "シロコ テ ラー" → "シロコテラー"
    """
    return "".join(text.replace('*', '').replace('\n', '').replace('\r', '').split())

def preprocess_image(image_path):
    """
    画像の前処理：入力画像から中央の明るい部分を抽出し、
    最終サイズ 1611×696 にリサイズします（輪郭検出を利用）。
    """
    print("Attempting to load image from:", image_path)
    if not os.path.exists(image_path):
        raise Exception("ファイルが存在しません:" + image_path)
    img = cv2.imread(image_path)
    if img is None:
        raise Exception("画像が読み込めませんでした。")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    ret, thresh_img = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        cropped = img
    else:
        largest_contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest_contour)
        cropped = img[y:y+h, x:x+w]
    resized = cv2.resize(cropped, (1611, 696), interpolation=cv2.INTER_AREA)
    return resized

def mask_regions(image):
    """
    指定された領域を白で塗りつぶします。
    マスク領域：
      - (425,150)〜(700,225)
      - (1260,150)〜(1535,225)
      - (0,240)〜(1611,565)
    ※ 領域4は不要です。
    """
    cv2.rectangle(image, (425, 150), (700, 225), (255, 255, 255), thickness=-1)
    cv2.rectangle(image, (1260, 150), (1535, 225), (255, 255, 255), thickness=-1)
    cv2.rectangle(image, (0, 240), (1611, 565), (255, 255, 255), thickness=-1)
    return image

def parse_ocr_text(ocr_text):
    """
    OCR全体のテキストから、「VS」以前の部分をヘッダーとして利用し、
    プレイヤー名（"Lv.90 ..."）と勝敗（Win/Lose）を抽出します。
    """
    lines = [l.strip() for l in ocr_text.splitlines() if l.strip()]
    try:
        vs_index = lines.index("VS")
    except ValueError:
        vs_index = None
    header_lines = lines[:vs_index] if vs_index is not None else lines[:len(lines)//2]
    lv_entries = [(i, line) for i, line in enumerate(header_lines) if line.startswith("Lv.")]
    if len(lv_entries) >= 2:
        left_idx, left_line = lv_entries[0]
        right_idx, right_line = lv_entries[1]
        left_player = left_line.replace("Lv.90", "").strip()
        right_player = right_line.replace("Lv.90", "").strip()
    else:
        left_player, right_player = "LeftPlayer", "RightPlayer"
        left_idx = right_idx = -1
    win_positions = [i for i, line in enumerate(header_lines) if "Win" in line]
    lose_positions = [i for i, line in enumerate(header_lines) if "Lose" in line]
    if win_positions and lose_positions:
        left_win_dist = min([abs(left_idx - pos) for pos in win_positions])
        left_lose_dist = min([abs(left_idx - pos) for pos in lose_positions])
        if left_win_dist <= left_lose_dist:
            left_result, right_result = "Win", "Lose"
        else:
            left_result, right_result = "Lose", "Win"
    elif win_positions:
        left_win_dist = min([abs(left_idx - pos) for pos in win_positions])
        right_win_dist = min([abs(right_idx - pos) for pos in win_positions])
        if left_win_dist <= right_win_dist:
            left_result, right_result = "Win", "Lose"
        else:
            left_result, right_result = "Lose", "Win"
    elif lose_positions:
        left_lose_dist = min([abs(left_idx - pos) for pos in lose_positions])
        right_lose_dist = min([abs(right_idx - pos) for pos in lose_positions])
        if left_lose_dist <= right_lose_dist:
            left_result, right_result = "Lose", "Win"
        else:
            left_result, right_result = "Win", "Lose"
    else:
        left_result = right_result = ""
    return left_player, left_result, right_player, right_result, None, None

def ocr_region(image, region):
    """
    指定された領域 (x1, y1, x2, y2) の部分画像からOCRを実施し、
    結果に clean_text() を適用して返します。
    """
    x1, y1, x2, y2 = region
    sub_img = image[y1:y2, x1:x2]
    temp_path = "temp_region.jpg"
    cv2.imwrite(temp_path, sub_img)
    text = perform_google_vision_ocr(temp_path)
    os.remove(temp_path)
    return clean_text(text)

def process_image(image_path):
    """
    指定された画像を処理し、ヘッダーおよびキャラ名のOCR結果とアイコン判定（剣アイコン）
    に基づいて、攻撃側情報と防衛側情報に分けた row_data を返します。
    """
    preprocessed_img = preprocess_image(image_path)
    
    # ヘッダー用にマスク処理
    masked_img = mask_regions(preprocessed_img.copy())
    debug_path = "debug_preprocessed.jpg"
    cv2.imwrite(debug_path, masked_img)
    print("前処理・マスク後の画像を保存しました:", debug_path)
    
    temp_path = "temp_preprocessed.jpg"
    cv2.imwrite(temp_path, masked_img)
    full_ocr_text = perform_google_vision_ocr(temp_path)
    os.remove(temp_path)
    print("OCR recognized text (header extraction):")
    print(full_ocr_text)
    
    left_player, left_result, right_player, right_result, _, _ = parse_ocr_text(full_ocr_text)
    
    # アイコン検出用ROI (35,115)〜(115,195)
    icon_roi = preprocessed_img[115:195, 35:115]
    cv2.imwrite("debug_icon_roi.jpg", icon_roi)
    print("Icon ROI saved as 'debug_icon_roi.jpg'.")
    
    # 剣アイコン判定用テンプレート画像の取得
    attack_url, defense_url = get_template_urls()
    attack_template = load_template(attack_url)
    
    # カラー画像同士のテンプレートマッチングを実施（閾値0.4）
    left_has_sword = match_icon(icon_roi, attack_template, thresh=0.4)
    print("Left has sword:", left_has_sword)
    
    # 剣の検出結果に基づいて、攻撃側プレイヤーを決定
    if left_has_sword:
        attack_side_player = left_player
        attack_side_result = left_result
        defense_side_player = right_player
        defense_side_result = right_result
    else:
        attack_side_player = right_player
        attack_side_result = right_result
        defense_side_player = left_player
        defense_side_result = left_result
    
    # キャラクター領域抽出（下限680で設定）
    left_regions = [
        (87, 637, 183, 680),
        (186, 637, 280, 680),
        (284, 637, 379, 680),
        (383, 637, 478, 680),
        (481, 637, 576, 680),
        (579, 637, 679, 680)
    ]
    right_regions = [
        (922, 637, 1017, 680),
        (1020, 637, 1115, 680),
        (1118, 637, 1213, 680),
        (1216, 637, 1311, 680),
        (1314, 637, 1409, 680),
        (1412, 637, 1512, 680)
    ]
    
    left_chars = [ocr_region(preprocessed_img, region) for region in left_regions]
    right_chars = [ocr_region(preprocessed_img, region) for region in right_regions]
    
    print("Extracted left characters:")
    for idx, char in enumerate(left_chars, start=1):
        print(f"Left[{idx}]: '{char}'")
    print("Extracted right characters:")
    for idx, char in enumerate(right_chars, start=1):
        print(f"Right[{idx}]: '{char}'")
    
    # 出力配置：攻撃側情報とそのキャラ情報、その後に空白1列を挟んで防衛側情報とそのキャラ情報
    if left_has_sword:
        attack_chars = left_chars
        defense_chars = right_chars
    else:
        attack_chars = right_chars
        defense_chars = left_chars
    
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row_data = (
        [date_str, attack_side_player, attack_side_result] +
        attack_chars +
        [""] +  # 空白列：これにより防衛側情報がK列（11列目）から開始
        [defense_side_player, defense_side_result] +
        defense_chars
    )
    
    # ※ この段階ではスプレッドシートには更新せず、確認・修正画面にrow_dataを渡します。
    return row_data

# HTMLテンプレート：画像アップロードフォーム
UPLOAD_FORM_HTML = '''
<!doctype html>
<html>
  <head>
    <title>画像アップロード</title>
  </head>
  <body>
    <h1>画像アップロード</h1>
    <form method="post" enctype="multipart/form-data">
      <input type="file" name="image_file">
      <br><br>
      <input type="submit" value="アップロードして処理">
    </form>
  </body>
</html>
'''

# HTMLテンプレート：確認・修正用フォーム
# ここでは、OCRで抽出された各フィールド（全18項目）を表示し、ユーザーが修正可能な状態にします。
# 先頭に「修正時、記号は全て半角で入力するように!」という注意文を追加しました。
CONFIRM_FORM_HTML = '''
<!doctype html>
<html>
  <head>
    <title>確認・修正画面</title>
  </head>
  <body>
    <h1>抽出結果の確認・修正</h1>
    <p style="color:red; font-weight:bold;">修正時、記号は全て半角で入力するように!</p>
    <form method="POST" action="/confirm">
      <table border="1" cellpadding="5" cellspacing="0">
        <tr>
          <th>項目</th>
          <th>値</th>
        </tr>
        {% for i in range(row_data|length) %}
        <tr>
          <td>{{ labels[i] }}</td>
          <td>
            {% if i == 9 %}
              <!-- 空白列は編集不可に -->
              <input type="text" name="field{{ i }}" value="{{ row_data[i] }}" readonly>
            {% else %}
              <input type="text" name="field{{ i }}" value="{{ row_data[i] }}">
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </table>
      <br>
      <input type="submit" value="上記内容でスプレッドシートへ送信">
    </form>
  </body>
</html>
'''

# HTMLテンプレート：最終確認画面（成功時またはエラー時）
RESULT_PAGE_HTML = '''
<!doctype html>
<html>
  <head>
    <title>結果</title>
  </head>
  <body>
    <h1>{{ message }}</h1>
    <a href="/">トップに戻る</a>
  </body>
</html>
'''

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "image_file" not in request.files:
            return "画像ファイルが選択されていません。", 400
        file = request.files["image_file"]
        if file.filename == "":
            return "画像ファイルが選択されていません。", 400
        # 画像をアップロードフォルダに保存
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        # 画像処理を実行して抽出結果（row_data）を取得
        try:
            row_data = process_image(file_path)
            # 確認・修正用フォームに渡すため、各フィールドのラベルも定義
            labels = [
                "日付",
                "攻撃側プレイヤー",
                "攻撃結果",
                "攻撃キャラ1",
                "攻撃キャラ2",
                "攻撃キャラ3",
                "攻撃キャラ4",
                "攻撃キャラ5",
                "攻撃キャラ6",
                "（空白）",
                "防衛側プレイヤー",
                "防衛結果",
                "防衛キャラ1",
                "防衛キャラ2",
                "防衛キャラ3",
                "防衛キャラ4",
                "防衛キャラ5",
                "防衛キャラ6"
            ]
            return render_template_string(CONFIRM_FORM_HTML, row_data=row_data, labels=labels)
        except Exception as e:
            return render_template_string(RESULT_PAGE_HTML, message=f"エラーが発生しました: {str(e)}")
    else:
        # GET の場合、画像アップロードフォームを表示
        return render_template_string(UPLOAD_FORM_HTML)

@app.route("/confirm", methods=["POST"])
def confirm():
    # フォームで送信された各フィールドの値を取得し、元のrow_dataリストに再構築
    try:
        row_data = []
        for i in range(18):
            field_value = request.form.get(f"field{i}", "")
            row_data.append(field_value)
        # Unicode 正規化を使って全角文字（括弧含む）を半角に変換する
        row_data = [unicodedata.normalize('NFKC', field) for field in row_data]
        # 修正済みデータでスプレッドシート更新
        update_spreadsheet(row_data)
        return render_template_string(RESULT_PAGE_HTML, message="スプレッドシートの更新に成功しました！")
    except Exception as e:
        return render_template_string(RESULT_PAGE_HTML, message=f"スプレッドシートの更新に失敗しました: {str(e)}")

if __name__ == "__main__":
    # Render 環境では環境変数 PORT に指定されたポートを使用します。
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)



