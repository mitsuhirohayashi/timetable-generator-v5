"""3年生の空きスロットを最終的に埋めるスクリプト"""
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict

def fill_3rd_final():
    """3年生の空きスロットを埋める（簡略版）"""
    # ファイルパス
    input_path = Path("data/output/output_fixed.csv")
    output_path = Path("data/output/output_final.csv")
    
    # CSVを読み込み
    df = pd.read_csv(input_path, header=None)
    
    # 3年3組と3年6組の空きスロットを特定
    targets = [
        (17, "3年3組", ["月", "6"], "数"),  # 月曜6限に数学
        (17, "3年3組", ["火", "6"], "理"),  # 火曜6限に理科
        (19, "3年6組", ["木", "5"], "社"),  # 木曜5限に社会
        (19, "3年6組", ["金", "5"], "保"),  # 金曜5限に保健体育
    ]
    
    filled_count = 0
    
    for row_idx, class_name, time_info, subject in targets:
        # 該当する列を探す
        col_idx = None
        for col in range(1, len(df.columns)):
            if df.iloc[0, col] == time_info[0] and df.iloc[1, col] == time_info[1]:
                col_idx = col
                break
        
        if col_idx is not None:
            current_val = df.iloc[row_idx, col_idx]
            if pd.isna(current_val) or current_val == '':
                df.iloc[row_idx, col_idx] = subject
                print(f"配置: {class_name} {time_info[0]}{time_info[1]}限 → {subject}")
                filled_count += 1
            else:
                print(f"スキップ: {class_name} {time_info[0]}{time_info[1]}限 (既に{current_val})")
    
    # 保存
    df.to_csv(output_path, index=False, header=False)
    print(f"\n修正完了: {filled_count}箇所")
    print(f"出力ファイル: {output_path}")
    
    return filled_count

if __name__ == "__main__":
    fill_3rd_final()