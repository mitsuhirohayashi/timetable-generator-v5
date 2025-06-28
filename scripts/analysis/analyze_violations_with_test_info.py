#!/usr/bin/env python3
"""テスト期間を考慮した制約違反分析"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from collections import defaultdict
from src.infrastructure.config.path_config import path_config

def analyze_violations_with_test_info():
    """テスト期間を考慮して制約違反を分析"""
    
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
    
    print("=== テスト期間を考慮した制約違反分析 ===\n")
    
    # 1. 教師重複の再分析
    print("【教師重複違反の再分析】")
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
                    'grade': grade
                })
    
    # 重複を分析（テスト期間を考慮）
    real_teacher_violations = []
    test_period_supervisions = []
    grade5_joint_classes = []
    
    for (day, period), teacher_classes in time_teacher_assignments.items():
        is_test_period = (day, period) in test_periods
        
        for teacher, assignments in teacher_classes.items():
            if len(assignments) > 1:
                # 5組合同授業かチェック
                is_grade5 = all('5組' in a['class'] for a in assignments)
                
                # 同一学年かチェック
                grades = set(a['grade'] for a in assignments)
                same_grade = len(grades) == 1
                
                if is_grade5:
                    grade5_joint_classes.append({
                        'teacher': teacher,
                        'day': day,
                        'period': period,
                        'classes': [a['class'] for a in assignments]
                    })
                elif is_test_period and same_grade:
                    test_period_supervisions.append({
                        'teacher': teacher,
                        'day': day,
                        'period': period,
                        'classes': [a['class'] for a in assignments],
                        'grade': list(grades)[0]
                    })
                else:
                    real_teacher_violations.append({
                        'teacher': teacher,
                        'day': day,
                        'period': period,
                        'classes': [a['class'] for a in assignments]
                    })
    
    print(f"教師重複総数: {len(real_teacher_violations) + len(test_period_supervisions) + len(grade5_joint_classes)}")
    print(f"- テスト期間の巡回監督: {len(test_period_supervisions)} 件（正常）")
    print(f"- 5組合同授業: {len(grade5_joint_classes)} 件（正常）")
    print(f"- 実際の違反: {len(real_teacher_violations)} 件\n")
    
    # 2. 体育館使用の再分析
    print("【体育館使用違反の再分析】")
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
    
    real_gym_violations = []
    test_period_pe = []
    
    for (day, period), classes in time_pe_classes.items():
        if len(classes) > 1:
            is_test_period = (day, period) in test_periods
            is_grade5_joint = all('5組' in c for c in classes)
            
            if is_test_period:
                test_period_pe.append({
                    'day': day,
                    'period': period,
                    'classes': classes,
                    'count': len(classes)
                })
            elif not is_grade5_joint:
                real_gym_violations.append({
                    'day': day,
                    'period': period,
                    'classes': classes,
                    'count': len(classes)
                })
    
    print(f"体育館使用重複: {len(real_gym_violations) + len(test_period_pe)}")
    print(f"- テスト期間のペーパーテスト: {len(test_period_pe)} 件（正常）")
    print(f"- 実際の違反: {len(real_gym_violations)} 件\n")
    
    # 3. サマリー
    print("=== 最終的な制約違反サマリー ===")
    print(f"実際の教師重複違反: {len(real_teacher_violations)} 件")
    print(f"実際の体育館使用違反: {len(real_gym_violations)} 件")
    print(f"合計違反件数: {len(real_teacher_violations) + len(real_gym_violations)} 件\n")
    
    # 詳細表示
    if real_teacher_violations:
        print("【実際の教師重複違反（上位5件）】")
        for v in real_teacher_violations[:5]:
            print(f"  {v['teacher']}先生: {v['day']}{v['period']}校時 - {', '.join(v['classes'])}")
    
    if real_gym_violations:
        print("\n【実際の体育館使用違反】")
        for v in real_gym_violations:
            print(f"  {v['day']}{v['period']}校時: {v['count']}クラス - {', '.join(v['classes'])}")

if __name__ == "__main__":
    analyze_violations_with_test_info()