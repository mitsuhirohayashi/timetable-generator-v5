#!/usr/bin/env python3
"""
日内重複違反を修正するスクリプト
Daily duplicate violations fixer
"""

import csv
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Set

def read_timetable(filepath: str) -> Dict[str, Dict[str, str]]:
    """CSVファイルから時間割を読み込む"""
    timetable = {}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)  # ヘッダー行
        time_slots = next(reader)  # 時限行
        
        # デバッグ: ヘッダーを表示
        # print(f"Headers: {headers}")
        # print(f"Time slots: {time_slots}")
        
        for row in reader:
            if not row or not row[0]:  # 空行をスキップ
                continue
            
            class_name = row[0]
            timetable[class_name] = {}
            
            for i in range(1, len(row)):
                if i < len(headers) and i < len(time_slots):
                    # 月.1, 月.2 などの形式を月_2, 月_3に変換
                    day = headers[i].split('.')[0] if '.' in headers[i] else headers[i]
                    period = time_slots[i]
                    slot_key = f"{day}_{period}"
                    timetable[class_name][slot_key] = row[i] if i < len(row) else ''
    
    return timetable

def find_daily_duplicates(timetable: Dict[str, Dict[str, str]]) -> Dict[str, List[Tuple[str, str, List[str]]]]:
    """各クラスの日内重複を検出"""
    duplicates = defaultdict(list)
    
    days = ['月', '火', '水', '木', '金']
    
    for class_name, schedule in timetable.items():
        for day in days:
            # その日の科目をカウント
            day_subjects = []
            
            for period in ['1', '2', '3', '4', '5', '6']:
                slot_key = f"{day}_{period}"
                if slot_key in schedule:
                    subject = schedule[slot_key]
                    if subject and subject not in ['', '欠', 'YT', '学', '道', '総', '学総', '行']:
                        day_subjects.append((period, subject))
            
            # 重複を検出
            subject_positions = defaultdict(list)
            for period, subject in day_subjects:
                subject_positions[subject].append(period)
            
            for subject, positions in subject_positions.items():
                if len(positions) > 1:
                    duplicates[class_name].append((day, subject, positions))
    
    return duplicates

def load_base_timetable(filepath: str = 'data/config/base_timetable.csv') -> Dict[str, Dict[str, int]]:
    """標準時数を読み込む"""
    base_hours = {}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)  # ヘッダー行をスキップ
            
            for row in reader:
                if not row or not row[0]:
                    continue
                
                class_name = row[0]
                base_hours[class_name] = {}
                
                # 科目名と時数のペアを読み込む
                for i in range(1, len(row), 2):
                    if i + 1 < len(row) and row[i]:
                        subject = row[i]
                        hours = int(row[i + 1]) if row[i + 1] else 0
                        base_hours[class_name][subject] = hours
    except:
        # ファイルが読めない場合はデフォルト値を使用
        pass
    
    return base_hours

def get_subject_hours(timetable: Dict[str, Dict[str, str]], class_name: str) -> Counter:
    """クラスの現在の科目時数を取得"""
    counter = Counter()
    
    schedule = timetable.get(class_name, {})
    for slot, subject in schedule.items():
        if subject and subject not in ['', '欠', 'YT', '学', '道', '総', '学総', '行', '自立', '日生', '作業']:
            counter[subject] += 1
    
    return counter

def find_replacement_subject(timetable: Dict[str, Dict[str, str]], base_hours: Dict[str, Dict[str, int]], 
                           class_name: str, day: str, period: str, exclude_subjects: Set[str]) -> str:
    """代替科目を探す"""
    current_hours = get_subject_hours(timetable, class_name)
    standard_hours = base_hours.get(class_name, {})
    
    # その日の科目を収集（重複チェック用）
    day_subjects = set()
    for p in ['1', '2', '3', '4', '5', '6']:
        slot_key = f"{day}_{p}"
        if slot_key in timetable.get(class_name, {}):
            subject = timetable[class_name][slot_key]
            if subject:
                day_subjects.add(subject)
    
    # 主要5教科を優先
    priority_subjects = ['国', '数', '英', '理', '社']
    other_subjects = ['音', '美', '保', '技', '家']
    
    # 時数が不足している科目を探す
    candidates = []
    
    # デフォルトの標準時数（base_timetable.csvが読めない場合）
    default_hours = {
        '国': 4, '数': 3, '英': 4, '理': 3, '社': 3,
        '音': 1, '美': 1, '保': 3, '技': 2, '家': 1
    }
    
    for subjects, priority in [(priority_subjects, 1), (other_subjects, 2)]:
        for subject in subjects:
            if subject in exclude_subjects or subject in day_subjects:
                continue
            
            current = current_hours.get(subject, 0)
            standard = standard_hours.get(subject, default_hours.get(subject, 2))
            
            if current < standard:
                shortage = standard - current
                candidates.append((priority, shortage, subject))
    
    # 優先度と不足時数でソート
    candidates.sort(key=lambda x: (x[0], -x[1]))
    
    if candidates:
        return candidates[0][2]
    
    # 不足がない場合は、その日にまだ配置されていない科目を選ぶ
    for subject in priority_subjects + other_subjects:
        if subject not in exclude_subjects and subject not in day_subjects:
            return subject
    
    return '自習'  # どうしても見つからない場合

