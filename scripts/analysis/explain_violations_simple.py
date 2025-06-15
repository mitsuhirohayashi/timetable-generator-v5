#!/usr/bin/env python3
"""制約違反を分かりやすく説明するシンプル版"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from collections import defaultdict
import csv

def read_output_csv(file_path):
    """時間割CSVを読み込む"""
    schedule = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)  # 曜日行
        periods = next(reader)  # 時限行
        
        for row in reader:
            if not row[0] or row[0].strip() == "":  # 空行をスキップ
                continue
            class_name = row[0]
            schedule[class_name] = {}
            
            for i, (day, period, subject) in enumerate(zip(headers[1:], periods[1:], row[1:])):
                if day and period:
                    time_key = f"{day}曜{period}時限"
                    schedule[class_name][time_key] = subject.strip()
    
    return schedule

def read_teacher_mapping():
    """教師マッピングを読み込む"""
    teacher_mapping = {}
    file_path = Path(__file__).parent.parent.parent / "data" / "config" / "teacher_subject_mapping.csv"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            teacher = row['教員名']
            subject = row['教科']
            grade = int(row['学年'])
            class_num = int(row['組'])
            class_key = f"{grade}年{class_num}組"
            
            if class_key not in teacher_mapping:
                teacher_mapping[class_key] = {}
            teacher_mapping[class_key][subject] = teacher
    
    return teacher_mapping

def read_team_teaching_config():
    """チームティーチング設定を読み込む"""
    import json
    file_path = Path(__file__).parent.parent.parent / "data" / "config" / "team_teaching_config.json"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    grade5_teachers = set(config['grade5_team_teaching']['team_teaching_teachers'])
    flexible_subjects = config['grade5_team_teaching'].get('flexible_subjects', {})
    simultaneous_teachers = {item['teacher'] for item in config['simultaneous_classes']}
    
    return grade5_teachers, flexible_subjects, simultaneous_teachers

def analyze_violations(schedule, teacher_mapping):
    """制約違反を分析"""
    violations = {
        'teacher_conflicts': defaultdict(list),
        'gym_conflicts': defaultdict(list),
        'grade5_issues': defaultdict(list),
        'empty_slots': defaultdict(int)
    }
    
    # チームティーチング設定を読み込む
    grade5_teachers, flexible_subjects, simultaneous_teachers = read_team_teaching_config()
    
    # 時間ごとにチェック
    all_times = set()
    for class_schedule in schedule.values():
        all_times.update(class_schedule.keys())
    
    for time_key in sorted(all_times):
        # その時間の全授業を収集
        time_assignments = []
        for class_name, class_schedule in schedule.items():
            if time_key in class_schedule and class_schedule[time_key]:
                subject = class_schedule[time_key]
                if class_name in teacher_mapping and subject in teacher_mapping[class_name]:
                    teacher = teacher_mapping[class_name][subject]
                    time_assignments.append({
                        'class': class_name,
                        'subject': subject,
                        'teacher': teacher
                    })
        
        # 教師の重複をチェック
        teacher_classes = defaultdict(list)
        for assignment in time_assignments:
            teacher_classes[assignment['teacher']].append(assignment)
        
        for teacher, assignments in teacher_classes.items():
            if len(assignments) > 1:
                # 特別な教師はスキップ
                if teacher in simultaneous_teachers:
                    continue
                
                # 5組の教師の場合
                if teacher in grade5_teachers:
                    # 5組以外のクラスが含まれているかチェック
                    non_grade5 = [a for a in assignments if "5組" not in a['class']]
                    if non_grade5:
                        # 5組と他クラスの同時授業
                        classes = [a['class'] for a in assignments]
                        subjects = list(set(a['subject'] for a in assignments))
                        
                        # 国語の柔軟対応チェック
                        if teacher in ["寺田", "金子み"] and all(s == "国" for s in subjects):
                            violations['grade5_issues'][time_key].append({
                                'teacher': teacher,
                                'classes': classes,
                                'type': 'flexible_japanese',
                                'subjects': subjects
                            })
                        else:
                            violations['teacher_conflicts'][time_key].append({
                                'teacher': teacher,
                                'classes': classes,
                                'subjects': subjects
                            })
                else:
                    # 通常の教師重複
                    classes = [a['class'] for a in assignments]
                    subjects = list(set(a['subject'] for a in assignments))
                    violations['teacher_conflicts'][time_key].append({
                        'teacher': teacher,
                        'classes': classes,
                        'subjects': subjects
                    })
        
        # 体育館使用をチェック
        pe_classes = [a for a in time_assignments if a['subject'] == '保']
        if len(pe_classes) > 1:
            violations['gym_conflicts'][time_key] = [a['class'] for a in pe_classes]
    
    # 空きコマをカウント
    for class_name, class_schedule in schedule.items():
        empty_count = sum(1 for v in class_schedule.values() if not v or v == "")
        if empty_count > 0:
            violations['empty_slots'][class_name] = empty_count
    
    return violations

def main():
    """メイン処理"""
    print("="*60)
    print("時間割の制約違反を分かりやすく説明します")
    print("="*60)
    print()
    
    # ファイルパス
    output_file = Path(__file__).parent.parent.parent / "data" / "output" / "output.csv"
    
    # データ読み込み
    print("【データ読み込み中...】")
    schedule = read_output_csv(output_file)
    teacher_mapping = read_teacher_mapping()
    
    # 違反分析
    violations = analyze_violations(schedule, teacher_mapping)
    
    print("\n【制約違反の詳細説明】\n")
    
    # 1. 教師の重複授業
    if violations['teacher_conflicts']:
        print("■ 教師が同じ時間に複数クラスで授業している問題")
        print("  （1人の教師は同時に1つのクラスしか教えられません）\n")
        
        for time_key, conflicts in sorted(violations['teacher_conflicts'].items()):
            print(f"  ◆ {time_key}:")
            for conflict in conflicts:
                classes_str = "、".join(conflict['classes'])
                subjects_str = "、".join(conflict['subjects'])
                print(f"    - {conflict['teacher']}先生が {classes_str} で同時に授業")
                print(f"      教科: {subjects_str}")
            print()
    
    # 2. 5組の特殊ケース
    if violations['grade5_issues']:
        print("■ 5組の国語授業の調整が必要な箇所")
        print("  （5組の国語は寺田先生か金子み先生のどちらかが担当可能）\n")
        
        for time_key, issues in sorted(violations['grade5_issues'].items()):
            print(f"  ◆ {time_key}:")
            for issue in issues:
                if issue['type'] == 'flexible_japanese':
                    classes_str = "、".join(issue['classes'])
                    print(f"    - {issue['teacher']}先生が {classes_str} で国語の授業")
                    other_teacher = "金子み" if issue['teacher'] == "寺田" else "寺田"
                    print(f"      → {other_teacher}先生が空いていれば、5組は{other_teacher}先生が担当可能")
            print()
    
    # 3. 体育館の重複使用
    if violations['gym_conflicts']:
        print("■ 体育館を複数クラスが同時に使用している問題")
        print("  （体育館は1つしかないので、同時に使えるのは1クラスだけ）\n")
        
        for time_key, classes in sorted(violations['gym_conflicts'].items()):
            classes_str = "、".join(classes)
            print(f"  ◆ {time_key}: {classes_str} が同時に体育")
            
            # 5組が含まれている場合の特記
            grade5_classes = [c for c in classes if "5組" in c]
            if len(grade5_classes) >= 2:
                print(f"      ※ 5組（{', '.join(grade5_classes)}）は合同体育の可能性")
                print(f"      → それでも体育館は1つなので、時間調整が必要")
            print()
    
    # 4. 空きコマ
    if violations['empty_slots']:
        print("■ 空きコマがあるクラス")
        print("  （授業が入っていない時間）\n")
        
        total_empty = sum(violations['empty_slots'].values())
        for class_name, count in sorted(violations['empty_slots'].items(), key=lambda x: -x[1]):
            print(f"  - {class_name}: {count}コマ")
        print(f"\n  合計: {total_empty}コマの空き")
        print()
    
    # サマリー
    print("【まとめ】")
    violation_count = (
        sum(len(conflicts) for conflicts in violations['teacher_conflicts'].values()) +
        sum(len(issues) for issues in violations['grade5_issues'].values()) +
        len(violations['gym_conflicts'])
    )
    
    print(f"  • 教師重複: {sum(len(v) for v in violations['teacher_conflicts'].values())}件")
    print(f"  • 5組調整: {sum(len(v) for v in violations['grade5_issues'].values())}件")
    print(f"  • 体育館重複: {len(violations['gym_conflicts'])}件")
    print(f"  • 空きコマ: {sum(violations['empty_slots'].values())}コマ")
    print(f"\n  違反合計: {violation_count}件")
    
    print("\n【対処方法】")
    print("  1. 教師重複 → 別の教師に変更するか、時間を移動")
    print("  2. 5組調整 → 寺田/金子み先生の空き時間を確認して調整")
    print("  3. 体育館重複 → 体育の時間を別の時間に移動")
    print("  4. 空きコマ → 必要に応じて授業を配置")

if __name__ == "__main__":
    main()