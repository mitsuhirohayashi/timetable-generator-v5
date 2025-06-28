#!/usr/bin/env python3
"""
残りの空きスロットを埋める
"""

import csv
import sys
from pathlib import Path
from collections import defaultdict

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

def fill_empty_slots():
    """空きスロットを埋める"""
    
    # CSVファイルを読み込む
    input_path = project_root / 'data' / 'output' / 'output.csv'
    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # 標準時数（簡易版）
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
    
    fixed_count = 0
    
    # 各クラスの空きスロットを埋める
    for row_idx, row in enumerate(rows):
        if not row or not row[0] or row_idx < 2:  # ヘッダーをスキップ
            continue
        
        class_name = row[0]
        
        # 現在の時数をカウント
        current_hours = defaultdict(int)
        for col_idx in range(1, 31):
            if col_idx < len(row) and row[col_idx].strip():
                subj = row[col_idx].strip()
                if subj in base_hours:
                    current_hours[subj] += 1
        
        # 空きスロットを見つけて埋める
        for col_idx in range(1, 31):
            if col_idx < len(row) and not row[col_idx].strip():
                # その日の既存科目を確認
                day_idx = (col_idx - 1) // 6
                day_subjects = set()
                for period in range(6):
                    check_idx = day_idx * 6 + period + 1
                    if check_idx < len(row) and row[check_idx].strip():
                        day_subjects.add(row[check_idx].strip())
                
                # 不足している科目を優先順位付け
                candidates = []
                for subj, base in base_hours.items():
                    current = current_hours.get(subj, 0)
                    # その日にまだ配置されていない科目のみ
                    if subj not in day_subjects and current < base * 1.2:  # 標準の1.2倍まで許容
                        priority = base - current  # 不足が多いほど優先
                        candidates.append((priority, subj))
                
                # 優先度順にソート
                candidates.sort(reverse=True)
                
                if candidates:
                    # 最も優先度の高い科目を配置
                    _, selected_subject = candidates[0]
                    row[col_idx] = selected_subject
                    current_hours[selected_subject] += 1
                    
                    day = ['月', '火', '水', '木', '金'][(col_idx-1)//6]
                    period = ((col_idx-1) % 6) + 1
                    print(f"配置: {class_name} {day}曜{period}限 → {selected_subject}")
                    fixed_count += 1
    
    # ファイルに書き出す
    output_path = project_root / 'data' / 'output' / 'output_filled.csv'
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    
    print(f"\n合計 {fixed_count} 個の空きスロットを埋めました")
    print(f"結果を {output_path} に保存しました")
    
    # 元のファイルを置き換える
    import shutil
    shutil.copy(output_path, input_path)
    print(f"元のファイル {input_path} を更新しました")

if __name__ == '__main__':
    fill_empty_slots()