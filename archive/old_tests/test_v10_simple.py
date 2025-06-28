#!/usr/bin/env python3
"""
Simple test to compare V10 and V10 Fixed teacher availability initialization
"""

import sys
import logging
from pathlib import Path
from collections import defaultdict

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.domain.entities.school import School
from src.domain.entities.schedule import Schedule
from src.domain.value_objects.time_slot import TimeSlot, Subject, Teacher, ClassReference
from src.domain.value_objects.assignment import Assignment

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_data():
    """テスト用のデータを作成"""
    # 学校データの作成
    school = School()
    
    # 教師を追加
    teachers = ["井野口", "金子ひ", "塚本", "野口", "永山", "白石", "森山", "北", "金子み"]
    for teacher_name in teachers:
        teacher = Teacher(teacher_name)
        school.add_teacher(teacher)
    
    # クラスを追加
    for grade in [1, 2, 3]:
        for class_num in [1, 2, 3, 5, 6, 7]:
            class_ref = ClassReference(grade, class_num)
            school.add_class(class_ref)
    
    # スケジュールの作成（教師情報なし）
    schedule = Schedule()
    
    # いくつかの授業を配置（教師情報なし）
    assignments = [
        # 通常授業
        (TimeSlot("月", 4), ClassReference(1, 1), Subject("国")),
        (TimeSlot("月", 4), ClassReference(1, 2), Subject("数")),
        (TimeSlot("月", 4), ClassReference(2, 1), Subject("英")),
        
        # 5組の合同授業
        (TimeSlot("月", 5), ClassReference(1, 5), Subject("日生")),
        (TimeSlot("月", 5), ClassReference(2, 5), Subject("日生")),
        (TimeSlot("月", 5), ClassReference(3, 5), Subject("日生")),
        
        # 火曜日の授業
        (TimeSlot("火", 4), ClassReference(1, 1), Subject("数")),
        (TimeSlot("火", 4), ClassReference(1, 2), Subject("英")),
        (TimeSlot("火", 5), ClassReference(2, 1), Subject("国")),
        
        # 固定科目
        (TimeSlot("月", 6), ClassReference(1, 1), Subject("欠")),
        (TimeSlot("火", 6), ClassReference(1, 1), Subject("YT")),
    ]
    
    for time_slot, class_ref, subject in assignments:
        # 教師なしで配置
        assignment = Assignment(class_ref=class_ref, subject=subject, teacher=None)
        schedule.assign(time_slot, assignment)
    
    # 教科ごとの担当教師を設定（シンプル版）
    subject_teacher_map = {
        "国": {"1-1": "井野口", "1-2": "梶永", "2-1": "塚本"},
        "数": {"1-1": "井野口", "1-2": "井野口", "2-1": "塚本"},
        "英": {"1-1": "梶永", "1-2": "梶永", "2-1": "野口"},
        "日生": {"1-5": "金子み", "2-5": "金子み", "3-5": "金子み"},
    }
    
    # schoolのget_assigned_teacherメソッドをモック
    def mock_get_assigned_teacher(subject_obj, class_ref):
        class_key = f"{class_ref.grade}-{class_ref.class_number}"
        subject_name = subject_obj.name
        
        if subject_name in subject_teacher_map:
            teacher_name = subject_teacher_map[subject_name].get(class_key)
            if teacher_name:
                return Teacher(teacher_name)
        return None
    
    school.get_assigned_teacher = mock_get_assigned_teacher
    
    return school, schedule


