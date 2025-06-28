#!/usr/bin/env python3
"""最終的な包括修正 - 配置禁止違反と日内重複を修正"""

import csv
from typing import List, Dict, Tuple, Set
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))

def read_csv(filepath: str) -> List[List[str]]:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        return list(csv.reader(f))

def write_csv(filepath: str, data: List[List[str]]):
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)

def get_time_slot_info(col_idx: int) -> Tuple[str, int]:
    """列番号から曜日と時限を取得"""
    days = ['月', '火', '水', '木', '金']
    day_idx = (col_idx - 1) // 6
    period = ((col_idx - 1) % 6) + 1
    if day_idx < len(days):
        return days[day_idx], period
    return None, None

def check_daily_duplicate_in_day(row: List[str], target_col_idx: int, subject: str) -> bool:
    """指定した日に特定の科目が既にあるかチェック"""
    target_day, _ = get_time_slot_info(target_col_idx)
    if not target_day:
        return False
    
    day_idx = (target_col_idx - 1) // 6
    
    for period in range(1, 7):
        check_col_idx = day_idx * 6 + period
        if check_col_idx != target_col_idx and check_col_idx < len(row):
            if row[check_col_idx].strip() == subject:
                return True
    
    return False

def get_forbidden_subjects() -> Dict[Tuple[str, int], str]:
    """input.csvから配置禁止情報を取得"""
    forbidden = {}
    input_data = read_csv('data/input/input.csv')
    
    for row_idx in range(2, len(input_data)):
        if row_idx >= len(input_data):
            continue
        row = input_data[row_idx]
        if not row or not row[0]:
            continue
        
        class_name = row[0].strip()
        
        for col_idx in range(1, min(31, len(row))):
            value = row[col_idx].strip() if col_idx < len(row) else ''
            if value.startswith('非'):
                forbidden_subject = value[1:]  # 非保 -> 保
                forbidden[(class_name, col_idx)] = forbidden_subject
    
    return forbidden

def main():
    # データ読み込み
    output_data = read_csv('data/output/output.csv')
    forbidden_subjects = get_forbidden_subjects()
    
    print('=== 最終的な包括修正 ===\n')
    
    # バックアップ作成
    import shutil
    shutil.copy('data/output/output.csv', 'data/output/output_before_final_comprehensive_fix.csv')
    print('✅ バックアップを作成しました: output_before_final_comprehensive_fix.csv\n')
    
    # 1. 配置禁止違反の修正（2年1組 金曜6限の数学）
    print('【1. 配置禁止違反の修正】')
    for row_idx in range(2, len(output_data)):
        row = output_data[row_idx]
        if row and row[0] and row[0].strip() == '2年1組':
            # 金曜6限は列30
            col_idx = 30
            current_subject = row[col_idx].strip() if col_idx < len(row) else ''
            
            if (row[0].strip(), col_idx) in forbidden_subjects:
                forbidden = forbidden_subjects[(row[0].strip(), col_idx)]
                if current_subject == forbidden:
                    print(f'❌ 配置禁止違反発見: 2年1組 金曜6限に「{forbidden}」（非{forbidden}指定）')
                    
                    # 他の科目と交換
                    for search_col_idx in range(1, min(31, len(row))):
                        if search_col_idx != col_idx:
                            alt_subject = row[search_col_idx].strip()
                            # 数学以外の通常教科を探す
                            if alt_subject and alt_subject not in ['', '数', 'YT', '道', '欠'] and \
                               not check_daily_duplicate_in_day(row, col_idx, alt_subject):
                                # 交換
                                row[col_idx], row[search_col_idx] = row[search_col_idx], row[col_idx]
                                search_day, search_period = get_time_slot_info(search_col_idx)
                                print(f'✅ 修正: 金曜6限の「数」と{search_day}曜{search_period}限の「{alt_subject}」を交換')
                                break
                    else:
                        # 交換できない場合は他の科目に変更
                        for alt_subject in ['国', '英', '理', '社', '音', '美', '保', '技', '家']:
                            if alt_subject != forbidden and not check_daily_duplicate_in_day(row, col_idx, alt_subject):
                                row[col_idx] = alt_subject
                                print(f'✅ 修正: 金曜6限を「{alt_subject}」に変更')
                                break
            break
    
    print()
    
    # 2. 残りの日内重複修正（5組と3年2組）
    print('【2. 日内重複の修正】')
    
    # 5組の月曜英語重複を修正（構造的な問題なので別アプローチ）
    grade5_classes = ['1年5組', '2年5組', '3年5組']
    for class_name in grade5_classes:
        for row_idx in range(2, len(output_data)):
            row = output_data[row_idx]
            if row and row[0] and row[0].strip() == class_name:
                # 月曜日の英語をチェック
                monday_english_slots = []
                for period in range(1, 7):
                    col_idx = period  # 月曜日は列1-6
                    if col_idx < len(row) and row[col_idx].strip() == '英':
                        monday_english_slots.append(col_idx)
                
                # 重複があれば2つ目を別の科目に変更
                if len(monday_english_slots) >= 2:
                    second_slot = monday_english_slots[1]
                    # 5組で使える代替科目
                    for alt_subject in ['国', '数', '理', '社']:
                        if not check_daily_duplicate_in_day(row, second_slot, alt_subject):
                            row[second_slot] = alt_subject
                            print(f'✅ {class_name}: 月曜{second_slot}限の「英」を「{alt_subject}」に変更')
                            break
                break
    
    # 3年2組の月曜英語重複を修正
    for row_idx in range(2, len(output_data)):
        row = output_data[row_idx]
        if row and row[0] and row[0].strip() == '3年2組':
            # 月曜日の英語をチェック
            monday_english_slots = []
            for period in range(1, 7):
                col_idx = period  # 月曜日は列1-6
                if col_idx < len(row) and row[col_idx].strip() == '英':
                    monday_english_slots.append(col_idx)
            
            # 重複があれば修正（交換を試みる）
            if len(monday_english_slots) >= 2:
                second_slot = monday_english_slots[1]
                # 他の日の授業と交換
                for search_day_idx in range(1, 5):  # 火〜金
                    for search_period in range(1, 7):
                        search_col_idx = search_day_idx * 6 + search_period
                        if search_col_idx < len(row):
                            alt_subject = row[search_col_idx].strip()
                            if alt_subject and alt_subject not in ['', '英', 'YT', '道', '欠'] and \
                               not check_daily_duplicate_in_day(row, second_slot, alt_subject) and \
                               not check_daily_duplicate_in_day(row, search_col_idx, '英'):
                                # 交換
                                row[second_slot], row[search_col_idx] = row[search_col_idx], row[second_slot]
                                search_day, _ = get_time_slot_info(search_col_idx)
                                print(f'✅ 3年2組: 月曜{second_slot}限の「英」と{search_day}曜の「{alt_subject}」を交換')
                                break
                    else:
                        continue
                    break
            break
    
    # 修正後のデータを保存
    write_csv('data/output/output.csv', output_data)
    print('\n✅ 修正後のデータを保存しました: output.csv\n')
    
    print('修正完了！ 最終確認をしてください。')

if __name__ == "__main__":
    main()