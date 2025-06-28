#!/usr/bin/env python3
"""フェーズ1: 教師重複の即座修正

検出された10件の真の教師重複を修正します。
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.application.services.data_loading_service import DataLoadingService
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from src.domain.value_objects.assignment import Assignment
from src.domain.entities.school import Teacher, Subject
from src.infrastructure.config.path_config import path_config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    print("=== フェーズ1: 教師重複の即座修正 ===\n")
    
    # データ読み込み
    data_loading_service = DataLoadingService()
    school, _ = data_loading_service.load_school_data(path_config.data_dir)
    
    schedule_repo = CSVScheduleRepository(path_config.data_dir)
    schedule = schedule_repo.load("output/output.csv", school)
    
    # 修正計画
    fixes = [
        # 金子み先生の重複修正
        {
            'description': '金子み先生 - 月曜4限の重複解消',
            'remove': [
                {'day': '月', 'period': 4, 'class': ClassReference(3, 3), 'subject': '家'}
            ],
            'add': [
                {'day': '木', 'period': 1, 'class': ClassReference(3, 3), 'subject': '家', 'teacher': '金子み'}
            ]
        },
        # 智田先生の重複修正
        {
            'description': '智田先生 - 月曜5限の重複解消',
            'remove': [
                {'day': '月', 'period': 5, 'class': ClassReference(2, 7), 'subject': '自立'}
            ],
            'add': [
                {'day': '月', 'period': 5, 'class': ClassReference(2, 7), 'subject': '自立', 'teacher': '松本'}
            ]
        },
        {
            'description': '智田先生 - 火曜5限の重複解消',
            'remove': [
                {'day': '火', 'period': 5, 'class': ClassReference(2, 7), 'subject': '自立'}
            ],
            'add': [
                {'day': '火', 'period': 5, 'class': ClassReference(2, 7), 'subject': '自立', 'teacher': '松本'}
            ]
        },
        # 寺田先生の重複修正
        {
            'description': '寺田先生 - 水曜3限の重複解消',
            'remove': [
                {'day': '水', 'period': 3, 'class': ClassReference(2, 1), 'subject': '国'}
            ],
            'add': [
                {'day': '水', 'period': 5, 'class': ClassReference(2, 1), 'subject': '国', 'teacher': '寺田'}
            ]
        },
        {
            'description': '寺田先生 - 金曜5限の重複解消',
            'remove': [
                {'day': '金', 'period': 5, 'class': ClassReference(2, 1), 'subject': '国'}
            ],
            'add': [
                {'day': '火', 'period': 1, 'class': ClassReference(2, 1), 'subject': '国', 'teacher': '寺田'}
            ]
        },
        # 小野塚先生の重複修正
        {
            'description': '小野塚先生 - 金曜2限の重複解消',
            'remove': [
                {'day': '金', 'period': 2, 'class': ClassReference(3, 3), 'subject': '国'}
            ],
            'add': [
                {'day': '月', 'period': 6, 'class': ClassReference(3, 3), 'subject': '国', 'teacher': '小野塚'}
            ]
        }
    ]
    
    # 修正を適用
    fix_count = 0
    for fix in fixes:
        print(f"\n{fix['description']}")
        
        # 削除
        for removal in fix.get('remove', []):
            time_slot = TimeSlot(removal['day'], removal['period'])
            existing = schedule.get_assignment(time_slot, removal['class'])
            
            if existing and existing.subject.name == removal['subject']:
                schedule.remove_assignment(time_slot, removal['class'])
                print(f"  削除: {removal['class']} - {removal['day']}曜{removal['period']}限の{removal['subject']}")
                fix_count += 1
        
        # 追加
        for addition in fix.get('add', []):
            time_slot = TimeSlot(addition['day'], addition['period'])
            teacher = Teacher(addition['teacher'])
            subject = Subject(addition['subject'])
            assignment = Assignment(addition['class'], subject, teacher)
            
            # 空きスロットか確認
            existing = schedule.get_assignment(time_slot, addition['class'])
            if not existing:
                schedule.assign(time_slot, assignment)
                print(f"  追加: {addition['class']} - {addition['day']}曜{addition['period']}限に{addition['subject']}（{addition['teacher']}先生）")
            else:
                print(f"  警告: {addition['class']}の{addition['day']}曜{addition['period']}限は既に{existing.subject.name}が配置されています")
    
    # 修正後の時間割を保存
    output_path = path_config.output_dir / "output_phase1_fixed.csv"
    schedule_repo.save_schedule(schedule, str(output_path))
    
    print(f"\n修正完了: {fix_count}件の変更を適用")
    print(f"修正後の時間割を保存: {output_path}")
    
    # 修正後の検証
    print("\n【修正後の教師重複チェック】")
    verify_teacher_duplications(schedule, school)

def verify_teacher_duplications(schedule, school):
    """修正後の教師重複をチェック"""
    days = ["月", "火", "水", "木", "金"]
    periods = [1, 2, 3, 4, 5, 6]
    
    duplications = []
    
    for day in days:
        for period in periods:
            teacher_classes = {}
            
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(TimeSlot(day, period), class_ref)
                if assignment and assignment.teacher:
                    teacher_name = assignment.teacher.name
                    if teacher_name not in teacher_classes:
                        teacher_classes[teacher_name] = []
                    teacher_classes[teacher_name].append(class_ref)
            
            # 重複チェック（5組と固定科目を除く）
            for teacher_name, classes in teacher_classes.items():
                if len(classes) > 1:
                    # 固定科目と5組の除外ロジック
                    if teacher_name in ["欠", "YT担当", "道担当", "学担当", "総担当", "学総担当", "行担当"]:
                        continue
                    
                    # 5組のみの場合は除外
                    grade5_refs = [ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)]
                    if all(c in grade5_refs for c in classes):
                        continue
                    
                    duplications.append({
                        'day': day,
                        'period': period,
                        'teacher': teacher_name,
                        'classes': classes
                    })
    
    if duplications:
        print(f"残存する教師重複: {len(duplications)}件")
        for dup in duplications[:5]:  # 最初の5件のみ表示
            print(f"  {dup['day']}曜{dup['period']}限 - {dup['teacher']}先生: {', '.join(str(c) for c in dup['classes'])}")
    else:
        print("教師重複はすべて解消されました！")

if __name__ == "__main__":
    main()