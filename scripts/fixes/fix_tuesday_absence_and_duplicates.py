#!/usr/bin/env python3
"""火曜日の蒲地先生不在問題と3年3組の日内重複を修正するスクリプト"""
import sys
import os
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from src.domain.value_objects.assignment import Assignment
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.config.path_manager import get_path_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """火曜日の蒲地先生不在と3年3組の日内重複を修正"""
    path_manager = get_path_manager()
    
    # リポジトリの初期化
    schedule_repo = CSVScheduleRepository(path_manager.data_dir)
    school_repo = CSVSchoolRepository(path_manager.data_dir)
    
    # データの読み込み
    logger.info("データを読み込み中...")
    school = school_repo.load_school_data()
    schedule = schedule_repo.load(str(path_manager.output_dir / "output.csv"), school)
    
    # 問題1: 蒲地先生の火曜5・6限の授業を確認し修正
    logger.info("\n=== 問題1: 蒲地先生の火曜5・6限不在問題 ===")
    
    # 蒲地先生が担当するクラス
    kamachi_classes = [
        ClassReference(1, 1), ClassReference(1, 3), ClassReference(1, 5),
        ClassReference(2, 1), ClassReference(2, 2), ClassReference(2, 3), 
        ClassReference(2, 5), ClassReference(3, 5)
    ]
    
    violations_found = []
    
    # 火曜5限と6限をチェック
    for period in [5, 6]:
        time_slot = TimeSlot("火", period)
        
        for class_ref in kamachi_classes:
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.teacher.name == "蒲地":
                violations_found.append({
                    'time_slot': time_slot,
                    'class_ref': class_ref,
                    'subject': assignment.subject,
                    'teacher': assignment.teacher
                })
                logger.info(f"違反発見: {class_ref.full_name} {time_slot} - 社会(蒲地)")
    
    # 蒲地先生の授業を他の時間に移動
    for violation in violations_found:
        time_slot = violation['time_slot']
        class_ref = violation['class_ref']
        
        # 空いている時間を探す（火曜以外の日）
        moved = False
        for day in ["月", "水", "木", "金"]:
            for period in range(1, 7):
                new_time_slot = TimeSlot(day, period)
                
                # 既に授業がある場合はスキップ
                if schedule.get_assignment(new_time_slot, class_ref):
                    continue
                
                # ロックされている場合はスキップ
                if schedule.is_locked(new_time_slot, class_ref):
                    continue
                
                # その時間に蒲地先生が空いているか確認
                teacher_available = True
                for other_class in school.get_all_classes():
                    other_assignment = schedule.get_assignment(new_time_slot, other_class)
                    if other_assignment and other_assignment.teacher.name == "蒲地":
                        teacher_available = False
                        break
                
                if teacher_available:
                    # 元の授業を削除
                    schedule.remove_assignment(time_slot, class_ref)
                    
                    # 新しい時間に配置
                    new_assignment = Assignment(class_ref, violation['subject'], violation['teacher'])
                    if schedule.assign(new_time_slot, new_assignment):
                        logger.info(f"✓ {class_ref.full_name}: {time_slot} → {new_time_slot}に移動")
                        moved = True
                        break
            
            if moved:
                break
        
        if not moved:
            logger.warning(f"✗ {class_ref.full_name}の社会を移動できる空き時間が見つかりません")
    
    # 問題2: 3年3組の日内重複を修正
    logger.info("\n=== 問題2: 3年3組の日内重複問題 ===")
    
    class_ref = ClassReference(3, 3)
    
    # 木曜日の数学重複を修正（2限と5限）
    logger.info("\n木曜日の数学重複を修正...")
    thu_5_assignment = schedule.get_assignment(TimeSlot("木", 5), class_ref)
    
    if thu_5_assignment and thu_5_assignment.subject.name == "数":
        # 木曜5限の数学を他の科目に変更
        schedule.remove_assignment(TimeSlot("木", 5), class_ref)
        
        # 不足している科目を探す
        subject_counts = {}
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                ts = TimeSlot(day, period)
                assignment = schedule.get_assignment(ts, class_ref)
                if assignment:
                    subject_name = assignment.subject.name
                    if subject_name not in ["欠", "YT", "道", "学総", "総", "行"]:
                        subject_counts[subject_name] = subject_counts.get(subject_name, 0) + 1
        
        # 不足している科目を配置（国語、理科、英語など）
        for subject_name in ["国", "理", "英", "保"]:
            subject = Subject(subject_name)
            teacher = school.get_assigned_teacher(subject, class_ref)
            
            if teacher:
                # 教師が利用可能か確認
                teacher_available = True
                for other_class in school.get_all_classes():
                    other_assignment = schedule.get_assignment(TimeSlot("木", 5), other_class)
                    if other_assignment and other_assignment.teacher == teacher:
                        teacher_available = False
                        break
                
                if teacher_available:
                    new_assignment = Assignment(class_ref, subject, teacher)
                    if schedule.assign(TimeSlot("木", 5), new_assignment):
                        logger.info(f"✓ 木曜5限: 数 → {subject_name}({teacher.name})")
                        break
    
    # 金曜日の数学重複を修正（3限と5限）
    logger.info("\n金曜日の数学重複を修正...")
    fri_5_assignment = schedule.get_assignment(TimeSlot("金", 5), class_ref)
    
    if fri_5_assignment and fri_5_assignment.subject.name == "数":
        # 金曜5限の数学を他の科目に変更
        schedule.remove_assignment(TimeSlot("金", 5), class_ref)
        
        # 不足している科目を配置
        for subject_name in ["理", "国", "英", "美"]:
            subject = Subject(subject_name)
            teacher = school.get_assigned_teacher(subject, class_ref)
            
            if teacher:
                # 教師が利用可能か確認
                teacher_available = True
                for other_class in school.get_all_classes():
                    other_assignment = schedule.get_assignment(TimeSlot("金", 5), other_class)
                    if other_assignment and other_assignment.teacher == teacher:
                        teacher_available = False
                        break
                
                if teacher_available:
                    new_assignment = Assignment(class_ref, subject, teacher)
                    if schedule.assign(TimeSlot("金", 5), new_assignment):
                        logger.info(f"✓ 金曜5限: 数 → {subject_name}({teacher.name})")
                        break
    
    # 結果を保存
    logger.info("\n結果を保存中...")
    schedule_repo.save_schedule(schedule, str(path_manager.output_dir / "output.csv"))
    logger.info("✓ output.csvを更新しました")
    
    # 修正後の確認
    logger.info("\n=== 修正後の確認 ===")
    
    # 蒲地先生の火曜5・6限を確認
    logger.info("\n蒲地先生の火曜5・6限:")
    for period in [5, 6]:
        time_slot = TimeSlot("火", period)
        kamachi_found = False
        for class_ref in kamachi_classes:
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.teacher.name == "蒲地":
                kamachi_found = True
                logger.warning(f"  {time_slot} {class_ref.full_name}: 社会(蒲地) - まだ残っています!")
        if not kamachi_found:
            logger.info(f"  {time_slot}: 蒲地先生の授業なし ✓")
    
    # 3年3組の日内重複を確認
    logger.info("\n3年3組の日内科目配置:")
    for day in ["木", "金"]:
        logger.info(f"\n{day}曜日:")
        day_subjects = {}
        for period in range(1, 7):
            ts = TimeSlot(day, period)
            assignment = schedule.get_assignment(ts, ClassReference(3, 3))
            if assignment:
                subject_name = assignment.subject.name
                logger.info(f"  {period}限: {subject_name}")
                if subject_name not in ["欠", "YT", "道", "学総", "総", "行"]:
                    day_subjects[subject_name] = day_subjects.get(subject_name, 0) + 1
        
        # 重複をチェック
        for subject, count in day_subjects.items():
            if count > 1:
                logger.warning(f"  → {subject}が{count}回 - 日内重複!")
            else:
                logger.info(f"  → {subject}: {count}回 ✓")


if __name__ == "__main__":
    main()