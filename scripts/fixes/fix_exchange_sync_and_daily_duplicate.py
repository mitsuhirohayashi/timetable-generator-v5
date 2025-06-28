#!/usr/bin/env python3
"""交流学級同期違反と日内重複違反を修正するスクリプト

問題：
1. 3年6組（交流学級）が親学級（3年3組）と同期していない
   - 火曜5限: 3-3は「美」、3-6は「保」
   - 木曜2限: 3-3は「保」、3-6は空欄
   - 金曜5限: 3-3は「保」、3-6は空欄

2. 3年3組の月曜に英語が2回（4限と6限）配置されている
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.repositories.config_repository import ConfigRepository
from src.domain.value_objects.time_slot import TimeSlot
from src.shared.utils.csv_operations import CSVOperations


def fix_violations(input_path: str, output_path: str):
    """時間割の違反を修正"""
    print("=== 交流学級同期違反と日内重複違反の修正 ===")
    
    # 1. データ読み込み
    reader = CSVScheduleReader(CSVRepository())
    schedule = reader.read(input_path)
    
    # 設定読み込み
    config_repo = ConfigRepository()
    basics_data = config_repo.load_basics()
    
    basics_parser = BasicsParser()
    constraints_config = basics_parser.parse(basics_data)
    
    # 教師マッピング読み込み
    teacher_repo = TeacherMappingRepository(config_repo.config_dir)
    teacher_mapping = teacher_repo.load_teacher_mapping()
    
    # 学校エンティティ作成
    csv_repo = CSVRepository()
    base_timetable = csv_repo.read("data/config/base_timetable.csv")
    school = School.from_base_timetable(base_timetable, teacher_mapping)
    
    # ExchangeClassService作成
    exchange_service = ExchangeClassService()
    
    print("\n修正対象の違反:")
    
    # 2. 交流学級同期違反の修正
    print("\n■ 交流学級同期違反の修正")
    
    # 3-6と3-3の同期修正
    violations = [
        ("火", 5, "3年6組", "3年3組"),  # 3-6:保, 3-3:美
        ("木", 2, "3年6組", "3年3組"),  # 3-6:空, 3-3:保
        ("金", 5, "3年6組", "3年3組"),  # 3-6:空, 3-3:保
    ]
    
    for day, period, exchange_class, parent_class in violations:
        time_slot = TimeSlot(day, period)
        parent_assignment = schedule.get_assignment(time_slot, parent_class)
        exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
        
        print(f"\n{time_slot.format()} - {exchange_class}と{parent_class}の同期:")
        print(f"  現在: {parent_class}={parent_assignment.subject.name if parent_assignment else '空'}, "
              f"{exchange_class}={exchange_assignment.subject.name if exchange_assignment else '空'}")
        
        # 親学級に合わせて交流学級を修正
        if parent_assignment:
            # 交流学級の現在の授業を削除
            if exchange_assignment:
                schedule.remove_assignment(time_slot, exchange_class)
            
            # 親学級と同じ科目・教師を配置
            schedule.assign(
                time_slot=time_slot,
                class_ref=exchange_class,
                subject=parent_assignment.subject,
                teacher=parent_assignment.teacher
            )
            print(f"  修正: {exchange_class}を{parent_assignment.subject.name}に変更")
        else:
            # 親学級が空の場合、交流学級も空にする
            if exchange_assignment:
                schedule.remove_assignment(time_slot, exchange_class)
                print(f"  修正: {exchange_class}を空に変更")
    
    # 3. 日内重複違反の修正（3-3の月曜）
    print("\n■ 日内重複違反の修正")
    print("\n3年3組の月曜日の英語重複を修正:")
    
    # 月曜の全時限をチェック
    monday_assignments = []
    for period in range(1, 7):
        time_slot = TimeSlot("月", period)
        assignment = schedule.get_assignment(time_slot, "3年3組")
        if assignment:
            monday_assignments.append((period, assignment))
            print(f"  {period}限: {assignment.subject.name}")
    
    # 英語の重複を確認
    english_periods = [(p, a) for p, a in monday_assignments if a.subject.name == "英"]
    if len(english_periods) > 1:
        print(f"\n  英語が{len(english_periods)}回配置されています（{', '.join([f'{p}限' for p, _ in english_periods])}）")
        
        # 6限の英語を他の科目に変更（3年生は月曜6限も通常授業可能）
        time_slot_6 = TimeSlot("月", 6)
        
        # 利用可能な科目を探す（その日に配置されていない科目）
        used_subjects = {a.subject.name for _, a in monday_assignments}
        available_subjects = ["国", "数", "理", "社", "音", "美", "保", "技", "家"]
        available_subjects = [s for s in available_subjects if s not in used_subjects]
        
        if available_subjects:
            # 最初の利用可能な科目を選択（ここでは「国」を優先）
            new_subject_name = available_subjects[0]
            
            # 対応する教師を探す
            new_teacher = None
            for teacher_name, mappings in teacher_mapping.items():
                for mapping in mappings:
                    if (mapping["subject"] == new_subject_name and 
                        mapping["grade"] == 3 and 
                        mapping["class_num"] == 3):
                        new_teacher = teacher_name
                        break
                if new_teacher:
                    break
            
            if new_teacher:
                # 既存の割り当てを削除
                schedule.remove_assignment(time_slot_6, "3年3組")
                
                # 新しい科目を配置
                subject = school.get_subject(new_subject_name)
                teacher = school.get_teacher(new_teacher)
                
                schedule.assign(
                    time_slot=time_slot_6,
                    class_ref="3年3組",
                    subject=subject,
                    teacher=teacher
                )
                
                print(f"  修正: 6限の英語を{new_subject_name}（{new_teacher}先生）に変更")
    
    # 4. ファイル出力
    writer = CSVScheduleWriterImproved(CSVRepository())
    writer.write(schedule, output_path)
    
    print(f"\n修正完了！結果を {output_path} に保存しました。")
    print("\n※ 制約違反チェックを実行して確認してください:")
    print("  python3 check_violations.py")


if __name__ == "__main__":
    fix_violations(
        input_path="data/output/output.csv",
        output_path="data/output/output_fixed.csv"
    )