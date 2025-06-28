#!/usr/bin/env python3
"""3年3組の水曜6限の空白を埋める簡易修正スクリプト"""

import pandas as pd
from pathlib import Path

def fill_empty_slot():
    """3-3の水曜6限を埋める"""
    
    # CSVファイルを読み込み
    input_path = Path("/Users/hayashimitsuhiro/Desktop/timetable_v5/data/output/output.csv")
    df = pd.read_csv(input_path, header=None)
    
    # 3-3の行を特定（18行目、インデックスは17）
    class_3_3_row = 17
    
    # 水曜6限の列を特定（19列目、インデックスは18）
    wed_6th_col = 18
    
    # 現在の値を確認
    current_value = df.iloc[class_3_3_row, wed_6th_col]
    print(f"現在の3-3水曜6限: '{current_value}'")
    
    if pd.isna(current_value) or str(current_value).strip() == "":
        # 3-3の他の授業を確認して不足している科目を特定
        row_data = df.iloc[class_3_3_row, 1:31]  # 授業データのみ
        subjects_count = {}
        
        for val in row_data:
            if pd.notna(val) and str(val).strip() != "":
                subject = str(val).strip()
                subjects_count[subject] = subjects_count.get(subject, 0) + 1
        
        print(f"3-3の科目カウント: {subjects_count}")
        
        # 家庭科が少ないので配置
        df.iloc[class_3_3_row, wed_6th_col] = "家"
        print("3-3の水曜6限に「家」を配置しました")
        
        # ファイルを保存
        df.to_csv(input_path, index=False, header=False)
        print(f"修正済みファイルを保存しました: {input_path}")
        
        return True
    else:
        print("3-3の水曜6限は既に埋まっています")
        return False

if __name__ == "__main__":
    success = fill_empty_slot()
    if success:
        print("\n修正が完了しました。Excelで確認してください。")