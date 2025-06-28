#!/usr/bin/env python3
"""教師配置データを修正して5組専任教師を設定"""

import csv
import os


def fix_teacher_mapping():
    """教師配置を修正"""
    print("=== 教師配置データの修正 ===\n")
    
    input_path = "data/config/teacher_subject_mapping.csv"
    output_path = "data/config/teacher_subject_mapping.csv"
    
    # CSVを読み込む
    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    
    print("修正内容：")
    
    # 1. 寺田先生の5組国語を削除（金子み先生に置き換えるため）
    new_rows = []
    removed_count = 0
    for row in rows:
        if row[0] == "寺田" and row[1] == "国" and row[3] == "5":
            print(f"  削除: {','.join(row)}")
            removed_count += 1
        else:
            new_rows.append(row)
    
    # 2. 金子み先生の5組国語を追加
    added_rows = [
        ["金子み", "国", "1", "5"],
        ["金子み", "国", "2", "5"],
        ["金子み", "国", "3", "5"]
    ]
    
    for row in added_rows:
        new_rows.append(row)
        print(f"  追加: {','.join(row)}")
    
    # 3. ソート（読みやすさのため）
    new_rows.sort(key=lambda x: (x[1], int(x[2]), int(x[3]), x[0]))  # 教科、学年、組、教員名でソート
    
    # ファイルに書き込む
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(new_rows)
    
    print(f"\n修正完了！")
    print(f"  削除: {removed_count}件")
    print(f"  追加: {len(added_rows)}件")
    
    # 変更の検証
    print("\n変更後の5組担当教師:")
    with open(output_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        grade5_teachers = {}
        for row in reader:
            if row['組'] == '5':
                key = f"{row['学年']}-5 {row['教科']}"
                grade5_teachers[key] = row['教員名']
    
    for key in sorted(grade5_teachers.keys()):
        print(f"  {key}: {grade5_teachers[key]}")
    
    print("\n注意事項:")
    print("  - 5組の国語を寺田先生から金子み先生に変更しました")
    print("  - 数学（梶永先生）と理科（智田先生）は現状のままです")
    print("  - 必要に応じて、これらも別の専任教師に変更することを検討してください")
    print("\n次のステップ:")
    print("  python3 main.py generate")


if __name__ == "__main__":
    fix_teacher_mapping()