#!/usr/bin/env python3
"""テスト期間保護の修正スクリプト"""

import logging
from pathlib import Path
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser
from src.domain.value_objects.time_slot import TimeSlot
from src.domain.services.ultrathink.test_period_protector import TestPeriodProtector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_test_period_changes(original_file, generated_file, followup_file):
    """テスト期間の変更をチェック"""
    # リポジトリ初期化
    schedule_repo = CSVScheduleRepository()
    school_repo = CSVSchoolRepository()
    
    # 学校データ読み込み
    school = school_repo.load_school_data("data/config/base_timetable.csv")
    
    # スケジュール読み込み
    original_schedule = schedule_repo.load(original_file, school)
    generated_schedule = schedule_repo.load(generated_file, school)
    
    # Follow-upデータ読み込み
    parser = EnhancedFollowUpParser()
    followup_data = parser.parse(followup_file)
    
    # テスト期間保護サービス初期化
    protector = TestPeriodProtector()
    protector.load_followup_data(followup_data)
    protector.load_initial_schedule(original_schedule)
    
    logger.info(f"テスト期間: {sorted(list(protector.test_periods))}")
    
    # 変更をチェック
    changes = []
    for (day, period) in sorted(protector.test_periods):
        time_slot = TimeSlot(day, period)
        
        for class_ref in school.get_all_classes():
            original_assignment = original_schedule.get_assignment(time_slot, class_ref)
            generated_assignment = generated_schedule.get_assignment(time_slot, class_ref)
            
            if original_assignment and generated_assignment:
                if original_assignment.subject.name != generated_assignment.subject.name:
                    changes.append({
                        'time': f"{day}曜{period}限",
                        'class': str(class_ref),
                        'original': original_assignment.subject.name,
                        'generated': generated_assignment.subject.name
                    })
    
    return changes, protector

def fix_test_periods(generated_file, output_file, protector):
    """テスト期間を修正"""
    # リポジトリ初期化
    schedule_repo = CSVScheduleRepository()
    school_repo = CSVSchoolRepository()
    
    # データ読み込み
    school = school_repo.load_school_data("data/config/base_timetable.csv")
    schedule = schedule_repo.load(generated_file, school)
    
    # テスト期間保護を適用
    changed = protector.protect_test_periods(schedule, school)
    logger.info(f"修正された割り当て数: {changed}")
    
    # 保存
    schedule_repo.save_schedule(schedule, output_file)
    logger.info(f"修正済みスケジュールを保存: {output_file}")
    
    return changed

def main():
    logger.info("=== テスト期間保護チェック ===")
    
    # ファイルパス
    original_file = "data/input/input.csv"
    generated_file = "data/output/output.csv"
    followup_file = "data/input/Follow-up.csv"
    output_file = "data/output/output_test_period_fixed.csv"
    
    # 変更をチェック
    changes, protector = check_test_period_changes(original_file, generated_file, followup_file)
    
    if changes:
        logger.warning(f"\n❌ テスト期間に{len(changes)}件の変更が検出されました:")
        for change in changes[:10]:  # 最初の10件を表示
            logger.warning(
                f"  {change['time']} {change['class']}: "
                f"{change['original']} → {change['generated']}"
            )
        
        # 修正を実行
        logger.info("\n修正を実行中...")
        fix_test_periods(generated_file, output_file, protector)
        
        # 再チェック
        logger.info("\n修正後の確認...")
        changes_after, _ = check_test_period_changes(original_file, output_file, followup_file)
        
        if not changes_after:
            logger.info("✅ テスト期間の保護が完了しました")
        else:
            logger.error(f"❌ まだ{len(changes_after)}件の変更が残っています")
    else:
        logger.info("✅ テスト期間に変更はありません")

if __name__ == "__main__":
    main()