#!/usr/bin/env python3
"""教師重複違反の詳細分析（最終版）"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from collections import defaultdict
from src.infrastructure.config.path_config import path_config

def analyze_teacher_violations_detail():
    """教師重複違反の詳細を分析"""
    
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
    
    print("=== 教師重複違反の詳細分析（最終版） ===\n")
    
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
    
    # 違反を分類
    violations_by_type = {
        '異学年同時担当': [],
        '同学年複数クラス': [],
        '5組混在': []  # 5組と通常クラスの混在
    }
    
    for (day, period), teacher_classes in time_teacher_assignments.items():
        is_test_period = (day, period) in test_periods
        
        for teacher, assignments in teacher_classes.items():
            if len(assignments) <= 1:
                continue
                
            # 各種チェック
            grades = set(a['grade'] for a in assignments)
            class_nums = [a['class_num'] for a in assignments]
            
            # 5組のチェック
            grade5_count = class_nums.count(5)
            all_grade5 = all(num == 5 for num in class_nums)
            
            # 6組・7組の自立活動チェック（許容される）
            is_jiritsu_67 = (teacher in ['財津', '智田'] and 
                           all(a['subject'] == '自立' for a in assignments) and
                           all(num in [6, 7] for num in class_nums))
            
            # スキップ条件
            if all_grade5:  # 全て5組（合同授業）
                continue
            elif is_test_period and len(grades) == 1:  # テスト期間の同一学年
                continue
            elif is_jiritsu_67:  # 6組・7組の自立活動（許容）
                continue
            
            # 違反タイプを判定
            if len(grades) > 1:
                violations_by_type['異学年同時担当'].append({
                    'teacher': teacher,
                    'day': day,
                    'period': period,
                    'classes': [a['class'] for a in assignments],
                    'subjects': list(set(a['subject'] for a in assignments)),
                    'grades': sorted(grades)
                })
            elif grade5_count > 0 and grade5_count < len(assignments):
                violations_by_type['5組混在'].append({
                    'teacher': teacher,
                    'day': day,
                    'period': period,
                    'classes': [a['class'] for a in assignments],
                    'subjects': list(set(a['subject'] for a in assignments)),
                    'grade5_classes': [a['class'] for a in assignments if a['class_num'] == 5],
                    'other_classes': [a['class'] for a in assignments if a['class_num'] != 5]
                })
            else:
                violations_by_type['同学年複数クラス'].append({
                    'teacher': teacher,
                    'day': day,
                    'period': period,
                    'classes': [a['class'] for a in assignments],
                    'subjects': list(set(a['subject'] for a in assignments)),
                    'grade': list(grades)[0]
                })
    
    # 結果を表示
    print("【異学年同時担当】（最も深刻 - 物理的に不可能）")
    print(f"件数: {len(violations_by_type['異学年同時担当'])} 件\n")
    
    for v in sorted(violations_by_type['異学年同時担当'], 
                   key=lambda x: (x['day'], x['period'])):
        print(f"{v['day']}曜{v['period']}校時 - {v['teacher']}先生:")
        print(f"  クラス: {', '.join(v['classes'])}")
        print(f"  学年: {v['grades']}")
        print(f"  科目: {', '.join(v['subjects'])}")
        print()
    
    print("\n【5組混在】（5組合同授業と通常クラスの混在）")
    print(f"件数: {len(violations_by_type['5組混在'])} 件\n")
    
    for v in sorted(violations_by_type['5組混在'], 
                   key=lambda x: (x['day'], x['period'])):
        print(f"{v['day']}曜{v['period']}校時 - {v['teacher']}先生:")
        print(f"  5組: {', '.join(v['grade5_classes'])}")
        print(f"  その他: {', '.join(v['other_classes'])}")
        print(f"  科目: {', '.join(v['subjects'])}")
        print()
    
    print("\n【同学年複数クラス】（同時に複数教室は困難）")
    print(f"件数: {len(violations_by_type['同学年複数クラス'])} 件\n")
    
    for v in sorted(violations_by_type['同学年複数クラス'], 
                   key=lambda x: (x['day'], x['period'])):
        print(f"{v['day']}曜{v['period']}校時 - {v['teacher']}先生:")
        print(f"  クラス: {', '.join(v['classes'])} （{v['grade']}年生）")
        print(f"  科目: {', '.join(v['subjects'])}")
        print()
    
    # サマリー
    total = sum(len(violations) for violations in violations_by_type.values())
    print("\n=== サマリー ===")
    print(f"教師重複違反 合計: {total} 件")
    print(f"- 異学年同時担当: {len(violations_by_type['異学年同時担当'])} 件（最優先で修正必要）")
    print(f"- 5組混在: {len(violations_by_type['5組混在'])} 件")
    print(f"- 同学年複数クラス: {len(violations_by_type['同学年複数クラス'])} 件")
    
    # 教師別集計
    teacher_count = defaultdict(int)
    for vtype, violations in violations_by_type.items():
        for v in violations:
            teacher_count[v['teacher']] += 1
    
    print("\n【違反が多い教師トップ5】")
    for teacher, count in sorted(teacher_count.items(), 
                               key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {teacher}先生: {count} 件")

if __name__ == "__main__":
    analyze_teacher_violations_detail()