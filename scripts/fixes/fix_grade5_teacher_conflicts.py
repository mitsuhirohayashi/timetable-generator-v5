#!/usr/bin/env python3
"""5組の教師と競合する通常クラスの授業を修正"""
import sys
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
from src.infrastructure.repositories.schedule_io.csv_writer_improved import CSVScheduleWriterImproved
from src.domain.services.grade5_teacher_mapping_service import Grade5TeacherMappingService
from src.domain.value_objects.time_slot import Teacher, TimeSlot, ClassReference
from src.domain.value_objects.assignment import Assignment
from src.domain.value_objects.time_slot import Subject


class Grade5TeacherConflictFixer:
    def __init__(self):
        self.conflicts = []
        self.solutions = []
    
    def fix_conflicts(self):
        """5組の教師競合を修正"""
        
        # CSVを読み込み
        csv_reader = CSVScheduleReader()
        from src.domain.entities.school import School
        school = School()
        schedule = csv_reader.read("data/output/output.csv", school)
        
        # Grade5TeacherMappingService
        grade5_service = Grade5TeacherMappingService()
        
        print("=== 5組の教師競合を修正 ===")
        print()
        
        # 競合している授業を特定
        conflicts = []
        
        # 火曜4限の数学（梶永先生）
        conflicts.append({
            'time': TimeSlot("火", 4),
            'grade5_subject': '数',
            'grade5_teacher': '梶永',
            'conflict_class': ClassReference(1, 1),
            'conflict_subject': '数'
        })
        
        # 水曜4限の数学（梶永先生）
        conflicts.append({
            'time': TimeSlot("水", 4),
            'grade5_subject': '数',
            'grade5_teacher': '梶永',
            'conflict_class': ClassReference(1, 3),
            'conflict_subject': '数'
        })
        
        # 木曜6限の国語（寺田先生）
        conflicts.append({
            'time': TimeSlot("木", 6),
            'grade5_subject': '国',
            'grade5_teacher': '寺田',
            'conflict_class': ClassReference(1, 2),
            'conflict_subject': '国'
        })
        
        # 金曜5限の美術（金子み先生）
        conflicts.append({
            'time': TimeSlot("金", 5),
            'grade5_subject': '美',
            'grade5_teacher': '金子み',
            'conflict_class': ClassReference(1, 2),
            'conflict_subject': '美'
        })
        
        # 修正カウント
        fixed_count = 0
        
        for conflict in conflicts:
            time_slot = conflict['time']
            conflict_class = conflict['conflict_class']
            
            print(f"\n{time_slot}: {conflict_class} の {conflict['conflict_subject']} が5組と競合")
            
            # 通常クラスの授業を空にする（後で他の教科で埋める）
            try:
                # 既存の割り当てを削除
                existing = schedule.get_assignment(time_slot, conflict_class)
                if existing:
                    # まず削除
                    schedule._assignments.pop((time_slot, conflict_class), None)
                    print(f"  → {conflict_class} の授業を一時的に削除")
                    fixed_count += 1
            except Exception as e:
                print(f"  → エラー: {e}")
            
            # 5組に正しい教師を割り当て
            for grade in [1, 2, 3]:
                class_ref = ClassReference(grade, 5)
                existing_5 = schedule.get_assignment(time_slot, class_ref)
                
                if existing_5 and existing_5.subject:
                    # 教師が未割当または間違っている場合
                    if not existing_5.teacher or existing_5.teacher.name != conflict['grade5_teacher']:
                        correct_teacher = Teacher(conflict['grade5_teacher'])
                        existing_5.teacher = correct_teacher
                        print(f"  → {class_ref} に {conflict['grade5_teacher']} 先生を割り当て")
        
        print(f"\n合計 {fixed_count} 件の競合を修正しました")
        
        # 修正結果を保存
        if fixed_count > 0:
            from pathlib import Path
            csv_writer = CSVScheduleWriterImproved(school=school)
            csv_writer.write(schedule, Path("data/output/output_conflicts_fixed.csv"))
            print(f"\n修正結果を data/output/output_conflicts_fixed.csv に保存しました")
            
            # 元のファイルも更新
            csv_writer.write(schedule, Path("data/output/output.csv"))
            print(f"元のファイル data/output/output.csv も更新しました")
        
        return fixed_count


if __name__ == "__main__":
    fixer = Grade5TeacherConflictFixer()
    fixer.fix_conflicts()