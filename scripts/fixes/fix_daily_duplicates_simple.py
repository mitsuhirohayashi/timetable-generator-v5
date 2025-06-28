#!/usr/bin/env python3
"""
日内重複を修正する
"""

import csv
import sys
from pathlib import Path
from collections import defaultdict

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

def fix_daily_duplicates():
    """日内重複を修正"""
    
    # CSVファイルを読み込む
    input_path = project_root / 'data' / 'output' / 'output.csv'
    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # 標準時数を読み込む（簡易版 - 主要教科のみ）
    base_hours = {
        '国': 4.0,
        '社': 3.0,
        '数': 4.0,
        '理': 3.0,
        '音': 1.3,
        '美': 1.3,
        '保': 3.0,
        '技': 1.0,
        '家': 1.0,
        '英': 4.0
    }
    
    # 修正する重複
    duplicates = [
        ('1年7組', '木', '国'),
        ('2年1組', '月', '国'),
        ('2年7組', '月', '保'),
        ('3年3組', '月', '英')
    ]
    
    # クラスごとの行を見つける
    class_rows = {}
    for idx, row in enumerate(rows):
        if row and row[0]:
            class_rows[row[0]] = idx
    
    fixed_count = 0
    
    for class_name, day_name, subject in duplicates:
        if class_name not in class_rows:
            continue
        
        row_idx = class_rows[class_name]
        row = rows[row_idx]
        
        # 曜日のインデックス
        day_idx = {'月': 0, '火': 1, '水': 2, '木': 3, '金': 4}[day_name]
        
        # その曜日の科目を取得
        day_subjects = []
        for period in range(6):
            col_idx = day_idx * 6 + period + 1
            if col_idx < len(row):
                day_subjects.append((col_idx, row[col_idx].strip()))
        
        # 重複している科目を見つける
        subject_positions = [(idx, subj) for idx, subj in day_subjects if subj == subject]
        
        if len(subject_positions) >= 2:
            # 2つ目の重複を別の科目に変更
            change_idx, _ = subject_positions[1]
            
            # 現在の時数をカウント
            current_hours = defaultdict(int)
            for col_idx in range(1, 31):
                if col_idx < len(row) and row[col_idx].strip():
                    subj = row[col_idx].strip()
                    if subj not in ['YT', '道', '総', '学', '学総', '行', '欠', '自立', '日生', '作業', '生単']:
                        current_hours[subj] += 1
            
            # 不足している科目を見つける
            needed_subjects = []
            for subj, base in base_hours.items():
                if subj in ['国', '社', '数', '理', '音', '美', '保', '技', '家', '英']:
                    current = current_hours.get(subj, 0)
                    if current < base:
                        needed_subjects.append((subj, base - current))
            
            # 優先度順にソート（不足が多い順）
            needed_subjects.sort(key=lambda x: x[1], reverse=True)
            
            # 交換する科目を選ぶ
            replacement = None
            if needed_subjects:
                replacement = needed_subjects[0][0]
            else:
                # 不足がない場合は、現在少ない科目を選ぶ
                min_subject = min(base_hours.keys(), key=lambda x: current_hours.get(x, 0))
                replacement = min_subject
            
            # 変更を適用
            row[change_idx] = replacement
            period = ((change_idx - 1) % 6) + 1
            print(f"修正: {class_name} {day_name}曜{period}限 {subject} → {replacement}")
            fixed_count += 1
    
    # ファイルに書き出す
    output_path = project_root / 'data' / 'output' / 'output_duplicate_fixed.csv'
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    
    print(f"\n合計 {fixed_count} 個の日内重複を修正しました")
    print(f"結果を {output_path} に保存しました")
    
    # 元のファイルを置き換える
    import shutil
    shutil.copy(output_path, input_path)
    print(f"元のファイル {input_path} を更新しました")

if __name__ == '__main__':
    fix_daily_duplicates()