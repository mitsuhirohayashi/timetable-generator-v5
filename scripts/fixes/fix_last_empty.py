"""最後の空きスロットを埋める"""
import pandas as pd
import numpy as np

# CSVを読み込み
df = pd.read_csv("data/output/output.csv", header=None)

# 3年6組の木曜5限を見つけて埋める
row_idx = 19  # 3年6組
col_idx = None

# 木曜5限の列を探す
for col in range(1, len(df.columns)):
    if df.iloc[0, col] == "木" and df.iloc[1, col] == "5":
        col_idx = col
        break

if col_idx:
    df.iloc[row_idx, col_idx] = "英"  # 英語を配置
    print(f"配置: 3年6組 木曜5限 → 英")
    
    # 保存
    df.to_csv("data/output/output.csv", index=False, header=False)
    print("保存完了")