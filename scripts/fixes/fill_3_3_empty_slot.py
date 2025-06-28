#!/usr/bin/env python3
"""3年3組の水曜6校時の空白を埋める簡易スクリプト"""

import pandas as pd
from pathlib import Path

# ファイルパス
output_path = Path("data/output/output.csv")
backup_path = Path("data/output/output_backup.csv")

# バックアップ作成
df = pd.read_csv(output_path, header=None)
df.to_csv(backup_path, index=False, header=False)

# 3-3の行番号を特定（0-indexed）
row_3_3 = None
for i, row in df.iterrows():
    if str(row[0]) == "3年3組":
        row_3_3 = i
        break

if row_3_3 is None:
    print("3年3組が見つかりません")
    exit(1)

# 水曜6校時の列番号を特定（0-indexed）
# 列0: クラス名
# 列1-6: 月曜1-6校時
# 列7-12: 火曜1-6校時  
# 列13-18: 水曜1-6校時
# 水曜6校時 = 列18
col_wed_6 = 18

# 現在の値を確認
current_value = df.iloc[row_3_3, col_wed_6]
print(f"3-3の水曜6校時の現在の値: '{current_value}'")

# 空白の場合は「家」を配置（時間数が不足している科目）
if pd.isna(current_value) or str(current_value).strip() == "":
    # 3-3の時間割を確認
    subjects_count = {}
    for col in range(1, 31):  # 1-30列（月1〜金6）
        val = df.iloc[row_3_3, col]
        if pd.notna(val) and str(val).strip() != "":
            subj = str(val).strip()
            subjects_count[subj] = subjects_count.get(subj, 0) + 1
    
    print("\n現在の科目配置:")
    for subj, count in sorted(subjects_count.items()):
        print(f"  {subj}: {count}時間")
    
    # 家庭科が不足しているので配置
    df.iloc[row_3_3, col_wed_6] = "家"
    print(f"\n✅ 3-3の水曜6校時に「家」を配置しました")
    
    # 保存
    df.to_csv(output_path, index=False, header=False)
    print(f"✅ {output_path}を更新しました")
else:
    print(f"既に'{current_value}'が配置されています")