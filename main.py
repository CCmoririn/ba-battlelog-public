import os
import cv2
import pytz
import datetime
import numpy as np
import requests  # URLからの画像ダウンロード用
# 必要に応じてGoogle Sheets API用のライブラリ（例：gspread）をインポートしてください

# 日本時間 (JST) を定義
JST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(JST)

from ocr_processing import perform_google_vision_ocr
from spreadsheet_manager import update_spreadsheet

def get_template_urls():
    """
    Google スプレッドシートID "12rEszTQ20FdLoxBewBtz0kF8-MUt0TnBYrIwMj1E7c4"
    の「sonotaicon」シートからテンプレート画像のURLを取得します。
      - セルB2：攻撃側（剣アイコン）のURL（こちらを使用します）
      - セルB3：防衛側アイコンのURL（盾版用、今回は未使用）
    
    ※ 実際の環境では認証済みの gspread などを用いて取得してください。
    このコードでは、プレースホルダとして直接URLを設定しています。
    """
    attack_url = "https://drive.google.com/uc?export=download&id=1fvs35cCs0aKtxNZ1hX_myjiA_RrPufmB"
    defense_url = "https://drive.google.com/uc?export=download&id=17AdY1q9ZynxTNlBVUvJTmZMd220uC_bs"
    return attack_url, defense_url

def load_template(url):
    """
    指定されたURLからテンプレート画像をダウンロードし、カラー画像として取得後、
    80×80にリサイズして返します。グレースケール変換は行いません。
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

def match_icon(roi_img, template_img, thresh=0.5):
    """
    カラー画像同士でテンプレートマッチングを実施し、最大類似度が thresh 以上ならTrueを返します。
    """
    res = cv2.matchTemplate(roi_img, template_img, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    print("Template match max value:", max_val)
    return max_val >= thresh

def clean_text(text):
    """
    OCRで得られたテキストについて、まず "*" を削除し、
    改行および全ての空白を除去して連結します。
    例: "シロコ テ ラー" → "シロコテラー"
    """
    return "".join(text.replace('*', '').replace('\n', '').replace('\r', '').split())

def preprocess_image(image_path):
    """
    画像の前処理：画像から中央の明るい領域を抽出し、最終サイズを1611×696にリサイズします。
    輪郭検出を利用しています。
    """
    print("Attempting to load image from:", image_path)
    if not os.path.exists(image_path):
        raise Exception("ファイルが存在しません:" + image_path)
    img = cv2.imread(image_path)
    if img is None:
        raise Exception("画像が読み込めませんでした。")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5,5), 0)
    ret, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        cropped = img
    else:
        largest_contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest_contour)
        cropped = img[y:y+h, x:x+w]
    resized = cv2.resize(cropped, (1611,696), interpolation=cv2.INTER_AREA)
    return resized

def mask_regions(image):
    """
    指定領域を白で塗りつぶしてマスクします。
    マスク領域：
      - (425,150)〜(700,225)
      - (1260,150)〜(1535,225)
      - (0,240)〜(1611,565)
    ※ 領域4は不要です。
    """
    cv2.rectangle(image, (425,150), (700,225), (255,255,255), thickness=-1)
    cv2.rectangle(image, (1260,150), (1535,225), (255,255,255), thickness=-1)
    cv2.rectangle(image, (0,240), (1611,565), (255,255,255), thickness=-1)
    return image

def parse_ocr_text(ocr_text):
    """
    OCR全体のテキストから、「VS」以前をヘッダーとして利用し、
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
    指定領域 (x1,y1,x2,y2) の部分画像からOCRを実施し、
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
    # 画像の前処理：中央部分抽出＆リサイズ
    preprocessed_img = preprocess_image(image_path)
    
    # ヘッダー抽出用にマスク済み画像を生成し保存
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
    
    # アイコン検出用ROI：指定された (35,115)〜(115,195)
    icon_roi = preprocessed_img[115:195, 35:115]
    cv2.imwrite("debug_icon_roi.jpg", icon_roi)
    print("Icon ROI saved as 'debug_icon_roi.jpg'.")
    
    # 剣アイコン判定用テンプレート画像の取得（attack_urlを使用）
    attack_url, defense_url = get_template_urls()
    attack_template = load_template(attack_url)
    
    # カラー画像同士でテンプレートマッチングを実施（閾値0.4）
    left_has_sword = match_icon(icon_roi, attack_template, thresh=0.4)
    print("Left has sword:", left_has_sword)
    
    # 剣検出結果に応じ、プレイヤー情報の割り当て
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
    
    # キャラクター領域抽出（左側および右側、下限680に合わせる）
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
    
    # 出力配置の調整：剣検出結果に応じ、攻撃側情報を左、防衛側情報を右に配置
    if left_has_sword:
        attack_chars = left_chars
        defense_chars = right_chars
    else:
        attack_chars = right_chars
        defense_chars = left_chars
    
    date_str = datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    # 攻撃側情報（9列分：日付、攻撃側プレイヤー、勝敗、6キャラ）＋空白1列を挟み、次に防衛側情報
    # これにより、防衛側情報がK列（11列目）から始まります。
    row_data = (
        [date_str, attack_side_player, attack_side_result] +
        attack_chars +
        [""] +  # ここで空白1列を挿入
        [defense_side_player, defense_side_result] +
        defense_chars
    )
    
    update_spreadsheet(row_data)
    return row_data

def main():
    uploads_dir = os.path.abspath("uploads")
    image_path = os.path.join(uploads_dir, "battle4.png")
    row_data = process_image(image_path)
    print("スプレッドシートを更新しました:", row_data)

　　# ここでしらす式変換を即時実行
    subprocess.run(["python", "call_gas.py"])

if __name__ == "__main__":
    main()
