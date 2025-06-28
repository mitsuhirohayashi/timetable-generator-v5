#!/usr/bin/env python3
"""手動で空きスロットを埋めるスクリプト"""

import csv
import logging
from pathlib import Path
from collections import defaultdict

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def read_csv(file_path):
    """CSVファイルを読み込む"""
    rows = []
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)
    return rows

def write_csv(file_path, rows):
    """CSVファイルに書き込む"""
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)

def analyze_empty_slots(rows):
    """空きスロットを分析"""
    empty_slots = []
    days = ['月', '火', '水', '木', '金']
    
    # ヘッダー行をスキップ
    for row_idx, row in enumerate(rows[2:], 2):
        if not row or not row[0]:  # 空行をスキップ
            continue
        class_name = row[0]
        for col_idx, cell in enumerate(row[1:], 1):
            if cell == '':
                day_index = (col_idx-1) // 6
                period = ((col_idx-1) % 6) + 1
                day = days[day_index]
                empty_slots.append({
                    'row': row_idx,
                    'col': col_idx,
                    'class': class_name,
                    'day': day,
                    'period': period
                })
    
    return empty_slots

def count_subject_hours(rows, class_name):
    """各クラスの科目別時数をカウント"""
    hours = defaultdict(int)
    
    # クラスの行を探す
    class_row = None
    for row in rows[2:]:
        if row and row[0] == class_name:
            class_row = row
            break
    
    if not class_row:
        return hours
    
    # 科目をカウント
    for cell in class_row[1:]:
        if cell and cell != '':
            hours[cell] += 1
    
    return hours

def get_standard_hours(class_name):
    """標準時数を取得（簡易版）"""
    # 学年を判定
    grade = int(class_name[0])
    class_num = int(class_name[2])
    
    # 5組は特別
    if class_num == 5:
        return {
            '国': 4, '社': 1, '数': 4, '理': 3,
            '音': 1, '美': 1, '保': 2, '技': 1,
            '家': 1, '英': 2, '道': 1
        }
    
    # 通常学級
    if grade == 1:
        return {
            '国': 4, '社': 3, '数': 4, '理': 3,
            '音': 1, '美': 1, '保': 3, '技': 1,
            '家': 1, '英': 4, '道': 1
        }
    elif grade == 2:
        return {
            '国': 4, '社': 3, '数': 3, '理': 4,
            '音': 1, '美': 1, '保': 3, '英': 4,
            '道': 1
        }
    else:  # 3年
        return {
            '国': 3, '社': 4, '数': 4, '理': 4,
            '音': 1, '美': 1, '保': 3, '英': 4,
            '道': 1
        }

def suggest_subject(class_name, current_hours, day, period):
    """埋めるべき科目を提案"""
    standard = get_standard_hours(class_name)
    
    # 不足している科目をリストアップ
    shortage = {}
    for subject, required in standard.items():
        current = current_hours.get(subject, 0)
        if current < required:
            shortage[subject] = required - current
    
    if not shortage:
        # 全て満たしている場合は、主要5教科を追加
        major_subjects = ['国', '数', '英', '理', '社']
        for subj in major_subjects:
            if subj in standard:
                return subj
        return None
    
    # 不足が多い順にソート
    sorted_shortage = sorted(shortage.items(), key=lambda x: x[1], reverse=True)
    
    # 最も不足している科目を返す
    return sorted_shortage[0][0]

def fill_empty_slots(input_file, output_file):
    """空きスロットを埋める"""
    # CSVを読み込む
    rows = read_csv(input_file)
    
    # 空きスロットを分析
    empty_slots = analyze_empty_slots(rows)
    logger.info(f"空きスロット数: {len(empty_slots)}")
    
    # 各空きスロットを埋める
    filled_count = 0
    for slot in empty_slots:
        class_name = slot['class']
        
        # 現在の時数をカウント
        current_hours = count_subject_hours(rows, class_name)
        
        # 埋めるべき科目を提案
        subject = suggest_subject(class_name, current_hours, slot['day'], slot['period'])
        
        if subject:
            # CSVに書き込む
            rows[slot['row']][slot['col']] = subject
            filled_count += 1
            logger.info(f"{class_name} {slot['day']}曜{slot['period']}限 → {subject}")
    
    # 結果を保存
    write_csv(output_file, rows)
    logger.info(f"埋めたスロット数: {filled_count}/{len(empty_slots)}")
    
    return filled_count, len(empty_slots)

def main():
    """メイン処理"""
    input_file = Path('data/output/output.csv')
    output_file = Path('data/output/output_filled.csv')
    
    if not input_file.exists():
        logger.error(f"入力ファイルが見つかりません: {input_file}")
        return
    
    logger.info("=== 手動空きスロット埋め処理開始 ===")
    
    filled, total = fill_empty_slots(input_file, output_file)
    
    logger.info(f"\n処理完了:")
    logger.info(f"- 総空きスロット数: {total}")
    logger.info(f"- 埋めたスロット数: {filled}")
    logger.info(f"- 出力ファイル: {output_file}")
    
    # output.csvにコピー
    if filled > 0:
        import shutil
        shutil.copy2(output_file, input_file)
        logger.info(f"output.csvを更新しました")

if __name__ == "__main__":
    main()