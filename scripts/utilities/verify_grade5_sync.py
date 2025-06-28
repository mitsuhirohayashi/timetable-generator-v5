#!/usr/bin/env python3
"""Grade5同期の詳細確認"""

import logging
from collections import defaultdict
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot
from src.domain.utils import parse_class_reference

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_grade5_sync(schedule_file):
    """5組の同期状態を詳細チェック"""
    # リポジトリ初期化
    schedule_repo = CSVScheduleRepository()
    school_repo = CSVSchoolRepository()
    
    # データ読み込み
    school = school_repo.load_school_data("data/config/base_timetable.csv")
    schedule = schedule_repo.load(schedule_file, school)
    
    grade5_classes = ['1年5組', '2年5組', '3年5組']
    sync_violations = []
    sync_ok = []
    
    logger.info(f"\n=== {schedule_file} の5組同期チェック ===")
    
    for day in ['月', '火', '水', '木', '金']:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            # 各5組クラスの科目を取得
            subjects = {}
            for class_name in grade5_classes:
                class_ref = parse_class_reference(class_name)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject:
                    subjects[class_name] = assignment.subject.name
                else:
                    subjects[class_name] = "空き"
            
            # 全て同じかチェック
            unique_subjects = set(subjects.values())
            if len(unique_subjects) > 1:
                sync_violations.append({
                    'time': f"{day}曜{period}限",
                    'subjects': subjects,
                    'unique': unique_subjects
                })
            else:
                sync_ok.append({
                    'time': f"{day}曜{period}限",
                    'subject': list(unique_subjects)[0]
                })
    
    # 結果表示
    logger.info(f"\n同期OK: {len(sync_ok)}スロット")
    logger.info(f"同期違反: {len(sync_violations)}スロット")
    
    if sync_violations:
        logger.info("\n違反詳細:")
        for v in sync_violations[:5]:  # 最初の5件
            logger.info(f"  {v['time']}: {v['subjects']}")
    
    return len(sync_violations)

def main():
    # 元のファイル
    original_violations = check_grade5_sync("data/output/output.csv")
    
    # 修正後のファイル
    fixed_violations = check_grade5_sync("data/output/output_grade5_sync_fixed.csv")
    
    logger.info(f"\n=== 改善結果 ===")
    logger.info(f"5組同期違反: {original_violations} → {fixed_violations} ({original_violations - fixed_violations}件削減)")

if __name__ == "__main__":
    main()