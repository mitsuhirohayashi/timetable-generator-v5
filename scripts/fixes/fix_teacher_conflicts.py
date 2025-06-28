#!/usr/bin/env python3
"""教師重複違反を修正"""

import csv
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Set

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.infrastructure.config.path_config import path_config


def analyze_teacher_conflicts():
    """教師の重複を分析"""
    # 現在のoutput.csvを読み込む
    output_path = path_config.output_dir / "output.csv"
    
    with open(output_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        data = list(reader)
    
    # 教師マッピングを読み込む
    teacher_mapping_path = path_config.data_dir / "config" / "teacher_subject_mapping.csv"
    teacher_subject_map = {}  # (subject, class) -> teacher
    
    with open(teacher_mapping_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            teacher = row['教員名']
            subject = row['教科']
            grade = row['学年']
            class_num = row['組']
            class_name = f"{grade}年{class_num}組"
            key = (subject, class_name)
            teacher_subject_map[key] = teacher
    
    # 時間割データから教師の割り当てを抽出
    # teacher_schedule[(day, period)] = [(teacher, class, subject), ...]
    teacher_schedule = defaultdict(list)
    
    days = ["月", "火", "水", "木", "金"]
    
    for row_idx, row in enumerate(data):
        if row_idx < 2:  # ヘッダー行をスキップ
            continue
            
        class_name = row[0] if row else ""
        
        # 空白行をスキップ
        if not class_name or class_name.strip() == '':
            continue
        
        # 各時間の科目を確認
        for col_idx in range(1, min(31, len(row))):  # 列1-30 (月1-金6)
            subject = row[col_idx] if col_idx < len(row) else ""
            if not subject:
                continue
                
            # 列番号から曜日と校時を計算
            day_idx = (col_idx - 1) // 6
            period = ((col_idx - 1) % 6) + 1
            
            if day_idx < len(days):
                day = days[day_idx]
                
                # 固定科目や特殊科目はスキップ
                if subject in ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行", "自立", "日生", "作業", "生単"]:
                    continue
                
                # 教師を特定
                key = (subject, class_name)
                teacher = teacher_subject_map.get(key, f"{subject}担当")
                
                teacher_schedule[(day, period)].append((teacher, class_name, subject))
    
    # 重複を検出
    conflicts = []
    for (day, period), assignments in teacher_schedule.items():
        # 同じ教師が複数クラスを担当している場合
        teacher_count = defaultdict(list)
        for teacher, class_name, subject in assignments:
            teacher_count[teacher].append((class_name, subject))
        
        for teacher, classes in teacher_count.items():
            if len(classes) > 1:
                # 5組の合同授業は除外
                grade5_classes = [c for c, _ in classes if c.endswith("5組")]
                if len(grade5_classes) == len(classes) and len(set(s for _, s in classes)) == 1:
                    continue
                    
                conflicts.append({
                    'day': day,
                    'period': period,
                    'teacher': teacher,
                    'classes': classes
                })
    
    return conflicts


def fix_teacher_conflicts():
    """教師重複違反を修正"""
    print("=== 教師重複違反の修正 ===\n")
    
    # 重複を分析
    conflicts = analyze_teacher_conflicts()
    
    if not conflicts:
        print("教師重複違反は見つかりませんでした")
        return 0
    
    print(f"教師重複違反を{len(conflicts)}件検出しました")
    
    # 現在のoutput.csvを読み込む
    output_path = path_config.output_dir / "output.csv"
    with open(output_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        data = list(reader)
    
    # クラス名から行番号のマッピング
    class_to_row = {}
    for i, row in enumerate(data):
        if i >= 2 and row and row[0]:
            class_name = row[0].strip()
            class_to_row[class_name] = i
    
    # 修正件数
    fixed_count = 0
    
    # 具体的な修正を実施
    print("\n修正対象:")
    
    # 1. 月曜2限の井野口先生重複（1-1と1-2）
    for conflict in conflicts:
        if conflict['day'] == '月' and conflict['period'] == 2 and conflict['teacher'] == '井野口':
            print(f"\n■ 月曜2限の井野口先生重複")
            # 1-2の月曜2限を他の科目に変更
            if "1年2組" in class_to_row:
                row_idx = class_to_row["1年2組"]
                col_idx = 2  # 月曜2限
                print(f"  修正: 1年2組の月曜2限を「英」→「国」に変更")
                data[row_idx][col_idx] = "国"
                fixed_count += 1
                break
    
    # 2. 火曜3限の井野口先生重複（1-3と3-6）
    for conflict in conflicts:
        if conflict['day'] == '火' and conflict['period'] == 3 and conflict['teacher'] == '井野口':
            print(f"\n■ 火曜3限の井野口先生重複")
            # 3-6は交流学級なので、親学級（3-3）を確認
            if "3年3組" in class_to_row and "3年6組" in class_to_row:
                row_3_3 = class_to_row["3年3組"]
                row_3_6 = class_to_row["3年6組"]
                col_idx = 9  # 火曜3限
                
                # 3-3を数学に変更すれば、3-6は自立活動可能
                print(f"  修正: 3年3組の火曜3限を「英」→「数」に変更")
                print(f"  修正: 3年6組の火曜3限を「英」→「自立」に変更")
                data[row_3_3][col_idx] = "数"
                data[row_3_6][col_idx] = "自立"
                fixed_count += 2
                break
    
    # 3. その他の重大な重複を修正
    for conflict in conflicts[:3]:  # 最初の3件のみ
        if fixed_count >= 5:  # 一度に修正する数を制限
            break
            
        day = conflict['day']
        period = conflict['period']
        teacher = conflict['teacher']
        classes = conflict['classes']
        
        # 列インデックスを計算
        day_idx = ["月", "火", "水", "木", "金"].index(day)
        col_idx = day_idx * 6 + period
        
        # 最初のクラスは維持し、2番目のクラスを変更
        if len(classes) >= 2:
            class_name, subject = classes[1]
            if class_name in class_to_row:
                row_idx = class_to_row[class_name]
                
                # 他の科目に変更
                print(f"\n■ {day}曜{period}限の{teacher}重複")
                print(f"  修正: {class_name}の{subject}を別の科目に変更")
                
                # その日の使用済み科目を確認
                used_subjects = []
                for p in range(1, 7):
                    col = day_idx * 6 + p
                    if col < len(data[row_idx]):
                        used_subjects.append(data[row_idx][col])
                
                # 使用可能な科目を探す
                available = ["国", "社", "数", "理", "英", "音", "美", "保", "技", "家"]
                available = [s for s in available if s not in used_subjects]
                
                if available:
                    data[row_idx][col_idx] = available[0]
                    fixed_count += 1
    
    # 修正後のデータを保存
    if fixed_count > 0:
        # バックアップを作成
        backup_path = output_path.with_suffix('.csv.bak_teacher')
        with open(backup_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(data)
        print(f"\nBackup saved to: {backup_path}")
        
        # 修正版を保存
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(data)
        print(f"\nFixed {fixed_count} teacher conflicts")
        print(f"Updated schedule saved to: {output_path}")
    
    return fixed_count


if __name__ == "__main__":
    fixed_count = fix_teacher_conflicts()
    print(f"\nTotal conflicts fixed: {fixed_count}")
    print("\n制約違反チェックを再実行してください:")
    print("  python3 check_violations.py")