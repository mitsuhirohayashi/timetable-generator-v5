#!/usr/bin/env python3
"""3年6組の自立活動特別ルールのテスト"""

import sys
import logging
from pathlib import Path

# プロジェクトのルートディレクトリをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.parsers.natural_followup_parser import NaturalFollowUpParser

def check_3_6_jiritsu_placements():
    """3年6組の自立活動配置をチェック"""
    # ロギング設定
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger = logging.getLogger(__name__)
    
    # CSVリポジトリを初期化
    csv_repo = CSVScheduleRepository()
    schedule = csv_repo.load("data/output/output.csv")
    
    if not schedule:
        logger.error("出力スケジュールが見つかりません")
        return
    
    # テスト期間情報を読み込む
    parser = NaturalFollowUpParser(Path("data/input"))
    result = parser.parse_file("Follow-up.csv")
    test_periods = set()
    
    if result.get("test_periods"):
        for test_period in result["test_periods"]:
            day = test_period.day
            for period in test_period.periods:
                test_periods.add((day, period))
    
    logger.info("=== 3年6組の自立活動配置チェック ===")
    logger.info(f"テスト期間: {sorted(test_periods)}")
    logger.info("")
    
    # 3年6組と3年3組のクラス参照
    class_3_6 = ClassReference(3, 6)
    class_3_3 = ClassReference(3, 3)
    
    violations = []
    jiritsu_count = 0
    
    # 全時間帯をチェック
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            # 3年6組の割り当てを取得
            assignment_3_6 = schedule.get_assignment(time_slot, class_3_6)
            
            if assignment_3_6 and assignment_3_6.subject.name == "自立":
                jiritsu_count += 1
                
                # 3年3組の割り当てを取得
                assignment_3_3 = schedule.get_assignment(time_slot, class_3_3)
                
                # テスト期間かチェック
                is_test_period = (day, period) in test_periods
                
                logger.info(f"{day}{period}限: 3-6={assignment_3_6.subject.name}, "
                          f"3-3={assignment_3_3.subject.name if assignment_3_3 else '空き'}, "
                          f"テスト期間={'Yes' if is_test_period else 'No'}")
                
                # テスト期間でない場合、3-3が数学か英語である必要がある
                if not is_test_period:
                    if not assignment_3_3 or assignment_3_3.subject.name not in ["数", "英"]:
                        violations.append({
                            'time_slot': time_slot,
                            'parent_subject': assignment_3_3.subject.name if assignment_3_3 else '空き'
                        })
    
    logger.info("")
    logger.info(f"3年6組の自立活動: 合計{jiritsu_count}コマ")
    
    if violations:
        logger.warning(f"\n違反が{len(violations)}件見つかりました:")
        for v in violations:
            logger.warning(f"  {v['time_slot']}: 3-3が{v['parent_subject']}（数または英である必要）")
    else:
        logger.info("✓ すべての自立活動配置が適切です")
    
    # 財津先生の担当確認
    logger.info("\n=== 財津先生の自立活動担当確認 ===")
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            for grade in [1, 2, 3]:
                class_ref = ClassReference(grade, 6)
                assignment = schedule.get_assignment(time_slot, class_ref)
                
                if assignment and assignment.subject.name == "自立":
                    logger.info(f"{time_slot}: {class_ref} - 担当: {assignment.teacher.name}")

if __name__ == "__main__":
    check_3_6_jiritsu_placements()