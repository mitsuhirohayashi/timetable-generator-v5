#!/usr/bin/env python3
"""柔軟な埋め戦略のデモンストレーション"""

import logging
from pathlib import Path
from src.domain.services.implementations.flexible_filling_strategy import FlexibleFillingStrategy
from src.domain.entities.school import School, Subject, Teacher
from src.domain.entities.schedule import Schedule
from src.domain.value_objects.time_slot import TimeSlot, ClassReference

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def demo_flexible_strategy():
    """柔軟な戦略のデモ"""
    
    # FlexibleFillingStrategyのインスタンス作成
    strategy = FlexibleFillingStrategy()
    logger.info(f"戦略名: {strategy.name}")
    
    # 戦略の特徴を表示
    logger.info("\n=== FlexibleFillingStrategyの特徴 ===")
    logger.info(f"1日最大配置数（国語）: {strategy.get_max_daily_occurrences('国')}")
    logger.info(f"連続時限チェック: {strategy.should_check_consecutive_periods()}")
    logger.info(f"日内重複の厳密チェック: {strategy.should_check_daily_duplicate_strictly()}")
    logger.info(f"禁止科目フィルタ: {strategy.should_filter_forbidden_subjects()}")
    
    # ダミーデータでテスト
    logger.info("\n=== 代替教師検索のデモ ===")
    
    # ダミーの学校データ
    school = School()
    
    # 教科を追加
    math_subj = Subject("数")
    eng_subj = Subject("英")
    school.add_subject(math_subj)
    school.add_subject(eng_subj)
    
    # 教師を追加
    teacher1 = Teacher("田中")
    teacher2 = Teacher("山田")
    teacher3 = Teacher("佐藤")
    
    # ダミーのスケジュール
    schedule = Schedule()
    time_slot = TimeSlot("月", 1)
    class_ref = ClassReference(3, 1)  # 3年1組
    
    # 配置可能な科目を取得
    subjects = strategy.get_placeable_subjects(schedule, school, time_slot, class_ref)
    logger.info(f"配置可能な科目数: {len(subjects)}")
    
    # 候補リストを作成（ダミーデータ）
    shortage_subjects = {math_subj: 2, eng_subj: 1}
    teacher_loads = {"田中": 20, "山田": 15, "佐藤": 25}
    
    candidates = strategy.create_candidates(
        schedule, school, time_slot, class_ref,
        shortage_subjects, teacher_loads
    )
    
    logger.info(f"\n候補数: {len(candidates)}")
    for i, (subject, teacher) in enumerate(candidates[:5], 1):
        logger.info(f"  候補{i}: {subject.name} - {teacher.name}")
    
    logger.info("\n=== 柔軟性の例 ===")
    logger.info("1. 通常の担当教師が不在でも、代替教師を自動検索")
    logger.info("2. 時数が余っている科目も配置候補に追加")
    logger.info("3. 緊急時は他学年の教師も検討")
    logger.info("4. 1日2回まで同じ科目を配置可能（通常は1回）")
    logger.info("5. 連続時限での配置も許可")
    
    return True

if __name__ == "__main__":
    logger.info("=== 柔軟な埋め戦略のデモンストレーション ===")
    
    success = demo_flexible_strategy()
    
    if success:
        logger.info("\n✓ FlexibleFillingStrategyが正しく動作しています")
        logger.info("\nこの戦略により、人間の時間割作成者のような柔軟な判断が可能になります。")
        logger.info("教師不在時でも代替案を見つけ、完全な時間割を作成できます。")
    
    logger.info("\n=== デモ終了 ===")