#!/usr/bin/env python3
"""教師の担当構造を詳細分析"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.infrastructure.config.path_config import path_config
import pandas as pd
from collections import defaultdict
import json

def analyze_teacher_mapping():
    """教師マッピングの詳細分析"""
    # teacher_subject_mapping.csvを読み込み
    mapping_path = path_config.config_dir / "teacher_subject_mapping.csv"
    df = pd.read_csv(mapping_path)
    
    print("=== 教師担当構造の分析 ===\n")
    
    # 教師ごとの担当状況を集計
    teacher_stats = defaultdict(lambda: {
        'subjects': set(),
        'classes': set(),
        'total_assignments': 0,
        'subject_class_pairs': []
    })
    
    for _, row in df.iterrows():
        teacher = row['教員名']
        subject = row['教科']
        grade = row['学年']
        class_num = row['組']
        class_ref = f"{grade}年{class_num}組"
        
        teacher_stats[teacher]['subjects'].add(subject)
        teacher_stats[teacher]['classes'].add(class_ref)
        teacher_stats[teacher]['total_assignments'] += 1
        teacher_stats[teacher]['subject_class_pairs'].append((subject, class_ref))
    
    # 問題のある教師（同じ科目を複数クラスで担当）を特定
    problematic_teachers = {}
    for teacher, stats in teacher_stats.items():
        subject_classes = defaultdict(list)
        for subject, class_ref in stats['subject_class_pairs']:
            subject_classes[subject].append(class_ref)
        
        for subject, classes in subject_classes.items():
            if len(classes) > 1:
                if teacher not in problematic_teachers:
                    problematic_teachers[teacher] = {}
                problematic_teachers[teacher][subject] = classes
    
    print(f"複数クラスで同じ科目を担当している教師: {len(problematic_teachers)}人\n")
    
    # 詳細表示
    total_conflicts = 0
    for teacher, subjects in sorted(problematic_teachers.items()):
        print(f"{teacher}先生:")
        for subject, classes in subjects.items():
            print(f"  {subject}: {', '.join(classes)} ({len(classes)}クラス)")
            total_conflicts += len(classes) - 1
        print()
    
    print(f"潜在的な時間割衝突数: {total_conflicts}件")
    
    # 科目別の教師数を分析
    subject_teachers = defaultdict(set)
    for _, row in df.iterrows():
        subject_teachers[row['教科']].add(row['教員名'])
    
    print("\n=== 科目別教師数 ===")
    for subject, teachers in sorted(subject_teachers.items()):
        print(f"{subject}: {len(teachers)}人 ({', '.join(sorted(teachers))})")
    
    return problematic_teachers, df

def create_conflict_analysis(problematic_teachers, df):
    """教師衝突の分析"""
    # 衝突する授業のペアを収集
    class_subject_pairs = []
    conflicts = defaultdict(list)
    
    for _, row in df.iterrows():
        teacher = row['教員名']
        if teacher in problematic_teachers:
            subject = row['教科']
            class_ref = f"{row['学年']}年{row['組']}組"
            if subject in problematic_teachers[teacher]:
                class_subject_pairs.append((class_ref, subject, teacher))
    
    # 同じ教師が担当する授業間の衝突を記録
    for i, (class1, subject1, teacher1) in enumerate(class_subject_pairs):
        for j, (class2, subject2, teacher2) in enumerate(class_subject_pairs[i+1:], i+1):
            if teacher1 == teacher2:
                conflicts[teacher1].append((f"{class1}_{subject1}", f"{class2}_{subject2}"))
    
    print(f"\n=== 教師衝突分析 ===")
    print(f"衝突する授業ペア数: {sum(len(v) for v in conflicts.values())}")
    
    # 最も衝突の多い教師
    if conflicts:
        max_conflicts_teacher = max(conflicts.items(), key=lambda x: len(x[1]))
        print(f"最も衝突の多い教師: {max_conflicts_teacher[0]} ({len(max_conflicts_teacher[1])}ペア)")
    
    return conflicts

def analyze_schedule_constraints(problematic_teachers):
    """スケジュール制約の分析"""
    print("\n=== スケジュール制約の分析 ===")
    
    # 各教師の週あたり最大授業数
    max_periods_per_week = 5 * 6  # 5日 × 6時限
    
    for teacher, subjects in problematic_teachers.items():
        total_classes = sum(len(classes) for classes in subjects.values())
        print(f"\n{teacher}先生:")
        print(f"  担当クラス数: {total_classes}")
        print(f"  週あたり最大可能授業数: {max_periods_per_week}")
        
        # 各科目の必要時間数を推定（仮定）
        estimated_hours = {}
        for subject, classes in subjects.items():
            if subject in ['国', '数', '英']:
                hours_per_class = 4  # 主要教科
            elif subject in ['理', '社']:
                hours_per_class = 3
            elif subject in ['保', '音', '美', '技', '家']:
                hours_per_class = 2
            else:
                hours_per_class = 1
            
            estimated_hours[subject] = hours_per_class * len(classes)
        
        total_required = sum(estimated_hours.values())
        print(f"  推定必要授業時間: {total_required}時間")
        print(f"  充足率: {min(100, total_required / max_periods_per_week * 100):.1f}%")
        
        if total_required > max_periods_per_week:
            print(f"  ⚠️ 物理的に不可能！追加教師が必要です。")

def suggest_solutions(problematic_teachers):
    """解決策の提案"""
    print("\n=== 解決策の提案 ===")
    
    solutions = []
    
    for teacher, subjects in problematic_teachers.items():
        for subject, classes in subjects.items():
            if len(classes) > 3:
                solutions.append({
                    'type': 'split_teacher',
                    'teacher': teacher,
                    'subject': subject,
                    'classes': classes,
                    'suggestion': f"{teacher}先生の{subject}を2人の教師で分担"
                })
            elif len(classes) > 1:
                solutions.append({
                    'type': 'time_constraint',
                    'teacher': teacher,
                    'subject': subject,
                    'classes': classes,
                    'suggestion': f"{teacher}先生の{subject}授業を異なる時間に配置"
                })
    
    print("\n推奨される解決策:")
    for i, solution in enumerate(solutions, 1):
        print(f"\n{i}. {solution['suggestion']}")
        print(f"   対象: {', '.join(solution['classes'])}")
        if solution['type'] == 'split_teacher':
            print(f"   理由: {len(solution['classes'])}クラスは1人では困難")
    
    return solutions

def main():
    # 教師マッピングを分析
    problematic_teachers, df = analyze_teacher_mapping()
    
    # 衝突分析
    conflicts = create_conflict_analysis(problematic_teachers, df)
    
    # スケジュール制約を分析
    analyze_schedule_constraints(problematic_teachers)
    
    # 解決策を提案
    solutions = suggest_solutions(problematic_teachers)
    
    # 分析結果を保存
    analysis_results = {
        'problematic_teachers': {
            teacher: {subject: classes for subject, classes in subjects.items()}
            for teacher, subjects in problematic_teachers.items()
        },
        'total_conflicts': sum(len(v) for v in conflicts.values()),
        'solutions': solutions
    }
    
    with open('teacher_analysis_results.json', 'w', encoding='utf-8') as f:
        json.dump(analysis_results, f, ensure_ascii=False, indent=2)
    
    print("\n分析結果を teacher_analysis_results.json に保存しました")

if __name__ == "__main__":
    main()