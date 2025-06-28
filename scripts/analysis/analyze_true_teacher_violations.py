#!/usr/bin/env python3
"""真の教師重複違反のみを分析（テストと5組を正しく処理）"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from collections import defaultdict
from src.infrastructure.config.path_config import path_config

def analyze_true_teacher_violations():
    """真の教師重複違反のみを分析"""
    
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
    
    print("=== 真の教師重複違反の分析 ===\n")
    
    # 時間割から教師の配置を収集
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
    
    # 違反を収集（正しい判定で）
    violations = []
    skipped_cases = []
    
    for (day, period), teacher_classes in time_teacher_assignments.items():
        is_test_period = (day, period) in test_periods
        
        for teacher, assignments in teacher_classes.items():
            if len(assignments) <= 1:
                continue
                
            # 各種チェック
            grades = set(a['grade'] for a in assignments)
            class_nums = [a['class_num'] for a in assignments]
            
            # 5組のチェック
            grade5_assignments = [a for a in assignments if a['class_num'] == 5]
            non_grade5_assignments = [a for a in assignments if a['class_num'] != 5]
            
            # 6組・7組の自立活動チェック（許容される）
            is_jiritsu_67 = (teacher in ['財津', '智田'] and 
                           all(a['subject'] == '自立' for a in assignments) and
                           all(num in [6, 7] for num in class_nums))
            
            # スキップ条件の詳細な判定
            skip_reason = None
            
            # 全て5組の場合
            if len(grade5_assignments) == len(assignments) and len(grade5_assignments) == 3:
                skip_reason = "5組合同授業"
            # テスト期間で同一学年の通常クラスのみ
            elif is_test_period and len(grades) == 1 and len(grade5_assignments) == 0:
                skip_reason = "テスト期間の巡回"
            # テスト期間で、通常クラス（同一学年）+ 5組の組み合わせ
            elif is_test_period and len(non_grade5_assignments) > 0:
                non_grade5_grades = set(a['grade'] for a in non_grade5_assignments)
                if len(non_grade5_grades) == 1 and len(grade5_assignments) == 3:
                    skip_reason = "テスト巡回＋5組合同"
            # 6組・7組の自立活動
            elif is_jiritsu_67:
                skip_reason = "6組・7組の自立活動（許容）"
            
            if skip_reason:
                skipped_cases.append({
                    'teacher': teacher,
                    'day': day,
                    'period': period,
                    'classes': [a['class'] for a in assignments],
                    'reason': skip_reason
                })
                continue
            
            # 実際の違反
            violations.append({
                'teacher': teacher,
                'day': day,
                'period': period,
                'classes': [a['class'] for a in assignments],
                'subjects': list(set(a['subject'] for a in assignments)),
                'grades': sorted(grades),
                'violation_type': '異学年同時担当' if len(grades) > 1 else '同学年複数クラス'
            })
    
    # スキップしたケースを表示
    print("【正常と判定されたケース（抜粋）】")
    for case in skipped_cases[:5]:
        print(f"{case['day']}曜{case['period']}校時 - {case['teacher']}先生: {case['reason']}")
    if len(skipped_cases) > 5:
        print(f"... 他 {len(skipped_cases) - 5} 件\n")
    else:
        print()
    
    # 違反を表示
    print("【真の教師重複違反】")
    print(f"合計: {len(violations)} 件\n")
    
    # 異学年同時担当
    cross_grade = [v for v in violations if v['violation_type'] == '異学年同時担当']
    same_grade = [v for v in violations if v['violation_type'] == '同学年複数クラス']
    
    print(f"異学年同時担当: {len(cross_grade)} 件")
    for v in sorted(cross_grade, key=lambda x: (x['day'], x['period'])):
        print(f"  {v['day']}曜{v['period']}校時 - {v['teacher']}先生: {', '.join(v['classes'])}")
    
    print(f"\n同学年複数クラス: {len(same_grade)} 件")
    for v in sorted(same_grade, key=lambda x: (x['day'], x['period'])):
        print(f"  {v['day']}曜{v['period']}校時 - {v['teacher']}先生: {', '.join(v['classes'])}")
    
    # 教師別集計
    teacher_count = defaultdict(int)
    for v in violations:
        teacher_count[v['teacher']] += 1
    
    print("\n【違反が多い教師】")
    for teacher, count in sorted(teacher_count.items(), 
                               key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {teacher}先生: {count} 件")

if __name__ == "__main__":
    analyze_true_teacher_violations()