def write_timetable(timetable: Dict[str, Dict[str, str]], filepath: str, original_filepath: str):
    """時間割をCSVファイルに書き出す"""
    # 元のファイルの構造を保持するため、元ファイルを読み込んで構造を取得
    with open(original_filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        time_slots = next(reader)
        class_order = []
        for row in reader:
            if row and row[0]:
                class_order.append(row[0])
    
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        
        # ヘッダーとtime slots
        writer.writerow(headers)
        writer.writerow(time_slots)
        
        # 各クラスのデータ
        for class_name in class_order:
            if class_name in timetable:
                row = [class_name]
                schedule = timetable[class_name]
                
                for i in range(1, len(headers)):
                    # 月.1, 月.2 などの形式を月_2, 月_3に変換
                    day = headers[i].split('.')[0] if '.' in headers[i] else headers[i]
                    period = time_slots[i]
                    slot_key = f"{day}_{period}"
                    
                    subject = schedule.get(slot_key, '')
                    row.append(subject)
                
                writer.writerow(row)
            else:
                # 空行の場合
                writer.writerow([''] * len(headers))

def fix_duplicates(input_path: str, output_path: str):
    """日内重複を修正"""
    print("=== 日内重複違反の修正 ===\n")
    
    # データ読み込み
    timetable = read_timetable(input_path)
    base_hours = load_base_timetable()
    
    # 重複を検出
    duplicates = find_daily_duplicates(timetable)
    
    if not duplicates:
        print("日内重複違反は見つかりませんでした。")
        return
    
    # 重複を表示
    print("検出された日内重複:")
    total_duplicates = 0
    for class_name, class_duplicates in sorted(duplicates.items()):
        if class_duplicates:
            print(f"\n{class_name}:")
            for day, subject, positions in class_duplicates:
                print(f"  - {day}曜日: {subject} が {len(positions)} 回 (時限: {positions})")
                total_duplicates += len(positions) - 1
    
    print(f"\n合計重複数: {total_duplicates} 件")
    
    # 修正実行
    print("\n=== 修正開始 ===")
    modifications = []
    
    for class_name, class_duplicates in duplicates.items():
        for day, subject, positions in class_duplicates:
            # 最初の出現以外を置き換える
            for i, period in enumerate(positions[1:], 1):
                slot_key = f"{day}_{period}"
                
                # すでに置き換えた科目を除外
                exclude_subjects = {subject}
                for mod in modifications:
                    if mod['class'] == class_name and mod['day'] == day:
                        exclude_subjects.add(mod['new_subject'])
                
                # 代替科目を探す
                new_subject = find_replacement_subject(
                    timetable, base_hours, class_name, day, period, exclude_subjects
                )
                
                if new_subject:
                    # 科目を変更
                    timetable[class_name][slot_key] = new_subject
                    
                    modification = {
                        'class': class_name,
                        'day': day,
                        'period': period,
                        'old_subject': subject,
                        'new_subject': new_subject,
                        'slot': slot_key
                    }
                    modifications.append(modification)
                    
                    print(f"{class_name} {day}曜{period}限: {subject} → {new_subject}")
                else:
                    print(f"警告: {class_name} {day}曜{period}限の代替科目が見つかりません")
    
    # 修正後の重複を再チェック
    print("\n=== 修正後の検証 ===")
    new_duplicates = find_daily_duplicates(timetable)
    
    remaining_duplicates = 0
    for class_name, class_duplicates in new_duplicates.items():
        remaining_duplicates += sum(len(positions) - 1 for _, _, positions in class_duplicates)
    
    print(f"修正前の重複数: {total_duplicates} 件")
    print(f"修正後の重複数: {remaining_duplicates} 件")
    print(f"解決された重複: {total_duplicates - remaining_duplicates} 件")
    
    if remaining_duplicates > 0:
        print("\n残存する重複:")
        for class_name, class_duplicates in sorted(new_duplicates.items()):
            if class_duplicates:
                print(f"\n{class_name}:")
                for day, subject, positions in class_duplicates:
                    print(f"  - {day}曜日: {subject} が {len(positions)} 回 (時限: {positions})")
    
    # ファイルに保存
    write_timetable(timetable, output_path, input_path)
    print(f"\n修正済みファイルを保存しました: {output_path}")
    
    # 修正内容のサマリー
    print("\n=== 修正サマリー ===")
    print(f"修正された授業数: {len(modifications)}")
    
    # クラス別修正数
    class_mods = defaultdict(int)
    for mod in modifications:
        class_mods[mod['class']] += 1
    
    print("\nクラス別修正数:")
    for class_name, count in sorted(class_mods.items()):
        print(f"  {class_name}: {count} 件")

def main():
    input_path = 'data/output/output.csv'
    
    # バックアップを作成
    import shutil
    backup_path = 'data/output/output.csv.bak_daily_duplicates'
    shutil.copy(input_path, backup_path)
    print(f"バックアップを作成しました: {backup_path}")
    
    # 同じファイルに上書き保存
    output_path = input_path
    
    fix_duplicates(input_path, output_path)

if __name__ == '__main__':
    main()