def test_v10_initialization():
    """V10とV10 Fixedの初期化を比較"""
    school, schedule = create_test_data()
    
    # V10の実装をシミュレート
    logger.info("\n=== V10 Original (Simulated) ===")
    v10_teacher_availability = {}
    
    # 全教師の全時間を利用可能として初期化
    for teacher in school.get_all_teachers():
        v10_teacher_availability[teacher.name] = set()
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                v10_teacher_availability[teacher.name].add((day, period))
    
    # V10では教師が検出されない（assignmentにteacherがないため）
    v10_busy_count = 0
    logger.info(f"V10: 既存教師配置数: {v10_busy_count}")
    
    # V10 Fixedの実装をシミュレート
    logger.info("\n=== V10 Fixed (Simulated) ===")
    v10_fixed_teacher_availability = {}
    
    # 全教師の全時間を利用可能として初期化
    for teacher in school.get_all_teachers():
        v10_fixed_teacher_availability[teacher.name] = set()
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                v10_fixed_teacher_availability[teacher.name].add((day, period))
    
    # V10 Fixedでは教師を推定して利用不可にマーク
    v10_fixed_busy_count = 0
    teacher_assignments = defaultdict(list)
    
    test_periods = {("月", 1), ("月", 2), ("月", 3), ("火", 1), ("火", 2), ("火", 3), ("水", 1), ("水", 2)}
    fixed_subjects = {"欠", "YT", "学", "学活", "道", "道徳", "総", "総合", "学総", "行", "行事", "テスト"}
    
    for time_slot, assignment in schedule.get_all_assignments():
        # 固定科目やテスト期間はスキップ
        if assignment.subject.name in fixed_subjects:
            continue
        if (time_slot.day, time_slot.period) in test_periods:
            continue
        
        # 教師を推定
        teacher = assignment.teacher
        if not teacher:
            teacher = school.get_assigned_teacher(assignment.subject, assignment.class_ref)
        
        if teacher and teacher.name in v10_fixed_teacher_availability:
            # 5組の合同授業をチェック
            if assignment.class_ref.class_number == 5:
                # 他の5組も同じ教師か確認（簡略化）
                grade5_count = sum(1 for t, a in schedule.get_all_assignments() 
                                  if t == time_slot and a.class_ref.class_number == 5)
                if grade5_count == 3:  # 3クラス合同
                    logger.debug(f"5組合同授業: {teacher.name}先生 @ {time_slot.day}{time_slot.period}限")
                    teacher_assignments[teacher.name].append((time_slot, "5組合同"))
                    continue
            
            # この時間帯を利用不可にマーク
            v10_fixed_teacher_availability[teacher.name].discard((time_slot.day, time_slot.period))
            v10_fixed_busy_count += 1
            teacher_assignments[teacher.name].append((time_slot, assignment.class_ref))
            logger.debug(f"既存配置: {teacher.name}先生 @ {time_slot.day}{time_slot.period}限 ({assignment.class_ref})")
    
    logger.info(f"V10 Fixed: 既存教師配置数: {v10_fixed_busy_count}")
    
    # 結果の比較
    logger.info("\n=== 比較結果 ===")
    logger.info(f"V10 Original - 検出された既存配置: 0")
    logger.info(f"V10 Fixed - 検出された既存配置: {v10_fixed_busy_count}")
    
    # 各教師の利用可能時間を比較
    for teacher_name in ["井野口", "金子み", "塚本", "野口", "梶永"]:
        if teacher_name in v10_teacher_availability and teacher_name in v10_fixed_teacher_availability:
            v10_available = len(v10_teacher_availability[teacher_name])
            v10_fixed_available = len(v10_fixed_teacher_availability[teacher_name])
            logger.info(f"{teacher_name}先生 - V10: {v10_available}スロット利用可能, V10 Fixed: {v10_fixed_available}スロット利用可能")
            
            if v10_available != v10_fixed_available:
                busy_slots = v10_teacher_availability[teacher_name] - v10_fixed_teacher_availability[teacher_name]
                logger.info(f"  → V10 Fixedで追加でbusyになったスロット: {len(busy_slots)}個")
                for day, period in sorted(busy_slots)[:3]:
                    logger.info(f"    - {day}{period}限")
    
    logger.info("\n=== まとめ ===")
    logger.info("V10の問題: input.csvに教師情報がないため、既存配置の教師を検出できない")
    logger.info("V10 Fixedの解決: school.get_assigned_teacherを使用して教師を推定し、正しく利用不可にマーク")


if __name__ == "__main__":
    test_v10_initialization()