#!/usr/bin/env python3
"""どの制約が3年生6限目の配置をブロックしているか調査"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.application.services.data_loading_service import DataLoadingService
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from src.domain.value_objects.assignment import Assignment
from src.domain.constraints.daily_duplicate_constraint import DailyDuplicateConstraint
from src.domain.constraints.teacher_conflict_constraint_refactored import TeacherConflictConstraintRefactored
from src.domain.constraints.exchange_class_sync_constraint import ExchangeClassSyncConstraint

def main():
    # サービスの初期化
    data_loading_service = DataLoadingService()
    data_dir = Path("data")
    
    # 学校データ読み込み
    school, use_enhanced_features = data_loading_service.load_school_data(data_dir)
    
    # 最新の時間割を読み込み
    csv_repo = CSVScheduleRepository()
    schedule = csv_repo.load_desired_schedule("data/output/output.csv", school)
    
    print("=== 3年3組 月曜6限に数学を配置できない理由 ===\n")
    
    time_slot = TimeSlot("月", 6)
    class_ref = ClassReference(3, 3)
    
    # 数学の教師を探す
    subject = None
    for subj in school.get_all_standard_hours(class_ref).keys():
        if subj.name == "数":
            subject = subj
            break
    
    if subject:
        # 利用可能な教師を確認
        teachers = list(school.get_subject_teachers(subject))
        print(f"数学を教えられる教師: {[t.name for t in teachers]}")
        
        # 個別の制約をチェック
        daily_duplicate = DailyDuplicateConstraint()
        teacher_conflict = TeacherConflictConstraintRefactored()
        exchange_sync = ExchangeClassSyncConstraint()
        
        for teacher in teachers[:3]:  # 最初の3人だけテスト
            print(f"\n{teacher.name}先生で配置を試行:")
            
            # この時間に既に授業があるかチェック
            is_busy = False
            for c in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, c)
                if assignment and assignment.teacher and assignment.teacher.name == teacher.name:
                    print(f"  → {teacher.name}先生は既に{c.full_name}で授業中")
                    is_busy = True
                    break
            
            if not is_busy:
                # 配置を試す
                test_assignment = Assignment(class_ref, subject, teacher)
                
                # 日内重複チェック
                if not daily_duplicate.check(schedule, school, time_slot, test_assignment):
                    print(f"  → 日内重複制約違反: 3年3組の月曜日に数学が既にあります")
                    continue
                
                # 教師重複チェック
                if not teacher_conflict.check(schedule, school, time_slot, test_assignment):
                    print(f"  → 教師重複制約違反: {teacher.name}先生は同時刻に他のクラスで授業があります")
                    continue
                
                # 交流学級同期チェック（もし3年3組が親学級の場合）
                # 3年3組は通常クラスなので、この制約は関係ないはず
                
                print(f"  → 配置可能！")

if __name__ == "__main__":
    main()