#!/usr/bin/env python3
"""3年生の月曜・火曜・水曜6限を埋める簡易スクリプト"""

import pandas as pd
import os

def main():
    print("=== 3年生の月曜・火曜・水曜6限を埋める ===\n")
    
    # CSVファイルを読み込む（ヘッダーなしで読み込む）
    input_file = "data/output/output.csv"
    df = pd.read_csv(input_file, encoding='utf-8', header=None)
    
    # 列名を取得（曜日と時限の情報）
    columns = df.columns.tolist()
    
    # 3年生の担任教師マッピング
    homeroom_subjects = {
        "3年1組": "学活",  # 白石先生
        "3年2組": "総",    # 森山先生
        "3年3組": "学活",  # 北先生
        "3年5組": "日生",  # 金子み先生（5組は特別）
        "3年6組": "学活",  # 北先生（3年3組と同じ）
        "3年7組": "総"     # 森山先生（3年2組と同じ）
    }
    
    changes_made = []
    
    # 月曜・火曜・水曜の6限の列を探す
    days_periods = [("月", "6"), ("火", "6"), ("水", "6")]
    
    # ヘッダー行を取得
    header_row = df.iloc[0].tolist()  # 曜日
    period_row = df.iloc[1].tolist()  # 時限
    
    print("ヘッダー行（最初の10列）:", header_row[:10])
    print("時限行（最初の10列）:", period_row[:10])
    
    for day, period in days_periods:
        # 該当する列を探す
        col_idx = None
        for i in range(1, len(header_row)):
            if header_row[i] == day and period_row[i] == period:
                col_idx = i
                print(f"見つけた: {day}曜{period}限は列{i}")
                break
        
        if col_idx is None:
            print(f"見つからない: {day}曜{period}限")
            continue
            
        # 3年生のクラスを処理（データは3行目から開始）
        for idx in range(2, len(df)):
            class_name = df.iloc[idx, 0]
            if isinstance(class_name, str) and class_name.startswith("3年") and class_name in homeroom_subjects:
                current_value = df.iloc[idx, col_idx]
                print(f"デバッグ: {day}曜6限 {class_name} = '{current_value}' (type: {type(current_value)})")
                
                # 空白または欠損値の場合
                if pd.isna(current_value) or str(current_value).strip() == "":
                    # 適切な科目を割り当て
                    if day == "月":
                        subject = homeroom_subjects[class_name]
                    elif day == "火":
                        subject = "道"  # 火曜は道徳
                    else:  # 水曜
                        subject = "学総" if "3年5組" not in class_name else "自立"
                    
                    # 値を更新
                    df.iloc[idx, col_idx] = subject
                    changes_made.append(f"{day}曜6限 {class_name}: {subject}")
                    print(f"✓ {day}曜6限 {class_name}: {subject}を配置")
    
    # 月曜5限の社会の重複も確認して修正
    print("\n=== 月曜5限の教師重複を確認 ===")
    
    # 月曜5限の列を探す
    mon5_col = None
    for i in range(1, len(header_row)):
        if header_row[i] == "月" and period_row[i] == "5":
            mon5_col = i
            break
    
    if mon5_col:
        # 3年2組と3年3組の月曜5限を確認
        idx_3_2 = None
        idx_3_3 = None
        for idx in range(2, len(df)):
            class_name = df.iloc[idx, 0]
            if class_name == "3年2組":
                idx_3_2 = idx
            elif class_name == "3年3組":
                idx_3_3 = idx
        
        # 両方とも社会の場合、3年3組を変更
        if idx_3_2 is not None and idx_3_3 is not None and df.iloc[idx_3_2, mon5_col] == "社" and df.iloc[idx_3_3, mon5_col] == "社":
            print("月曜5限: 3年2組と3年3組が両方とも社会")
            # 3年3組を英語に変更
            df.iloc[idx_3_3, mon5_col] = "英"
            changes_made.append("月曜5限 3年3組: 社 → 英")
            print("✓ 月曜5限 3年3組: 社 → 英に変更")
    
    # 変更を保存
    if changes_made:
        print(f"\n=== 変更内容 ({len(changes_made)}件) ===")
        for change in changes_made:
            print(f"  • {change}")
        
        # 保存（インデックス列を含めない）
        df.to_csv(input_file, index=False, encoding='utf-8', header=False)
        print(f"\n✓ {input_file}に変更を保存しました")
    else:
        print("\n変更はありませんでした")

if __name__ == "__main__":
    main()