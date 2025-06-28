#!/usr/bin/env python3
"""違反の詳細分析スクリプト"""

import pandas as pd
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from src.domain.entities.school import School
from src.domain.entities.schedule import Schedule
from src.domain.value_objects.time_slot import TimeSlot
from src.infrastructure.parsers.basics_parser import BasicsParser
from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
from src.infrastructure.repositories.schedule_io.csv_writer import CSVScheduleWriter
from src.infrastructure.parsers.followup_constraint_parser import FollowupConstraintParser

def analyze_teacher_conflicts(schedule, school):
    """教師重複の詳細分析"""
    print("\n=== 教師重複の詳細分析 ===")
    
    # テスト期間の情報を取得
    parser = FollowupConstraintParser()
    constraints = parser.parse('data/input/Follow-up.csv')
    test_periods = []
    for constraint in constraints:
        if "テスト" in constraint.description and "時間割の変更をしないでください" in constraint.description:
            # 月曜1-3、火曜1-3、水曜1-2がテスト期間
            if "月曜" in constraint.description or constraint.day == "月":
                test_periods.extend([("月", 1), ("月", 2), ("月", 3)])
            elif "火曜" in constraint.description or constraint.day == "火":
                test_periods.extend([("火", 1), ("火", 2), ("火", 3)])
            elif "水曜" in constraint.description or constraint.day == "水":
                test_periods.extend([("水", 1), ("水", 2)])
    
    # 教師マッピングファイルを読み込む
    teacher_mapping = {}
    try:
        df = pd.read_csv('data/config/teacher_subject_mapping.csv')
        for _, row in df.iterrows():
            key = f"{row['学年']}年{row['組']}組_{row['教科']}"
            teacher_mapping[key] = row['教員名']
    except Exception as e:
        print(f"教師マッピングファイルの読み込みエラー: {e}")
        return
    
    # 時間ごとの教師配置を確認
    conflicts = []
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            teacher_assignments = {}
            
            for class_obj in school.classes:
                assignment = schedule.get_assignment(class_obj.class_id, time_slot)
                if assignment and assignment.subject and assignment.subject.name not in ["欠", "YT"]:
                    # 教師を特定
                    key = f"{class_obj.grade}年{class_obj.class_num}組_{assignment.subject.name}"
                    teacher = teacher_mapping.get(key, f"{assignment.subject.name}担当")
                    
                    if teacher not in teacher_assignments:
                        teacher_assignments[teacher] = []
                    teacher_assignments[teacher].append(class_obj.class_id)
            
            # 重複をチェック
            for teacher, classes in teacher_assignments.items():
                if len(classes) > 1:
                    # 5組の合同授業は除外
                    if set(classes) == {"1年5組", "2年5組", "3年5組"}:
                        continue
                    
                    # テスト期間の巡回監督は除外
                    is_test_period = (day, period) in test_periods
                    if is_test_period:
                        # 同じ学年のテストかチェック
                        grades = set()
                        subjects = set()
                        for cls in classes:
                            grade = int(cls[0])
                            grades.add(grade)
                            assignment = schedule.get_assignment(cls, time_slot)
                            if assignment and assignment.subject:
                                subjects.add(assignment.subject.name)
                        
                        # 同じ学年で同じ科目なら巡回監督として正常
                        if len(grades) == 1 and len(subjects) == 1:
                            print(f"  {day}曜{period}限: {teacher}先生 - テスト巡回監督 ({', '.join(classes)})")
                            continue
                    
                    # 交流学級と親学級の体育は除外
                    exchange_pairs = [
                        ("1年1組", "1年6組"), ("1年2組", "1年7組"),
                        ("2年3組", "2年6組"), ("2年2組", "2年7組"),
                        ("3年3組", "3年6組"), ("3年2組", "3年7組")
                    ]
                    is_exchange_pair = False
                    for parent, exchange in exchange_pairs:
                        if set(classes) == {parent, exchange}:
                            # 両方とも体育かチェック
                            parent_subj = schedule.get_assignment(parent, time_slot).subject.name
                            exchange_subj = schedule.get_assignment(exchange, time_slot).subject.name
                            if parent_subj == "保" and exchange_subj == "保":
                                is_exchange_pair = True
                                break
                    
                    if not is_exchange_pair:
                        conflicts.append({
                            'day': day,
                            'period': period,
                            'teacher': teacher,
                            'classes': classes,
                            'is_test': is_test_period
                        })
    
    # 結果を表示
    print(f"\n真の教師重複: {len(conflicts)}件")
    for conflict in conflicts:
        test_note = " (テスト期間)" if conflict['is_test'] else ""
        print(f"  {conflict['day']}曜{conflict['period']}限: {conflict['teacher']}先生 - {', '.join(conflict['classes'])}{test_note}")

