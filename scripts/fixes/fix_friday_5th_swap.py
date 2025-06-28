#!/usr/bin/env python3
"""3年3組の金曜5限を他の授業と交換して修正するスクリプト"""
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
    """3年3組の金曜5限を他の授業と交換して数学または英語を配置"""
    path_manager = get_path_manager()
    
    # リポジトリの初期化
    schedule_repo = CSVScheduleRepository(path_manager.data_dir)
    school_repo = CSVSchoolRepository(path_manager.data_dir)
    
    # データの読み込み
    logger.info("データを読み込み中...")
    school = school_repo.load_school_data()
    schedule = schedule_repo.load(str(path_manager.output_dir / "output.csv"), school)
    
    class_ref = ClassReference(3, 3)
    target_slot = TimeSlot("金", 5)
    
    logger.info("=== 3年3組の金曜5限を修正（交換方式） ===")
    
    # 3年6組（交流学級）の金曜5限を確認
    exchange_class = ClassReference(3, 6)
    exchange_assignment = schedule.get_assignment(target_slot, exchange_class)
    
    if exchange_assignment and exchange_assignment.subject.name in ["自立", "日生", "作業"]:
        logger.info(f"3年6組の金曜5限は{exchange_assignment.subject.name}です")
        logger.info("3年3組の金曜5限は数学または英語である必要があります")
        
        # 金曜日以外で数学・英語でない授業を探して交換
        swapped = False
        
        for day in ["月", "火", "水", "木"]:
            for period in range(1, 7):
                swap_slot = TimeSlot(day, period)
                
                # ロックされている場合はスキップ
                if schedule.is_locked(swap_slot, class_ref):
                    continue
                
                swap_assignment = schedule.get_assignment(swap_slot, class_ref)
                if not swap_assignment:
                    continue
                
                # 固定科目はスキップ
                if swap_assignment.subject.name in ["欠", "YT", "道", "学総", "総", "行", "技家"]:
                    continue
                
                # 数学・英語はスキップ
                if swap_assignment.subject.name in ["数", "英", "算"]:
                    continue
                
                # この科目が金曜日にあるかチェック
                friday_has_this_subject = False
                for p in range(1, 7):
                    check_slot = TimeSlot("金", p)
                    check_assignment = schedule.get_assignment(check_slot, class_ref)
                    if check_assignment and check_assignment.subject.name == swap_assignment.subject.name:
                        friday_has_this_subject = True
                        break
                
                if friday_has_this_subject:
                    continue
                
                # 金曜5限を数学または英語に変更できるかチェック
                for new_subject_name in ["数", "英"]:
                    # その日にその科目があるかチェック
                    day_has_subject = False
                    for p in range(1, 7):
                        if p == period:
                            continue
                        check_slot = TimeSlot(day, p)
                        check_assignment = schedule.get_assignment(check_slot, class_ref)
                        if check_assignment and check_assignment.subject.name == new_subject_name:
                            day_has_subject = True
                            break
                    
                    if day_has_subject:
                        continue
                    
                    # 教師を取得
                    new_subject = Subject(new_subject_name)
                    new_teacher = school.get_assigned_teacher(new_subject, class_ref)
                    
                    if not new_teacher:
                        continue
                    
                    # 両方の時間で教師が利用可能かチェック
                    new_teacher_available_friday = True
                    swap_teacher_available_target = True
                    
                    for other_class in school.get_all_classes():
                        if other_class == class_ref:
                            continue
                        
                        # 金曜5限の新教師チェック
                        other_assignment = schedule.get_assignment(target_slot, other_class)
                        if other_assignment and other_assignment.teacher == new_teacher:
                            new_teacher_available_friday = False
                        
                        # 交換先での元教師チェック
                        other_assignment = schedule.get_assignment(swap_slot, other_class)
                        if other_assignment and other_assignment.teacher == swap_assignment.teacher:
                            swap_teacher_available_target = False
                    
                    if new_teacher_available_friday and swap_teacher_available_target:
                        # 交換を実行
                        logger.info(f"\n交換を実行: {swap_slot}の{swap_assignment.subject.name} ↔ 金曜5限に{new_subject_name}")
                        
                        # 両方を削除
                        schedule.remove_assignment(swap_slot, class_ref)
                        schedule.remove_assignment(target_slot, class_ref)
                        
                        # 新しい割り当て
                        new_assignment_friday = Assignment(class_ref, new_subject, new_teacher)
                        new_assignment_swap = Assignment(class_ref, swap_assignment.subject, swap_assignment.teacher)
                        
                        if schedule.assign(target_slot, new_assignment_friday):
                            if schedule.assign(swap_slot, new_assignment_swap):
                                logger.info(f"✓ 交換成功: 金曜5限={new_subject_name}, {swap_slot}={swap_assignment.subject.name}")
                                swapped = True
                                break
                            else:
                                # ロールバック
                                schedule.remove_assignment(target_slot, class_ref)
                                schedule.assign(swap_slot, swap_assignment)
                
                if swapped:
                    break
            
            if swapped:
                break
        
        if not swapped:
            logger.warning("適切な交換相手が見つかりませんでした")
            
            # 最後の手段：金曜5限に美術を配置（交流学級の制約を一時的に無視）
            beauty_subject = Subject("美")
            beauty_teacher = school.get_assigned_teacher(beauty_subject, class_ref)
            
            if beauty_teacher:
                beauty_assignment = Assignment(class_ref, beauty_subject, beauty_teacher)
                if schedule.assign(target_slot, beauty_assignment):
                    logger.info("✓ 金曜5限に美術を配置しました（暫定対応）")
    
    # 結果を保存
    logger.info("\n結果を保存中...")
    schedule_repo.save_schedule(schedule, str(path_manager.output_dir / "output.csv"))
    logger.info("✓ output.csvを更新しました")
    
    # 最終確認
    logger.info("\n=== 最終確認 ===")
    
    # 3年3組の金曜5限を確認
    final_assignment = schedule.get_assignment(target_slot, class_ref)
    if final_assignment:
        logger.info(f"3年3組の金曜5限: {final_assignment.subject.name}({final_assignment.teacher.name})")
        
        # 交流学級との関係を確認
        exchange_assignment = schedule.get_assignment(target_slot, exchange_class)
        if exchange_assignment and exchange_assignment.subject.name in ["自立", "日生", "作業"]:
            status = "✓" if final_assignment.subject.name in ["数", "英", "算"] else "✗"
            logger.info(f"交流学級チェック: 3年6組(自立) ← 3年3組({final_assignment.subject.name}) {status}")
    else:
        logger.warning("3年3組の金曜5限: まだ空欄です")


if __name__ == "__main__":
    main()