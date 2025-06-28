#!/usr/bin/env python3
"""5組の水曜4限を優先的に埋めるスクリプト

5組（1-5, 2-5, 3-5）の水曜4限が全て空きになっている問題を解決します。
その他の空きコマも含めて、優先順位を付けて埋めます。
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import logging
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
from src.infrastructure.config.constraint_loader import ConstraintLoader
from src.domain.services.unified_constraint_system import UnifiedConstraintSystem
from src.domain.services.smart_empty_slot_filler import SmartEmptySlotFiller
from src.domain.services.grade5_synchronizer_refactored import RefactoredGrade5Synchronizer
from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from src.domain.value_objects.assignment import Assignment
from src.domain.entities.school import Subject
from src.domain.utils.schedule_utils import ScheduleUtils

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def analyze_empty_slots(schedule, school):
    """空きスロットを分析"""
    empty_slots = {
        'grade5_wed4': [],
        'grade3_6th': [],
        'other': []
    }
    
    days = ["月", "火", "水", "木", "金"]
    for day in days:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            for class_ref in school.get_all_classes():
                # 特別な空きコマはスキップ
                if should_skip_slot(time_slot, class_ref):
                    continue
                
                # 既に割り当てがある場合はスキップ
                if schedule.get_assignment(time_slot, class_ref):
                    continue
                
                # ロックされている場合はスキップ
                if schedule.is_locked(time_slot, class_ref):
                    continue
                
                # 分類
                if class_ref.grade in [1, 2, 3] and class_ref.class_num == 5 and day == "水" and period == 4:
                    empty_slots['grade5_wed4'].append((time_slot, class_ref))
                elif class_ref.grade == 3 and period == 6:
                    empty_slots['grade3_6th'].append((time_slot, class_ref))
                else:
                    empty_slots['other'].append((time_slot, class_ref))
    
    return empty_slots


def should_skip_slot(time_slot, class_ref):
    """スキップすべきスロットかチェック"""
    # 3年生の特別ルール
    if class_ref.grade == 3:
        # 金曜6限のYTのみスキップ
        if time_slot.day == "金" and time_slot.period == 6:
            return True
        return False
    
    # 1・2年生のルール
    # 月曜6限（欠）
    if time_slot.day == "月" and time_slot.period == 6:
        return True
    
    # 火曜・水曜・金曜の6限（YT）
    if ((time_slot.day == "火" and time_slot.period == 6) or
        (time_slot.day == "水" and time_slot.period == 6) or
        (time_slot.day == "金" and time_slot.period == 6)):
        return True
    
    return False


def fix_grade5_wednesday_4th(schedule, school, synchronizer):
    """5組の水曜4限を修正"""
    logger.info("=== 5組の水曜4限を修正 ===")
    
    wed4_slot = TimeSlot("水", 4)
    
    # 現在の状態を確認
    grade5_classes = [
        ClassReference(1, 5),
        ClassReference(2, 5),
        ClassReference(3, 5)
    ]
    
    empty_count = 0
    for class_ref in grade5_classes:
        assignment = schedule.get_assignment(wed4_slot, class_ref)
        if not assignment:
            empty_count += 1
            logger.info(f"{class_ref}の水曜4限: 空き")
        else:
            logger.info(f"{class_ref}の水曜4限: {assignment.subject.name}({assignment.teacher.name})")
    
    if empty_count == 0:
        logger.info("5組の水曜4限は既に埋まっています")
        return 0
    
    # ensure_grade5_syncを使って同期的に埋める
    if synchronizer.ensure_grade5_sync(schedule, school, wed4_slot):
        logger.info("5組の水曜4限を同期的に埋めました")
        return empty_count
    else:
        logger.warning("5組の水曜4限の同期に失敗しました")
        return 0


def main():
    """メイン処理"""
    logger.info("5組の水曜4限修正スクリプトを開始")
    
    # リポジトリとローダーの初期化
    schedule_repo = CSVScheduleRepository(Path("data"))
    school_repo = CSVSchoolRepository(Path("data"))
    absence_loader = TeacherAbsenceLoader()
    constraint_loader = ConstraintLoader()
    
    # データ読み込み
    logger.info("データを読み込み中...")
    school = school_repo.load_school_data()
    schedule = schedule_repo.load_desired_schedule("output/output.csv", school)
    constraints = constraint_loader.load_all_constraints()
    
    # 制約システムの初期化
    constraint_system = UnifiedConstraintSystem()
    for constraint in constraints:
        constraint_system.add_constraint(constraint)
    
    # Grade5Synchronizerの初期化
    synchronizer = RefactoredGrade5Synchronizer(constraint_system)
    
    # 空きスロットの分析
    empty_slots = analyze_empty_slots(schedule, school)
    
    logger.info("\n=== 空きスロット分析結果 ===")
    logger.info(f"5組水曜4限: {len(empty_slots['grade5_wed4'])}スロット")
    logger.info(f"3年生6限: {len(empty_slots['grade3_6th'])}スロット")
    logger.info(f"その他: {len(empty_slots['other'])}スロット")
    
    # 5組の水曜4限を修正
    fixed_count = fix_grade5_wednesday_4th(schedule, school, synchronizer)
    
    if fixed_count > 0:
        # その他の空きスロットも埋める
        logger.info("\n=== その他の空きスロットを埋める ===")
        filler = SmartEmptySlotFiller(constraint_system, absence_loader)
        total_filled = filler.fill_empty_slots_smartly(schedule, school, max_passes=4)
        
        logger.info(f"\n合計 {fixed_count + total_filled} スロットを埋めました")
        
        # 結果を保存
        logger.info("\n修正結果を保存中...")
        schedule_repo.save_schedule(schedule)
        logger.info("修正結果を data/output/output.csv に保存しました")
    else:
        logger.info("5組の水曜4限は既に埋まっているため、修正は不要です")
    
    # 最終的な空きスロット数を確認
    final_empty = analyze_empty_slots(schedule, school)
    total_empty = (len(final_empty['grade5_wed4']) + 
                   len(final_empty['grade3_6th']) + 
                   len(final_empty['other']))
    
    logger.info(f"\n最終的な空きスロット数: {total_empty}")
    if total_empty > 0:
        logger.info("残っている空きスロット:")
        for category, slots in final_empty.items():
            if slots:
                logger.info(f"  {category}: {len(slots)}スロット")
                for time_slot, class_ref in slots[:5]:  # 最初の5件だけ表示
                    logger.info(f"    {time_slot} {class_ref}")


if __name__ == "__main__":
    main()