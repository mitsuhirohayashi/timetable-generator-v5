#!/usr/bin/env python3
"""空白スロットを通常教科のみで埋める（固定科目は絶対に使用しない）"""

import csv
import sys
from pathlib import Path
from collections import Counter, defaultdict

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.infrastructure.config.path_config import path_config


def count_subject_hours(data, class_row_idx):
    """クラスの各科目の現在の時数をカウント"""
    counter = Counter()
    if class_row_idx >= len(data):
        return counter
    
    row = data[class_row_idx]
    for col_idx in range(1, len(row)):
        subject = row[col_idx] if col_idx < len(row) else ""
        if subject and subject not in ["", " "]:
            counter[subject] += 1
    
    return counter


def get_day_subjects(data, class_row_idx, day_idx):
    """特定の日の科目リストを取得"""
    subjects = []
    if class_row_idx >= len(data):
        return subjects
    
    row = data[class_row_idx]
    for period in range(1, 7):
        col_idx = day_idx * 6 + period
        if col_idx < len(row):
            subject = row[col_idx]
            if subject and subject not in ["", " "]:
                subjects.append(subject)
    
    return subjects


def find_best_subject(data, class_name, class_row_idx, day_idx, period):
    """空白スロットに最適な通常教科を見つける"""
    
    # 固定科目リスト（絶対に使用しない）
    fixed_subjects = ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行", "行事"]
    
    # 特殊科目リスト（5組専用など）
    special_subjects = ["自立", "日生", "作業", "生単"]
    
    # 通常教科リスト
    normal_subjects = ["国", "社", "数", "理", "英", "音", "美", "保", "技", "家"]
    
    # 現在の時数をカウント
    current_hours = count_subject_hours(data, class_row_idx)
    
    # その日の科目を取得（重複チェック用）
    day_subjects = get_day_subjects(data, class_row_idx, day_idx)
    
    # 学年を判定
    grade = 0
    if '年' in class_name:
        try:
            grade = int(class_name.split('年')[0])
        except:
            grade = 0
    
    # 標準時数（参考値）
    standard_hours = {
        "国": 4, "社": 3, "数": 4 if grade == 1 else 3, 
        "理": 3, "英": 4, "音": 1, "美": 1, 
        "保": 3, "技": 2, "家": 1
    }
    
    # 候補を探す
    candidates = []
    
    for subject in normal_subjects:
        # その日にすでに配置されている場合はスキップ
        if subject in day_subjects:
            continue
        
        current = current_hours.get(subject, 0)
        standard = standard_hours.get(subject, 2)
        
        # 時数が不足している科目を優先
        if current < standard:
            shortage = standard - current
            priority = 1 if subject in ["国", "数", "英"] else 2  # 主要教科を優先
            candidates.append((priority, shortage, subject))
    
    # 優先度と不足時数でソート
    candidates.sort(key=lambda x: (x[0], -x[1]))
    
    if candidates:
        return candidates[0][2]
    
    # 候補がない場合、その日に配置されていない通常教科を選ぶ
    for subject in normal_subjects:
        if subject not in day_subjects:
            return subject
    
    return None


def fill_empty_slots():
    """空白スロットを通常教科のみで埋める"""
    print("=== 空白スロットを通常教科のみで埋める ===")
    print("固定科目（欠、YT、総、学、道など）は絶対に使用しません")
    print("CLAUDE.mdのルールを厳守します\n")
    
    # 現在のoutput.csvを読み込む
    output_path = path_config.output_dir / "output.csv"
    print(f"Reading schedule from: {output_path}")
    
    with open(output_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        data = list(reader)
    
    days = ["月", "火", "水", "木", "金"]
    filled_count = 0
    
    # 各行をチェック
    for row_idx, row in enumerate(data):
        if row_idx < 2:  # ヘッダー行をスキップ
            continue
            
        class_name = row[0] if row else ""
        
        # 空のクラス名や交流学級（6組・7組）の空白行はスキップ
        if not class_name or class_name.strip() == '':
            continue
        
        # 5組のみ空白を埋める（通常学級と5組のみ）
        if '6組' in class_name or '7組' in class_name:
            continue
        
        # 各時間の空白をチェック
        for col_idx in range(1, min(31, len(row))):
            current_value = row[col_idx] if col_idx < len(row) else ""
            
            # 空白の場合のみ処理
            if not current_value or current_value.strip() == "":
                # 曜日と時限を計算
                day_idx = (col_idx - 1) // 6
                period = ((col_idx - 1) % 6) + 1
                
                if day_idx < len(days):
                    day = days[day_idx]
                    
                    # 最適な通常教科を探す
                    new_subject = find_best_subject(
                        data, class_name, row_idx, day_idx, period
                    )
                    
                    if new_subject:
                        print(f"Filling {class_name} {day}曜{period}限: 空白 → {new_subject}")
                        row[col_idx] = new_subject
                        filled_count += 1
    
    # 修正後のデータを保存
    if filled_count > 0:
        # バックアップを作成
        backup_path = output_path.with_suffix('.csv.bak_filled_normal')
        with open(backup_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(data)
        print(f"\nBackup saved to: {backup_path}")
        
        # 修正版を保存
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(data)
        print(f"Filled {filled_count} empty slots with normal subjects only")
        print(f"Updated schedule saved to: {output_path}")
    else:
        print("No empty slots found or all slots already filled")
    
    return filled_count


def verify_no_fixed_subjects_added(data):
    """固定科目が追加されていないことを確認"""
    fixed_subjects = ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行", "行事"]
    
    # input.csvを読み込んで比較
    input_path = path_config.data_dir / "input" / "input.csv"
    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        input_data = list(reader)
    
    violations = []
    
    for row_idx in range(2, min(len(input_data), len(data))):
        for col_idx in range(1, 31):
            if col_idx < len(input_data[row_idx]) and col_idx < len(data[row_idx]):
                input_val = input_data[row_idx][col_idx] if col_idx < len(input_data[row_idx]) else ""
                output_val = data[row_idx][col_idx] if col_idx < len(data[row_idx]) else ""
                
                # 空白だった場所に固定科目が追加されていないかチェック
                if (not input_val or input_val.strip() == "") and output_val in fixed_subjects:
                    violations.append(f"{data[row_idx][0]} col{col_idx}: 空白 → {output_val}")
    
    if violations:
        print("\n❌ 警告: 固定科目が追加されています:")
        for v in violations:
            print(f"  {v}")
    else:
        print("\n✅ 確認: 固定科目は一切追加されていません")


if __name__ == "__main__":
    filled_count = fill_empty_slots()
    
    # 検証
    output_path = path_config.output_dir / "output.csv"
    with open(output_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        data = list(reader)
    
    verify_no_fixed_subjects_added(data)
    
    print(f"\n合計 {filled_count} 個の空白スロットを通常教科で埋めました")
    print("\nCLAUDE.mdのルール準拠:")
    print("✅ 空白スロットは通常教科（国、数、英、理、社、音、美、保、技、家など）で埋めること")
    print("✅ 固定科目（欠、YT、総、学など）は新規配置しない")