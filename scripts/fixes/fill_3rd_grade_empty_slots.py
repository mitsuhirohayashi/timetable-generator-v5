#!/usr/bin/env python3
"""3年生の6限目の空きスロットを手動で埋めるスクリプト"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.application.services.data_loading_service import DataLoadingService
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from src.domain.value_objects.assignment import Assignment

def main():
    # サービスの初期化
    data_loading_service = DataLoadingService()
    data_dir = Path("data")
    
    # 学校データ読み込み
    school, use_enhanced_features = data_loading_service.load_school_data(data_dir)
    
    # 最新の時間割を読み込み
    csv_repo = CSVScheduleRepository()
    schedule = csv_repo.load_desired_schedule("data/output/output.csv", school)
    
    print("=== 3年生の6限目の空きスロットを埋める ===\n")
    
    # 3年3組の月曜6限に数学を配置
    try:
        time_slot = TimeSlot("月", 6)
        class_ref = ClassReference(3, 3)
        
        # 標準時数から数学の科目オブジェクトを取得
        base_hours = school.get_all_standard_hours(class_ref)
        subject = None
        for subj, hours in base_hours.items():
            if subj.name == "数":
                subject = subj
                break
        
        if subject:
            # 数学の教師を探す
            teachers = list(school.get_subject_teachers(subject))
            for teacher in teachers:
                # この時間に空いている教師を探す
                is_available = True
                for c in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, c)
                    if assignment and assignment.teacher and assignment.teacher.name == teacher.name:
                        is_available = False
                        break
                
                if is_available:
                    print(f"3年3組 月曜6限に 数({teacher.name}) を配置")
                    assignment = Assignment(class_ref, subject, teacher)
                    schedule.assign(time_slot, assignment)
                    break
    except Exception as e:
        print(f"エラー: {e}")
    
    # 3年3組の火曜6限に理科を配置
    try:
        time_slot = TimeSlot("火", 6)
        class_ref = ClassReference(3, 3)
        
        # 標準時数から理科の科目オブジェクトを取得
        base_hours = school.get_all_standard_hours(class_ref)
        subject = None
        for subj, hours in base_hours.items():
            if subj.name == "理":
                subject = subj
                break
        
        if subject:
            # 理科の教師を探す
            teachers = list(school.get_subject_teachers(subject))
            for teacher in teachers:
                # この時間に空いている教師を探す
                is_available = True
                for c in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, c)
                    if assignment and assignment.teacher and assignment.teacher.name == teacher.name:
                        is_available = False
                        break
                
                if is_available:
                    print(f"3年3組 火曜6限に 理({teacher.name}) を配置")
                    assignment = Assignment(class_ref, subject, teacher)
                    schedule.assign(time_slot, assignment)
                    break
    except Exception as e:
        print(f"エラー: {e}")
    
    # 3年5組の火曜6限に保健体育を配置
    try:
        time_slot = TimeSlot("火", 6)
        class_ref = ClassReference(3, 5)
        
        # 標準時数から保健体育の科目オブジェクトを取得
        base_hours = school.get_all_standard_hours(class_ref)
        subject = None
        for subj, hours in base_hours.items():
            if subj.name == "保":
                subject = subj
                break
        
        if subject:
            # 保健体育の教師を探す（金子み先生を優先）
            teachers = list(school.get_subject_teachers(subject))
            teacher_found = None
            for teacher in teachers:
                if "金子み" in teacher.name:
                    teacher_found = teacher
                    break
            
            if not teacher_found and teachers:
                teacher_found = teachers[0]
            
            if teacher_found:
                # この時間に空いているかチェック
                is_available = True
                for c in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, c)
                    if assignment and assignment.teacher and assignment.teacher.name == teacher_found.name:
                        is_available = False
                        break
                
                if is_available:
                    print(f"3年5組 火曜6限に 保({teacher_found.name}) を配置")
                    
                    # 1年5組と2年5組にも同じ配置をする（5組同期）
                    for grade in [1, 2, 3]:
                        sync_class = ClassReference(grade, 5)
                        sync_assignment = Assignment(sync_class, subject, teacher_found)
                        schedule.assign(time_slot, sync_assignment)
                        print(f"  {grade}年5組に同期配置")
    except Exception as e:
        print(f"エラー: {e}")
    
    # 3年5組の水曜6限に数学を配置
    try:
        time_slot = TimeSlot("水", 6)
        class_ref = ClassReference(3, 5)
        
        # 標準時数から数学の科目オブジェクトを取得
        base_hours = school.get_all_standard_hours(class_ref)
        subject = None
        for subj, hours in base_hours.items():
            if subj.name == "数":
                subject = subj
                break
        
        if subject:
            # 数学の教師を探す（金子み先生を優先）
            teachers = list(school.get_subject_teachers(subject))
            teacher_found = None
            for teacher in teachers:
                if "金子み" in teacher.name:
                    teacher_found = teacher
                    break
            
            if not teacher_found and teachers:
                teacher_found = teachers[0]
            
            if teacher_found:
                # この時間に空いているかチェック
                is_available = True
                for c in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, c)
                    if assignment and assignment.teacher and assignment.teacher.name == teacher_found.name:
                        is_available = False
                        break
                
                if is_available:
                    print(f"3年5組 水曜6限に 数({teacher_found.name}) を配置")
                    
                    # 1年5組と2年5組にも同じ配置をする（5組同期）
                    for grade in [1, 2, 3]:
                        sync_class = ClassReference(grade, 5)
                        sync_assignment = Assignment(sync_class, subject, teacher_found)
                        schedule.assign(time_slot, sync_assignment)
                        print(f"  {grade}年5組に同期配置")
    except Exception as e:
        print(f"エラー: {e}")
    
    # 保存
    print("\n時間割を保存中...")
    csv_repo.save_schedule(schedule, "output.csv")
    print("完了！")

if __name__ == "__main__":
    main()