#!/usr/bin/env python3
"""5組の教師割り当てを修正するスクリプト"""
import sys
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
from src.infrastructure.repositories.schedule_io.csv_writer_improved import CSVScheduleWriterImproved
from src.domain.services.grade5_teacher_mapping_service import Grade5TeacherMappingService
from src.domain.value_objects.time_slot import Teacher
import csv

def fix_grade5_teachers():
    """5組の教師割り当てを修正"""
    # CSVを読み込み（教師情報も含めて）
    csv_reader = CSVScheduleReader()
    
    # 学校データを作成（教師情報を含めるため）
    from src.domain.entities.school import School
    school = School()
    
    # スケジュールを読み込み
    schedule = csv_reader.read("data/output/output.csv", school)
    
    # Grade5TeacherMappingServiceを初期化
    grade5_service = Grade5TeacherMappingService()
    
    # 修正カウント
    fixed_count = 0
    no_teacher_count = 0
    
    print("=== 5組の教師割り当てを修正 ===")
    print()
    
    # 全ての時間割をチェック
    days = ["月", "火", "水", "木", "金"]
    for day in days:
        for period in range(1, 7):
            from src.domain.value_objects.time_slot import TimeSlot
            time_slot = TimeSlot(day, period)
            
            # 5組のクラスをチェック
            for grade in [1, 2, 3]:
                from src.domain.value_objects.time_slot import ClassReference
                class_ref = ClassReference(grade, 5)
                
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject:
                    subject_name = assignment.subject.name
                    
                    # 正しい教師を取得
                    correct_teacher_name = grade5_service.get_teacher_for_subject(subject_name)
                    
                    if correct_teacher_name:
                        # 現在の教師をチェック
                        current_teacher_name = assignment.teacher.name if assignment.teacher else None
                        
                        if not assignment.teacher:
                            no_teacher_count += 1
                        
                        if current_teacher_name != correct_teacher_name:
                            # 教師を修正
                            correct_teacher = Teacher(correct_teacher_name)
                            assignment.teacher = correct_teacher
                            
                            print(f"{class_ref} {time_slot}: {subject_name} - 教師を{current_teacher_name or '未割当'}から{correct_teacher_name}に修正")
                            fixed_count += 1
    
    print(f"\n合計 {fixed_count} 件の教師割り当てを修正しました")
    print(f"教師未割当の授業: {no_teacher_count} 件")
    
    # 修正結果を保存
    if fixed_count > 0:
        csv_writer = CSVScheduleWriterImproved()
        csv_writer.write(schedule, None, "data/output/output_grade5_fixed.csv")
        print(f"\n修正結果を data/output/output_grade5_fixed.csv に保存しました")
        
        # 元のファイルも更新
        csv_writer.write(schedule, None, "data/output/output.csv")
        print(f"元のファイル data/output/output.csv も更新しました")
    
    return fixed_count

if __name__ == "__main__":
    fix_grade5_teachers()