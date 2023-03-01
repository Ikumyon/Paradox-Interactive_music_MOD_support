import csv

# exchange.csvから変換リストを読み込む
with open('exchange.csv', mode='r', encoding='utf-8') as f:
    reader = csv.reader(f)
    exchange_list = list(reader)

# 変換リストを'honyaku.txt'に書き込む
with open('honyaku.txt', mode='w', encoding='utf-8') as f:
    for exchange_pair in exchange_list:
        f.write(f" {exchange_pair[1]}: \"{exchange_pair[0]}\"\n")
