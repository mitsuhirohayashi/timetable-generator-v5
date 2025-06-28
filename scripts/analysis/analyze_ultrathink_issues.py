#!/usr/bin/env python3
"""UltrathinkPerfectGeneratorの問題分析"""

import pandas as pd
from src.domain.entities import School, Schedule
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.domain.services.ultrathink import UltrathinkPerfectGenerator
from src.infrastructure.parsers.natural_followup_parser import NaturalFollowUpParser
from src.infrastructure.parsers.followup_parser import FollowUpParser
from src.domain.constraints.teacher_absence_constraint import TeacherAbsenceConstraint

def analyze_issues():
    """問題を分析"""
    print("=== UltrathinkPerfectGenerator問題分析 ===\n")
    
    # 1. データ読み込み
    # データローディングサービスを使用
    from src.application.services.data_loading_service import DataLoadingService
    data_service = DataLoadingService()
    school, _ = data_service.load_school_data("data/")
    schedule = data_service.load_initial_schedule("data/", "input.csv", start_empty=False)
    
    print(f"学校データ: クラス数={len(school.get_all_classes())}, 教師数={len(school.get_all_teachers())}")
    print(f"初期スケジュール: 割り当て数={len(schedule.get_all_assignments())}")
    
    # 2. テスト期間の確認
    print("\n【テスト期間の確認】")
    if hasattr(schedule, 'test_periods'):
        print(f"テスト期間: {schedule.test_periods}")
    else:
        print("テスト期間情報なし")
    
    # 3. 教師不在情報の確認
    print("\n【教師不在情報の確認】")
    parser = FollowUpParser()
    followup_data = parser.parse("data/input/Follow-up.csv")
    
    # 教師不在制約の作成
    absence_constraint = TeacherAbsenceConstraint()
    absence_constraint.teacher_absences = followup_data.get('teacher_absences', {})
    
    print(f"教師不在情報: {len(absence_constraint.teacher_absences)}名")
    for teacher, absences in absence_constraint.teacher_absences.items():
        print(f"  {teacher}: {absences}")
    
    # 4. 空きスロットの確認
    print("\n【空きスロットの確認】")
    empty_count = 0
    empty_by_class = {}
    
    days = ["月", "火", "水", "木", "金"]
    for class_ref in school.get_all_classes():
        class_empty = 0
        for day in days:
            for period in range(1, 7):
                from src.domain.value_objects.time_slot import TimeSlot
                time_slot = TimeSlot(day=day, period=period)
                if not schedule.get_assignment(time_slot, class_ref):
                    class_empty += 1
                    empty_count += 1
        
        if class_empty > 0:
            class_name = f"{class_ref.grade}-{class_ref.class_number}"
            empty_by_class[class_name] = class_empty
    
    print(f"総空きスロット: {empty_count}")
    for class_name, count in sorted(empty_by_class.items()):
        print(f"  {class_name}: {count}スロット")
    
    # 5. 自立活動の現状確認
    print("\n【自立活動の現状確認】")
    jiritsu_count = {}
    exchange_classes = ["1-6", "1-7", "2-6", "2-7", "3-6", "3-7"]
    
    for class_name in exchange_classes:
        parts = class_name.split('-')
        grade = int(parts[0])
        class_num = int(parts[1])
        
        count = 0
        for class_ref in school.get_all_classes():
            if class_ref.grade == grade and class_ref.class_number == class_num:
                for day in days:
                    for period in range(1, 7):
                        time_slot = TimeSlot(day=day, period=period)
                        assignment = schedule.get_assignment(time_slot, class_ref)
                        if assignment and assignment.subject.name == "自立":
                            count += 1
                break
        
        jiritsu_count[class_name] = count
    
    print("交流学級の自立活動時数:")
    for class_name, count in jiritsu_count.items():
        print(f"  {class_name}: {count}時間（必要: 2時間）")
    
    # 6. 通常科目の必要時数確認
    print("\n【通常科目の必要時数と現状】")
    required_hours = {
        "国": 4, "社": 3, "数": 4, "理": 3, "音": 1,
        "美": 1, "保": 3, "技": 1, "家": 1, "英": 4,
        "道": 1, "学": 1, "総": 1
    }
    
    # 1年1組の例
    for class_ref in school.get_all_classes():
        if class_ref.grade == 1 and class_ref.class_number == 1:
            print(f"\n1年1組の現状:")
            current_hours = {}
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day=day, period=period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        subject = assignment.subject.name
                        current_hours[subject] = current_hours.get(subject, 0) + 1
            
            for subject, required in required_hours.items():
                current = current_hours.get(subject, 0)
                diff = required - current
                status = "OK" if diff == 0 else f"不足{diff}" if diff > 0 else f"超過{-diff}"
                print(f"  {subject}: 必要{required}, 現在{current} [{status}]")
            break
    
    # 7. ロックされているセルの確認
    print("\n【ロックされているセルの確認】")
    locked_count = 0
    for class_ref in school.get_all_classes():
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day=day, period=period)
                if schedule.is_locked(time_slot, class_ref):
                    locked_count += 1
    
    print(f"ロックされているセル数: {locked_count}")

if __name__ == "__main__":
    analyze_issues()