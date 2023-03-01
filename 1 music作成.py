import os
import csv
from pykakasi import kakasi

# ファイル名から拡張子を取り除く関数
def remove_extension(filename):
    return os.path.splitext(filename)[0]

# pykakasiによるローマ字変換
def to_romaji(text):
    kakasi_obj = kakasi()
    kakasi_obj.setMode('H', 'a')
    kakasi_obj.setMode('K', 'a')
    kakasi_obj.setMode('J', 'a')
    conv = kakasi_obj.getConverter()
    return conv.do(text)

# ファイル名を取得
dir_path = 'D:\自作mod\自動音楽MOD作成\music'#絶対パスでも相対パスでも
files = os.listdir(dir_path)

# ファイル名を変換してexchange.csvに書き込み
with open('exchange.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    for file in files:
        # 拡張子を取り除く
        filename = remove_extension(file)
        # ローマ字に変換する
        romaji = to_romaji(filename)
        # 全角文字を半角に、英数字と"_"以外の文字を削除する
        romaji = romaji.translate(str.maketrans({chr(0xFF01 + i): chr(0x21 + i) for i in range(94)}))
        romaji = ''.join(c for c in romaji if c.isalnum() or c == '_')
        # 変換前と変換後を","で区切ってexchange.csvに書き込む
        writer.writerow([file, romaji + ".ogg"])