#!/usr/bin/env python3
"""実際の教師名で教師重複を確認するスクリプト"""

import csv
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


def check_teacher_conflicts():
    """実際の教師名で重複をチェック"""
    print("=== 実際の教師名での教師重複チェック ===\n")
    
    # 時間割を読み込む
    with open("data/output/output.csv", 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        data = list(reader)
    
    # 教師マッピングを読み込む
    teacher_mapping = load_teacher_mapping()
    
    # 時間帯ごとの教師配置を記録
    time_slots = {}
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
    
    # 重複をチェック
    conflicts = []
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
                
                conflicts.append((time_slot, teacher, classes))
    
    # 結果を表示
    print(f"検出された教師重複: {len(conflicts)}件\n")
    
    for time_slot, teacher, classes in conflicts:
        print(f"【{time_slot}】{teacher}が以下のクラスを同時に担当:")
        for cls in sorted(classes):
            print(f"  - {cls}組")
        print()
    
    # 特に重要な違反を強調
    print("\n=== 特に修正が必要な重複 ===")
    important_conflicts = [c for c in conflicts if c[1] not in ["欠課先生", "未定先生", "TBA"]]
    
    for time_slot, teacher, classes in important_conflicts[:10]:  # 最初の10件
        print(f"- {time_slot}: {teacher} → {', '.join(sorted(classes))}")


if __name__ == "__main__":
    check_teacher_conflicts()