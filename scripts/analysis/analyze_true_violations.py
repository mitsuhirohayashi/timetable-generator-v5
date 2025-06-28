#!/usr/bin/env python3
"""真の制約違反のみを分析（5組合同授業とテスト巡回を正しく処理）"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from collections import defaultdict
from src.infrastructure.config.path_config import path_config

def analyze_true_violations():
    """真の制約違反のみを分析"""
    
    # テスト期間の定義（Follow-up.csvより）
    test_periods = [
        ('月', '1'), ('月', '2'), ('月', '3'),
        ('火', '1'), ('火', '2'), ('火', '3'),
        ('水', '1'), ('水', '2')
    ]
    
    # 時間割を読み込み
    schedule_df = pd.read_csv(path_config.output_dir / "output.csv", header=None)
    
    # ヘッダー行をスキップして処理
    days = schedule_df.iloc[0, 1:].tolist()
    periods = schedule_df.iloc[1, 1:].tolist()
    
    # 教師マッピングを読み込み
    teacher_mapping_df = pd.read_csv(path_config.config_dir / "teacher_subject_mapping.csv")
    
    # 教師と科目のマッピングを作成
    teacher_subject_map = {}
    for _, row in teacher_mapping_df.iterrows():
        key = (row['学年'], row['組'], row['教科'])
        teacher_subject_map[key] = row['教員名']
    
    print("=== 真の制約違反の分析 ===\n")
    
    # 1. 教師重複違反の詳細分析
    print("【教師重複違反の詳細】\n")
    time_teacher_assignments = defaultdict(lambda: defaultdict(list))
    
    for row_idx in range(2, len(schedule_df)):
        row = schedule_df.iloc[row_idx]
        if pd.isna(row[0]) or row[0] == "":
            continue
            
        class_name = row[0]
        if '年' not in class_name or '組' not in class_name:
            continue
            
        # クラス情報を解析
        parts = class_name.split('年')
        grade = int(parts[0])
        class_num = int(parts[1].replace('組', ''))
        
        for col_idx in range(1, len(row)):
            subject = row[col_idx]
            if pd.isna(subject) or subject == "" or subject == "欠":
                continue
                
            day = days[col_idx - 1]
            period = periods[col_idx - 1]
            
            # 教師を特定
            teacher_key = (grade, class_num, subject)
            teacher = teacher_subject_map.get(teacher_key, None)
            
            if teacher:
                time_key = (day, period)
                time_teacher_assignments[time_key][teacher].append({
                    'class': class_name,
                    'subject': subject,
                    'grade': grade,
                    'class_num': class_num
                })
    
    # 実際の違反を収集
    real_violations = []
    
    for (day, period), teacher_classes in time_teacher_assignments.items():
        is_test_period = (day, period) in test_periods
        
        for teacher, assignments in teacher_classes.items():
            if len(assignments) > 1:
                # 各種チェック
                grades = set(a['grade'] for a in assignments)
                class_nums = set(a['class_num'] for a in assignments)
                
                # 5組が含まれているかチェック
                has_grade5 = any(a['class_num'] == 5 for a in assignments)
                all_grade5 = all(a['class_num'] == 5 for a in assignments)
                
                # 同一学年かチェック
                same_grade = len(grades) == 1
                
                # スキップ条件
                if all_grade5:  # 全て5組（合同授業）
                    continue
                elif is_test_period and same_grade:  # テスト期間の同一学年
                    continue
                elif has_grade5 and len([a for a in assignments if a['class_num'] == 5]) == 3:
                    # 5組3クラスが含まれている場合、それらを1つとして扱う
                    non_grade5 = [a for a in assignments if a['class_num'] != 5]
                    if len(non_grade5) <= 1:  # 5組以外が1クラス以下なら問題なし
                        continue
                
                # 実際の違反
                real_violations.append({
                    'teacher': teacher,
                    'day': day,
                    'period': period,
                    'classes': [a['class'] for a in assignments],
                    'subjects': [a['subject'] for a in assignments],
                    'grades': list(grades),
                    'violation_type': '異学年同時担当' if len(grades) > 1 else '同学年複数クラス'
                })
    
    # 違反を時間帯別に表示
    violations_by_time = defaultdict(list)
    for v in real_violations:
        violations_by_time[(v['day'], v['period'])].append(v)
    
    total_teacher_violations = len(real_violations)
    
    for (day, period), violations in sorted(violations_by_time.items()):
        print(f"{day}曜{period}校時（{len(violations)}件）:")
        for v in violations:
            classes_str = ', '.join(v['classes'])
            subjects_str = ', '.join(set(v['subjects']))
            print(f"  - {v['teacher']}先生: {classes_str} ({subjects_str}) [{v['violation_type']}]")
        print()
    
    # 2. 体育館使用違反の詳細分析
    print("\n【体育館使用違反の詳細】\n")
    time_pe_classes = defaultdict(list)
    
    for row_idx in range(2, len(schedule_df)):
        row = schedule_df.iloc[row_idx]
        if pd.isna(row[0]) or row[0] == "":
            continue
            
        class_name = row[0]
        if '年' not in class_name or '組' not in class_name:
            continue
            
        for col_idx in range(1, len(row)):
            subject = row[col_idx]
            if pd.isna(subject) or subject == "":
                continue
                
            # 体育関連科目かチェック
            if subject in ['保', '保健', '体育', '保健体育']:
                day = days[col_idx - 1]
                period = periods[col_idx - 1]
                
                time_key = (day, period)
                time_pe_classes[time_key].append(class_name)
    
    gym_violations = []
    
    for (day, period), classes in time_pe_classes.items():
        if len(classes) > 1:
            is_test_period = (day, period) in test_periods
            is_grade5_joint = all('5組' in c for c in classes)
            
            if not is_test_period and not is_grade5_joint:
                gym_violations.append({
                    'day': day,
                    'period': period,
                    'classes': classes,
                    'count': len(classes)
                })
    
    total_gym_violations = len(gym_violations)
    
    for v in sorted(gym_violations, key=lambda x: (x['day'], x['period'])):
        print(f"{v['day']}曜{v['period']}校時:")
        print(f"  同時使用クラス: {', '.join(v['classes'])}")
        print(f"  → {v['count']}クラスが体育館を同時使用\n")
    
    # 3. サマリー
    print("\n=== 真の制約違反サマリー ===")
    print(f"教師重複違反: {total_teacher_violations} 件")
    print(f"体育館使用違反: {total_gym_violations} 件")
    print(f"合計: {total_teacher_violations + total_gym_violations} 件")
    
    # 統計情報
    if real_violations:
        print("\n【違反が多い教師】")
        teacher_count = defaultdict(int)
        for v in real_violations:
            teacher_count[v['teacher']] += 1
        
        for teacher, count in sorted(teacher_count.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {teacher}先生: {count}件")

if __name__ == "__main__":
    analyze_true_violations()