#!/usr/bin/env python3
"""3年生の6限目の空きスロットをデバッグするスクリプト"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.application.services.data_loading_service import DataLoadingService
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.domain.value_objects.time_slot import TimeSlot, ClassReference

def main():
    # サービスの初期化
    data_loading_service = DataLoadingService()
    data_dir = Path("data")
    
    # 学校データ読み込み
    school, use_enhanced_features = data_loading_service.load_school_data(data_dir)
    
    # 最新の時間割を読み込み
    csv_repo = CSVScheduleRepository()
    schedule = csv_repo.load_desired_schedule("data/output/output.csv", school)
    
    print("=== 3年生の6限目の状況を確認 ===\n")
    
    # 月曜・火曜・水曜の6限目をチェック
    days = ["月", "火", "水"]
    third_grade_classes = [
        ClassReference(3, 1),
        ClassReference(3, 2),
        ClassReference(3, 3),
        ClassReference(3, 5),
        ClassReference(3, 6),
        ClassReference(3, 7),
    ]
    
    for day in days:
        print(f"\n{day}曜日 6限目:")
        time_slot = TimeSlot(day, 6)
        
        for class_ref in third_grade_classes:
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment:
                print(f"  {class_ref.full_name}: {assignment.subject.name} ({assignment.teacher.name})")
            else:
                print(f"  {class_ref.full_name}: [空き]")
                
                # 配置可能な科目をチェック
                print(f"    配置可能な科目:")
                base_hours = school.get_all_standard_hours(class_ref)
                
                # 現在の割り当て数をカウント
                current_hours = {}
                for d in ["月", "火", "水", "木", "金"]:
                    for p in range(1, 7):
                        ts = TimeSlot(d, p)
                        a = schedule.get_assignment(ts, class_ref)
                        if a and a.subject:
                            current_hours[a.subject.name] = current_hours.get(a.subject.name, 0) + 1
                
                # 標準時数順でソート
                available_subjects = []
                for subject, standard_hours in sorted(base_hours.items(), key=lambda x: x[1], reverse=True):
                    if subject.name in ["欠", "YT", "道", "学", "学活", "学総", "総", "総合", "行", "行事"]:
                        continue
                    current = current_hours.get(subject.name, 0)
                    remaining = standard_hours - current
                    available_subjects.append((subject.name, standard_hours, current, remaining))
                
                # 主要教科を優先
                main_subjects = [s for s in available_subjects if s[0] in ["算", "国", "理", "社", "英", "数"]]
                other_subjects = [s for s in available_subjects if s[0] not in ["算", "国", "理", "社", "英", "数"]]
                
                print("    主要教科:")
                for subject_name, standard, current, remaining in main_subjects[:5]:
                    print(f"      {subject_name}: 標準{standard}時間, 現在{current}時間, 残り{remaining}時間")
                print("    その他教科:")
                for subject_name, standard, current, remaining in other_subjects[:3]:
                    print(f"      {subject_name}: 標準{standard}時間, 現在{current}時間, 残り{remaining}時間")

if __name__ == "__main__":
    main()