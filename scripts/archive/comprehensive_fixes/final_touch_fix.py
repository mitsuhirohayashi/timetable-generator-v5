#!/usr/bin/env python3
"""最後の仕上げ - 残りの日内重複を修正"""

import pandas as pd
from pathlib import Path

def final_touch():
    # ファイル読み込み
    input_path = Path(__file__).parent / "data" / "output" / "output_ultra_fixed.csv"
    output_path = Path(__file__).parent / "data" / "output" / "output_final_complete.csv"
    
    df = pd.read_csv(input_path, header=None)
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    print("=== 最後の仕上げ ===\n")
    
    def get_cell(day, period):
        for i, (d, p) in enumerate(zip(days, periods)):
            if d == day and str(p) == str(period):
                return i + 1
        return None
    
    def get_class_row(class_name):
        for i in range(2, len(df)):
            if df.iloc[i, 0] == class_name:
                return i
        return None
    
    # 2年2組の木曜の英語重複を修正
    print("【2年2組の木曜日英語重複を修正】")
    class_row = get_class_row("2年2組")
    
    if class_row:
        # 木曜5限の英を別の場所へ
        thu5_col = get_cell("木", "5")
        
        # 金曜3限と交換（金曜3限は国）
        fri3_col = get_cell("金", "3")
        
        if thu5_col and fri3_col:
            thu5_subj = df.iloc[class_row, thu5_col]
            fri3_subj = df.iloc[class_row, fri3_col]
            
            df.iloc[class_row, thu5_col] = fri3_subj
            df.iloc[class_row, fri3_col] = thu5_subj
            
            print(f"  ✓ 木曜5限(英) ⇔ 金曜3限(国)")
    
    # 最終検証
    print("\n【最終検証】")
    print("2年2組の木曜日:")
    thu_subjects = []
    for period in range(1, 7):
        col = get_cell("木", str(period))
        if col:
            subject = df.iloc[class_row, col]
            if pd.notna(subject):
                thu_subjects.append(f"{period}限:{subject}")
    print(f"  {', '.join(thu_subjects)}")
    
    # 保存
    df.to_csv(output_path, index=False, header=False)
    print(f"\n完成！: {output_path}")

if __name__ == "__main__":
    final_touch()