#!/usr/bin/env python3
"""交流学級同期違反を修正"""

import logging
from collections import defaultdict
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot, Subject
from src.domain.value_objects.assignment import Assignment
from src.domain.utils import parse_class_reference

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_exchange_sync_violations(schedule, school):
    """交流学級同期違反を分析"""
    exchange_pairs = {
        '1年6組': '1年1組',
        '1年7組': '1年2組',
        '2年6組': '2年3組',
        '2年7組': '2年2組',
        '3年6組': '3年3組',
        '3年7組': '3年2組'
    }
    
    violations = []
    
    for exchange_class, parent_class in exchange_pairs.items():
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                exchange_ref = parse_class_reference(exchange_class)
                parent_ref = parse_class_reference(parent_class)
                
                exchange_assignment = schedule.get_assignment(time_slot, exchange_ref)
                parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                
                exchange_subject = exchange_assignment.subject.name if exchange_assignment and exchange_assignment.subject else "空き"
                parent_subject = parent_assignment.subject.name if parent_assignment and parent_assignment.subject else "空き"
                
                # 自立活動以外で異なる場合は違反
                if exchange_subject != parent_subject and exchange_subject != '自立':
                    violations.append({
                        'time_slot': time_slot,
                        'exchange_class': exchange_class,
                        'parent_class': parent_class,
                        'exchange_subject': exchange_subject,
                        'parent_subject': parent_subject,
                        'exchange_assignment': exchange_assignment,
                        'parent_assignment': parent_assignment
                    })
    
    return violations

def fix_exchange_sync_violations(schedule, school):
    """交流学級同期違反を修正"""
    violations = analyze_exchange_sync_violations(schedule, school)
    fixed_count = 0
    
    logger.info(f"=== 交流学級同期違反の修正開始 ===")
    logger.info(f"検出された違反: {len(violations)}件")
    
    for violation in violations:
        time_slot = violation['time_slot']
        exchange_class = violation['exchange_class']
        parent_class = violation['parent_class']
        parent_assignment = violation['parent_assignment']
        
        logger.info(f"\n{time_slot}: {exchange_class}を{parent_class}に同期")
        logger.info(f"  現在: {exchange_class}={violation['exchange_subject']}, {parent_class}={violation['parent_subject']}")
        
        # 交流学級を親学級に同期させる
        exchange_ref = parse_class_reference(exchange_class)
        
        try:
            # 既存の割り当てを削除
            current = schedule.get_assignment(time_slot, exchange_ref)
            if current:
                schedule.remove_assignment(time_slot, exchange_ref)
            
            # 親学級に授業がある場合、同じ授業を配置
            if parent_assignment and parent_assignment.subject:
                # 親学級と同じ科目・教師で配置
                new_assignment = Assignment(
                    class_ref=exchange_ref,
                    subject=parent_assignment.subject,
                    teacher=parent_assignment.teacher
                )
                
                schedule.assign(time_slot, new_assignment)
                logger.info(f"  ✓ 修正成功: {exchange_class}を{parent_assignment.subject.name}({parent_assignment.teacher.name if parent_assignment.teacher else '教師未定'})に変更")
                fixed_count += 1
            else:
                # 親学級が空きの場合、交流学級も空きにする
                logger.info(f"  ✓ 修正成功: {exchange_class}を空きに変更")
                fixed_count += 1
                
        except Exception as e:
            logger.error(f"  ✗ 修正失敗: {e}")
    
    logger.info(f"\n=== 修正完了: {fixed_count}/{len(violations)}件 ===")
    return fixed_count

def verify_exchange_sync(schedule, school):
    """交流学級同期を検証"""
    violations = analyze_exchange_sync_violations(schedule, school)
    
    if not violations:
        logger.info("✅ すべての交流学級が正しく同期されています")
    else:
        logger.warning(f"❌ まだ{len(violations)}件の同期違反があります")
        for v in violations[:5]:
            logger.warning(f"  {v['time_slot']}: {v['exchange_class']}={v['exchange_subject']}, {v['parent_class']}={v['parent_subject']}")

def main():
    # リポジトリ初期化
    schedule_repo = CSVScheduleRepository()
    school_repo = CSVSchoolRepository()
    
    # データ読み込み
    logger.info("データ読み込み中...")
    school = school_repo.load_school_data("data/config/base_timetable.csv")
    
    # Grade5修正済みファイルから読み込む
    from pathlib import Path
    input_file = "data/output/output_grade5_sync_fixed.csv"
    if not Path(input_file).exists():
        input_file = "data/output/output.csv"
        logger.info(f"Grade5修正済みファイルが見つからないため、{input_file}を使用")
    
    schedule = schedule_repo.load(input_file, school)
    
    # 交流学級同期違反の修正
    fixed = fix_exchange_sync_violations(schedule, school)
    
    if fixed > 0:
        # 結果を保存
        output_file = "data/output/output_exchange_sync_fixed.csv"
        schedule_repo.save_schedule(schedule, output_file)
        logger.info(f"\n修正済み時間割を保存: {output_file}")
        
        # 検証
        logger.info("\n=== 修正後の検証 ===")
        verify_exchange_sync(schedule, school)

if __name__ == "__main__":
    main()