#!/usr/bin/env python3
"""空白スロットを通常教科で埋める（固定科目は使用しない）"""

import csv
import sys
from pathlib import Path
from collections import defaultdict, Counter

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.infrastructure.config.path_config import path_config


def get_subject_hours(schedule_data, class_name, class_row_idx):
    """クラスの現在の科目時数を取得"""
    counter = Counter()
    
    if class_row_idx >= len(schedule_data):
        return counter
        
    row = schedule_data[class_row_idx]
    
    for col_idx in range(1, len(row)):
        subject = row[col_idx] if col_idx < len(row) else ""
        if subject and subject not in ["", "欠", "YT", "学", "道", "総", "学総", "行", "自立", "日生", "作業", "生単"]:
            counter[subject] += 1
    
    return counter


def find_suitable_subject(schedule_data, class_name, class_row_idx, day_idx, period, 
                         fixed_subjects, special_subjects):
    """適切な通常教科を見つける"""
    
    # その日の科目を収集（重複チェック用）
    day_subjects = []
    for p in range(1, 7):
        col_idx = day_idx * 6 + p
        if col_idx < len(schedule_data[class_row_idx]):
            subject = schedule_data[class_row_idx][col_idx]
            if subject:
                day_subjects.append(subject)
    
    # 現在の時数を取得
    current_hours = get_subject_hours(schedule_data, class_name, class_row_idx)
    
    # 学年を判定
    grade = 0
    if '年' in class_name:
        try:
            grade = int(class_name.split('年')[0])
        except:
            grade = 0
    
    # 通常教科のリスト（固定科目と特殊科目を除く）
    regular_subjects = ["国", "社", "数", "理", "英", "音", "美", "保", "技", "家"]
    
    # 標準時数（デフォルト値）
    standard_hours = {
        "国": 4, "社": 3, "数": 3, "理": 3, "英": 4,
        "音": 1, "美": 1, "保": 3, "技": 2, "家": 1
    }
    
    # 学年別の優先順位調整
    if grade == 1:
        priority_order = ["英", "国", "数", "理", "社", "技", "家", "音", "美", "保"]
    elif grade == 2:
        priority_order = ["国", "英", "数", "社", "理", "技", "家", "音", "美", "保"]
    else:  # 3年
        priority_order = ["英", "数", "国", "社", "理", "音", "技", "美", "家", "保"]
    
    # 候補を探す
    candidates = []
    
    for subject in priority_order:
        # その日にすでに配置されている場合はスキップ
        if subject in day_subjects:
            continue
            
        # 固定科目・特殊科目はスキップ
        if subject in fixed_subjects or subject in special_subjects:
            continue
        
        current = current_hours.get(subject, 0)
        standard = standard_hours.get(subject, 2)
        
        if current < standard:
            shortage = standard - current
            candidates.append((shortage, subject))
    
    # 不足時数が多い順にソート
    candidates.sort(reverse=True)
    
    if candidates:
        return candidates[0][1]
    
    # 候補がない場合、その日に配置されていない通常教科を選ぶ
    for subject in regular_subjects:
        if subject not in day_subjects and subject not in fixed_subjects and subject not in special_subjects:
            return subject
    
    return None


def fill_empty_slots():
    """空白スロットを通常教科で埋める"""
    print("=== 空白スロットを通常教科で埋める ===")
    print("固定科目（欠、YT、総、学など）は使用しません\n")
    
    # 現在のoutput.csvを読み込む
    output_path = path_config.output_dir / "output.csv"
    print(f"Reading schedule from: {output_path}")
    
    with open(output_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        data = list(reader)
    
    # 固定科目と特殊科目のリスト
    fixed_subjects = ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行", "行事"]
    special_subjects = ["自立", "日生", "作業", "生単"]
    
    days = ["月", "火", "水", "木", "金"]
    filled_count = 0
    
    # 各行をチェック
    for row_idx, row in enumerate(data):
        if row_idx < 2:  # ヘッダー行をスキップ
            continue
            
        class_name = row[0] if row else ""
        
        # 空白行をスキップ
        if not class_name or class_name.strip() == '':
            continue
        
        # 各時間の空白をチェック
        for col_idx in range(1, min(31, len(row))):
            current_value = row[col_idx] if col_idx < len(row) else ""
            
            # 空白の場合
            if not current_value:
                # 曜日と時限を計算
                day_idx = (col_idx - 1) // 6
                period = ((col_idx - 1) % 6) + 1
                
                if day_idx < len(days):
                    day = days[day_idx]
                    
                    # 適切な科目を探す
                    new_subject = find_suitable_subject(
                        data, class_name, row_idx, day_idx, period,
                        fixed_subjects, special_subjects
                    )
                    
                    if new_subject:
                        print(f"Filling {class_name} {day}曜{period}限: 空白 → {new_subject}")
                        row[col_idx] = new_subject
                        filled_count += 1
                        
                        # 交流学級の同期（自立活動の時間は除く）
                        exchange_map = {
                            "1年1組": "1年6組", "1年6組": "1年1組",
                            "1年2組": "1年7組", "1年7組": "1年2組",
                            "2年3組": "2年6組", "2年6組": "2年3組",
                            "2年2組": "2年7組", "2年7組": "2年2組",
                            "3年3組": "3年6組", "3年6組": "3年3組",
                            "3年2組": "3年7組", "3年7組": "3年2組"
                        }
                        
                        if class_name in exchange_map:
                            exchange_class = exchange_map[class_name]
                            
                            # 交流学級の行を探す
                            for ex_idx, ex_row in enumerate(data):
                                if ex_idx >= 2 and ex_row and ex_row[0] == exchange_class:
                                    if col_idx < len(ex_row):
                                        # 交流学級が自立活動でない場合のみ同期
                                        if ex_row[col_idx] != "自立":
                                            print(f"  Syncing {exchange_class}: 空白 → {new_subject}")
                                            ex_row[col_idx] = new_subject
                                            filled_count += 1
                                    break
    
    # 修正後のデータを保存
    if filled_count > 0:
        # バックアップを作成
        backup_path = output_path.with_suffix('.csv.bak_fill_empty')
        with open(backup_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(data)
        print(f"\nBackup saved to: {backup_path}")
        
        # 修正版を保存
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(data)
        print(f"Filled {filled_count} empty slots with regular subjects")
        print(f"Updated schedule saved to: {output_path}")
    else:
        print("No empty slots found")
    
    return filled_count


if __name__ == "__main__":
    filled_count = fill_empty_slots()
    print(f"\nTotal slots filled: {filled_count}")
    print("\nCLAUDE.mdのルール:")
    print("- 空きスロットは通常教科のみで埋める")
    print("- 固定科目（欠、YT、総、学など）は新規配置しない")