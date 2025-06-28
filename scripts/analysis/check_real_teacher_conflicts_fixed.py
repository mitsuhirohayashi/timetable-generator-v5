#!/usr/bin/env python3
"""実際の教師名で教師重複を確認するスクリプト（テスト期間対応版）"""

import csv
import json
import os
import sys
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def load_teacher_mapping():
    """教師配置マッピングを読み込む"""
    teacher_mapping = defaultdict(list)
    
    with open("data/config/teacher_subject_mapping.csv", 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = f"{row['学年']}-{row['組']}-{row['教科']}"
            teacher_mapping[key] = row['教員名']
    
    return teacher_mapping


def load_test_periods():
    """テスト期間を読み込む"""
    with open("data/config/constraint_exclusion_rules.json", 'r', encoding='utf-8') as f:
        exclusion_rules = json.load(f)
    
    test_periods = set()
    if "exclusion_rules" in exclusion_rules and "test_periods" in exclusion_rules["exclusion_rules"]:
        for period_info in exclusion_rules["exclusion_rules"]["test_periods"]["periods"]:
            day = period_info["day"]
            for period in period_info["periods"]:
                test_periods.add(f"{day}{period}限")
    
    return test_periods


def is_test_period_conflict(time_slot, teacher, classes, subject_by_class):
    """テスト期間の正常な巡回監督かどうか判定"""
    # 同一学年かチェック
    grades = set()
    subjects = set()
    
    for cls in classes:
        if "-" in cls:
            grade = cls.split("-")[0]
            grades.add(grade)
            subjects.add(subject_by_class.get(cls, ""))
    
    # 同一学年・同一科目の場合はテスト巡回監督として正常
    return len(grades) == 1 and len(subjects) == 1


def check_teacher_conflicts():
    """実際の教師名で重複をチェック（テスト期間対応）"""
    print("=== 実際の教師名での教師重複チェック（テスト期間対応版） ===\n")
    
    # 時間割を読み込む
    with open("data/output/output.csv", 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        data = list(reader)
    
    # 教師マッピングとテスト期間を読み込む
    teacher_mapping = load_teacher_mapping()
    test_periods = load_test_periods()
    
    print(f"テスト期間: {sorted(test_periods)}\n")
    
    # 時間帯ごとの教師配置を記録
    time_slots = {}
    subject_by_time_class = {}  # 時間帯とクラスごとの科目を記録
    days = ["月", "火", "水", "木", "金"]
    periods = [1, 2, 3, 4, 5, 6]
    
    # クラス情報を収集
    for row_idx, row in enumerate(data):
        if not row or not row[0]:
            continue
        
        class_name = row[0].strip()
        if "組" not in class_name:
            continue
        
        # 学年と組を抽出
        if "年" in class_name and "組" in class_name:
            grade = class_name.split("年")[0]
            class_num = class_name.split("年")[1].split("組")[0]
            
            # 各時限の授業を確認
            for day_idx, day in enumerate(days):
                for period in periods:
                    col_idx = day_idx * 6 + period
                    
                    if col_idx < len(row):
                        subject = row[col_idx].strip()
                        
                        if subject and subject not in ["欠", "YT", ""]:
                            # 教師を特定
                            key = f"{grade}-{class_num}-{subject}"
                            teacher = teacher_mapping.get(key, f"{subject}担当")
                            
                            # 時間帯キー
                            time_key = f"{day}{period}限"
                            
                            if time_key not in time_slots:
                                time_slots[time_key] = defaultdict(list)
                            
                            time_slots[time_key][teacher].append(f"{grade}-{class_num}")
                            subject_by_time_class[f"{time_key}-{grade}-{class_num}"] = subject
    
    # 重複をチェック
    conflicts = []
    test_period_conflicts = []
    
    for time_slot, teachers in sorted(time_slots.items()):
        for teacher, classes in teachers.items():
            if len(classes) > 1:
                # 5組の合同授業は除外
                if set(classes) == {"1-5", "2-5", "3-5"}:
                    continue
                # 交流学級と親学級の体育は除外
                if len(classes) == 2:
                    parent_exchange_pairs = [
                        ("1-1", "1-6"), ("1-2", "1-7"), 
                        ("2-3", "2-6"), ("2-2", "2-7"),
                        ("3-3", "3-6"), ("3-2", "3-7")
                    ]
                    is_pair = False
                    for p1, p2 in parent_exchange_pairs:
                        if set(classes) == {p1, p2}:
                            is_pair = True
                            break
                    if is_pair:
                        continue
                
                # テスト期間かチェック
                if time_slot in test_periods:
                    # 科目情報を収集
                    subject_by_class = {}
                    for cls in classes:
                        subject_by_class[cls] = subject_by_time_class.get(f"{time_slot}-{cls}", "")
                    
                    if is_test_period_conflict(time_slot, teacher, classes, subject_by_class):
                        test_period_conflicts.append((time_slot, teacher, classes, "テスト巡回"))
                        continue
                
                conflicts.append((time_slot, teacher, classes))
    
    # 結果を表示
    print(f"検出された教師重複（テスト期間除外後）: {len(conflicts)}件")
    print(f"テスト期間の巡回監督（正常）: {len(test_period_conflicts)}件\n")
    
    # テスト期間の巡回監督を表示
    if test_period_conflicts:
        print("=== テスト期間の巡回監督（正常な運用） ===")
        for time_slot, teacher, classes, note in test_period_conflicts[:10]:  # 最初の10件
            print(f"【{time_slot}】{teacher} → {', '.join(sorted(classes))} （{note}）")
        if len(test_period_conflicts) > 10:
            print(f"... 他 {len(test_period_conflicts) - 10} 件")
        print()
    
    # 実際の違反を表示
    if conflicts:
        print("=== 実際の制約違反 ===")
        for time_slot, teacher, classes in conflicts[:20]:  # 最初の20件
            print(f"【{time_slot}】{teacher}が以下のクラスを同時に担当:")
            for cls in sorted(classes):
                print(f"  - {cls}組")
            print()
        
        if len(conflicts) > 20:
            print(f"... 他 {len(conflicts) - 20} 件の違反")
    
    # 特に重要な違反を強調
    if conflicts:
        print("\n=== 修正が必要な重複（テスト期間以外） ===")
        important_conflicts = [c for c in conflicts if c[1] not in ["欠課先生", "未定先生", "TBA"]]
        
        for time_slot, teacher, classes in important_conflicts[:10]:  # 最初の10件
            print(f"- {time_slot}: {teacher} → {', '.join(sorted(classes))}")
    else:
        print("✅ テスト期間を除外すると、実際の教師重複違反はありません。")


if __name__ == "__main__":
    check_teacher_conflicts()