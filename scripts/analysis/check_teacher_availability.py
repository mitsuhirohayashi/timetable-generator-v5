#!/usr/bin/env python3
"""教師の空き状況を確認するスクリプト"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.application.services.data_loading_service import DataLoadingService
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from collections import defaultdict

def main():
    # サービスの初期化
    data_loading_service = DataLoadingService()
    data_dir = Path("data")
    
    # 学校データ読み込み
    school, use_enhanced_features = data_loading_service.load_school_data(data_dir)
    
    # 最新の時間割を読み込み
    csv_repo = CSVScheduleRepository()
    schedule = csv_repo.load_desired_schedule("data/output/output.csv", school)
    
    print("=== 3年生6限目の教師空き状況 ===\n")
    
    # 空きスロットと必要な科目
    empty_slots = [
        (TimeSlot("月", 6), ClassReference(3, 3)),
        (TimeSlot("火", 6), ClassReference(3, 3)),
        (TimeSlot("火", 6), ClassReference(3, 5)),
        (TimeSlot("水", 6), ClassReference(3, 5))
    ]
    
    for time_slot, class_ref in empty_slots:
        print(f"\n{class_ref.full_name} {time_slot}:")
        
        # この時間の教師の状況を確認
        busy_teachers = set()
        for c in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, c)
            if assignment and assignment.teacher:
                busy_teachers.add(assignment.teacher.name)
        
        # 必要な科目と利用可能な教師を確認
        base_hours = school.get_all_standard_hours(class_ref)
        
        # 現在の割り当て数をカウント
        current_hours = defaultdict(int)
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                ts = TimeSlot(day, period)
                a = schedule.get_assignment(ts, class_ref)
                if a and a.subject:
                    current_hours[a.subject.name] += 1
        
        # 標準時数順でソート（固定科目を除く）
        available_subjects = []
        fixed_subjects = ["欠", "YT", "道", "学", "学活", "学総", "総", "総合", "行"]
        
        for subject, standard_hours in sorted(base_hours.items(), key=lambda x: x[1], reverse=True):
            if subject.name not in fixed_subjects:
                current = current_hours.get(subject.name, 0)
                shortage = standard_hours - current
                
                # この科目を教えられる教師を探す
                available_teachers = []
                for teacher in school.get_subject_teachers(subject):
                    if teacher.name not in busy_teachers:
                        available_teachers.append(teacher.name)
                
                if available_teachers:
                    available_subjects.append({
                        'subject': subject.name,
                        'standard': standard_hours,
                        'current': current,
                        'shortage': shortage,
                        'teachers': available_teachers
                    })
        
        # 主要教科を優先
        print("  配置可能な科目:")
        for subj in available_subjects[:5]:
            print(f"    {subj['subject']}: 標準{subj['standard']}時間, 現在{subj['current']}時間, 不足{subj['shortage']}時間")
            print(f"      利用可能教師: {', '.join(subj['teachers'])}")

if __name__ == "__main__":
    main()