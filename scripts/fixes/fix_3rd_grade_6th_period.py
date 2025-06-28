#!/usr/bin/env python3
"""3年生の月曜・火曜・水曜6限を埋めるスクリプト"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from src.infrastructure.repositories import CSVScheduleRepository as CSVRepository
from src.domain.entities.school import School
from src.domain.entities.schedule import Schedule
from src.infrastructure.config.logging_config import LoggingConfig
from src.domain.constraints.teacher_conflict_constraint_refactored import TeacherConflictConstraint
from src.domain.constraints.daily_duplicate_constraint import DailyDuplicateConstraint
from src.domain.constraints.base import ConstraintType

LoggingConfig.setup(production=True)

def main():
    print("=== 3年生の月曜・火曜・水曜6限を埋める ===\n")
    
    # データ読み込み
    repo = CSVRepository()
    school = repo.load_school_data()
    schedule = repo.load_schedule("data/output/output.csv")
    
    # 制約の設定
    teacher_constraint = TeacherConflictConstraint(ConstraintType.CRITICAL)
    daily_duplicate_constraint = DailyDuplicateConstraint(ConstraintType.CRITICAL)
    
    # 3年生の担任教師マッピング
    homeroom_teachers = {
        "3年1組": "白石",
        "3年2組": "森山",
        "3年3組": "北",
        "3年5組": "金子み",
        "3年6組": "北",  # 3年3組と同じ担任
        "3年7組": "森山"  # 3年2組と同じ担任
    }
    
    # 3年生の月曜・火曜・水曜6限を埋める
    days_to_fill = ["月", "火", "水"]
    third_grade_classes = ["3年1組", "3年2組", "3年3組", "3年5組", "3年6組", "3年7組"]
    
    changes_made = []
    
    for day in days_to_fill:
        for class_name in third_grade_classes:
            slot = schedule.get_slot(day, 6, class_name)
            
            # 空きスロットの場合のみ処理
            if not slot or not slot.subject:
                teacher_name = homeroom_teachers.get(class_name)
                
                # 担任が担当できる科目を決定
                # 月曜6限は社会、火曜6限は道徳、水曜6限は学総を優先
                if day == "月":
                    subject = "社"
                elif day == "火":
                    subject = "道"
                else:  # 水曜
                    subject = "学総"
                
                # 既に同じ日に同じ科目がないかチェック
                day_subjects = []
                for period in range(1, 7):
                    s = schedule.get_slot(day, period, class_name)
                    if s and s.subject:
                        day_subjects.append(s.subject)
                
                # 日内重複を避ける
                if subject in day_subjects:
                    # 代替科目を選択
                    alternatives = ["総", "学活", "国", "数", "英", "理", "社"]
                    for alt in alternatives:
                        if alt not in day_subjects:
                            subject = alt
                            break
                
                # 教師重複チェック
                can_assign = True
                for other_class in third_grade_classes:
                    if other_class != class_name:
                        other_slot = schedule.get_slot(day, 6, other_class)
                        if other_slot and other_slot.teacher == teacher_name:
                            can_assign = False
                            break
                
                if can_assign:
                    try:
                        # 科目を配置
                        schedule.assign(day, 6, class_name, subject, teacher_name)
                        changes_made.append(f"{day}曜6限 {class_name}: {subject} ({teacher_name}先生)")
                        print(f"✓ {day}曜6限 {class_name}: {subject}を配置 ({teacher_name}先生)")
                    except Exception as e:
                        print(f"✗ {day}曜6限 {class_name}: 配置失敗 - {e}")
    
    # 月曜5限の社会の教師重複も修正
    print("\n=== 月曜5限の教師重複を修正 ===")
    
    # 3-2と3-3の月曜5限の社会を確認
    slot_3_2 = schedule.get_slot("月", 5, "3年2組")
    slot_3_3 = schedule.get_slot("月", 5, "3年3組")
    
    if slot_3_2 and slot_3_3 and slot_3_2.subject == "社" and slot_3_3.subject == "社":
        # 同じ教師が担当している場合、片方を変更
        if slot_3_2.teacher == slot_3_3.teacher:
            print(f"月曜5限: 3年2組と3年3組で同じ教師({slot_3_2.teacher})が社会を担当")
            
            # 3年3組の社会を別の科目に変更
            # その日にまだない科目を探す
            day_subjects_3_3 = []
            for period in range(1, 7):
                s = schedule.get_slot("月", period, "3年3組")
                if s and s.subject and period != 5:
                    day_subjects_3_3.append(s.subject)
            
            # 代替科目を選択
            alternatives = ["英", "数", "国", "理", "美", "音", "技", "家"]
            for alt in alternatives:
                if alt not in day_subjects_3_3:
                    try:
                        # 適切な教師を探す
                        teacher = None
                        if alt == "英":
                            teacher = "箱崎"
                        elif alt == "数":
                            teacher = "井上"
                        elif alt == "国":
                            teacher = "伊藤"
                        elif alt == "理":
                            teacher = "白石"
                        else:
                            teacher = "北"  # 担任
                        
                        schedule.assign("月", 5, "3年3組", alt, teacher)
                        changes_made.append(f"月曜5限 3年3組: 社 → {alt} ({teacher}先生)")
                        print(f"✓ 月曜5限 3年3組: 社 → {alt}に変更 ({teacher}先生)")
                        break
                    except Exception as e:
                        continue
    
    # 変更を保存
    if changes_made:
        print(f"\n=== 変更内容 ({len(changes_made)}件) ===")
        for change in changes_made:
            print(f"  • {change}")
        
        # 保存
        repo.save_schedule(schedule, "data/output/output.csv")
        print("\n✓ 変更を保存しました")
    else:
        print("\n変更はありませんでした")

if __name__ == "__main__":
    main()