def analyze_other_violations(schedule, school):
    """その他の違反の詳細分析"""
    print("\n\n=== その他の違反の詳細分析 ===")
    
    # 月曜6限の固定違反
    print("\n【月曜6限固定違反】")
    monday_6_violations = []
    for class_obj in school.classes:
        if class_obj.grade in [1, 2]:  # 1・2年生のみ
            time_slot = TimeSlot("月", 6)
            assignment = schedule.get_assignment(class_obj.class_id, time_slot)
            if assignment and assignment.subject and assignment.subject.name != "欠":
                monday_6_violations.append({
                    'class': class_obj.class_id,
                    'subject': assignment.subject.name
                })
    
    print(f"月曜6限違反: {len(monday_6_violations)}件")
    for v in monday_6_violations:
        print(f"  {v['class']}: {v['subject']} (欠であるべき)")
    
    # 標準時数との差分
    print("\n【標準時数との差分】")
    try:
        base_df = pd.read_csv('data/config/base_timetable.csv', index_col=0)
        hour_violations = []
        
        for class_obj in school.classes:
            class_hours = {}
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(class_obj.class_id, time_slot)
                    if assignment and assignment.subject:
                        subj_name = assignment.subject.name
                        if subj_name not in ["欠", "YT", "学", "総", "道", "学総", "行"]:
                            class_hours[subj_name] = class_hours.get(subj_name, 0) + 1
            
            # 標準時数と比較
            if class_obj.class_id in base_df.columns:
                for subject in base_df.index:
                    standard = base_df.loc[subject, class_obj.class_id]
                    if pd.notna(standard) and standard > 0:
                        actual = class_hours.get(subject, 0)
                        diff = standard - actual
                        if abs(diff) >= 1:  # 1時間以上の差
                            hour_violations.append({
                                'class': class_obj.class_id,
                                'subject': subject,
                                'standard': standard,
                                'actual': actual,
                                'diff': diff
                            })
        
        print(f"時数差分違反: {len(hour_violations)}件")
        for v in sorted(hour_violations, key=lambda x: abs(x['diff']), reverse=True)[:10]:
            print(f"  {v['class']} {v['subject']}: 標準{v['standard']}時間 vs 実際{v['actual']}時間 (差{v['diff']:+.1f})")
    except Exception as e:
        print(f"標準時数ファイルの読み込みエラー: {e}")

def analyze_jiritsu_violations(schedule, school):
    """自立活動違反の詳細分析"""
    print("\n\n=== 自立活動違反の詳細分析 ===")
    
    exchange_mapping = {
        "1年6組": "1年1組",
        "1年7組": "1年2組",
        "2年6組": "2年3組",
        "2年7組": "2年2組",
        "3年6組": "3年3組",
        "3年7組": "3年2組"
    }
    
    violations = []
    for exchange_class, parent_class in exchange_mapping.items():
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                exchange_assignment = schedule.get_assignment(exchange_class, time_slot)
                
                if exchange_assignment and exchange_assignment.subject and exchange_assignment.subject.name == "自立":
                    parent_assignment = schedule.get_assignment(parent_class, time_slot)
                    if parent_assignment and parent_assignment.subject:
                        parent_subject = parent_assignment.subject.name
                        if parent_subject not in ["数", "英"]:
                            violations.append({
                                'day': day,
                                'period': period,
                                'exchange': exchange_class,
                                'parent': parent_class,
                                'parent_subject': parent_subject
                            })
    
    print(f"自立活動違反: {len(violations)}件")
    for v in violations:
        print(f"  {v['day']}曜{v['period']}限: {v['exchange']}が自立活動、{v['parent']}が{v['parent_subject']} (数学か英語であるべき)")

def main():
    # データ読み込み（簡易版）
    school = School()
    
    # クラス定義を読み込む
    class_df = pd.read_csv('data/config/class_definitions.csv')
    for _, row in class_df.iterrows():
        from src.domain.entities.class_entity import Class
        class_obj = Class(
            grade=row['学年'],
            class_num=row['組'],
            class_type=row['クラスタイプ']
        )
        school.add_class(class_obj)
    
    # 時間割読み込み
    reader = CSVScheduleReader()
    schedule = reader.read('data/output/output.csv', school)
    
    # 各種分析
    analyze_teacher_conflicts(schedule, school)
    analyze_other_violations(schedule, school)
    analyze_jiritsu_violations(schedule, school)
    
    # 空きコマの確認
    print("\n\n=== 空きコマの詳細 ===")
    empty_slots = []
    for class_obj in school.classes:
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(class_obj.class_id, time_slot)
                if not assignment or not assignment.subject:
                    empty_slots.append({
                        'class': class_obj.class_id,
                        'day': day,
                        'period': period
                    })
    
    print(f"空きコマ総数: {len(empty_slots)}個")
    for slot in empty_slots:
        print(f"  {slot['class']}: {slot['day']}曜{slot['period']}限")

if __name__ == "__main__":
    main()