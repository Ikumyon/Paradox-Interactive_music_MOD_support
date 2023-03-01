import os
import csv

# フォルダパスを指定する
folder_path = "D:\自作mod\自動音楽MOD作成\music"

# 変換リストを読み込む
with open("exchange.csv", mode="r", encoding="utf-8") as f:
    reader = csv.reader(f)
    exchange_list = list(reader)

# フォルダ内のファイルをループで処理する
for filename in os.listdir(folder_path):
    # 変換リストに基づいてファイル名を変換する
    for exchange_pair in exchange_list:
        if filename == exchange_pair[0]:
            os.rename(
                os.path.join(folder_path, filename),
                os.path.join(folder_path, exchange_pair[1])
            )
            break
