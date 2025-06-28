#!/usr/bin/env python3
"""空きスロットが埋まらない問題をデバッグ"""

import logging
from pathlib import Path
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.domain.services.csp_orchestrator import CSPOrchestrator
from src.domain.value_objects.time_slot import TimeSlot

# ロギング設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

def analyze_schedule_loading():
    """スケジュールの読み込みを分析"""
    
    # リポジトリ初期化
    base_path = Path("data")
    schedule_repo = CSVScheduleRepository(base_path)
    
    # 学校データ読み込み
    school = schedule_repo.load_school_data("config/base_timetable.csv")
    logger.info(f"学校データ読み込み完了: {len(school.get_all_classes())}クラス")
    
    # 初期スケジュール読み込み
    initial_schedule = schedule_repo.load_desired_schedule("input.csv", school)
    
    # 統計情報
    total_slots = 0
    filled_slots = 0
    empty_slots = 0
    locked_slots = 0
    
    days = ["月", "火", "水", "木", "金"]
    periods = range(1, 7)
    
    for day in days:
        for period in periods:
            for class_ref in school.get_all_classes():
                total_slots += 1
                time_slot = TimeSlot(day, period)
                
                assignment = initial_schedule.get_assignment(time_slot, class_ref)
                if assignment:
                    filled_slots += 1
                    if initial_schedule.is_locked(time_slot, class_ref):
                        locked_slots += 1
                else:
                    empty_slots += 1
    
    logger.info(f"=== スケジュール統計 ===")
    logger.info(f"総スロット数: {total_slots}")
    logger.info(f"埋まっているスロット: {filled_slots}")
    logger.info(f"空きスロット: {empty_slots}")
    logger.info(f"ロックされたスロット: {locked_slots}")
    logger.info(f"空きスロット率: {empty_slots/total_slots*100:.1f}%")
    
    # CSPオーケストレーターのデバッグ
    logger.info("\n=== CSPオーケストレーターのデバッグ ===")
    orchestrator = CSPOrchestrator(school, None)
    
    # 初期化処理をシミュレート
    test_schedule = initial_schedule.copy()
    
    # 各クラスの必要時数を確認
    logger.info("\n=== 各クラスの必要時数 ===")
    for class_ref in school.get_all_classes():
        if class_ref.class_number in [6, 7]:  # 交流学級はスキップ
            continue
        
        required_hours = orchestrator._get_required_hours(class_ref)
        current_hours = {}
        
        # 現在の配置時数を計算
        for day in days:
            for period in periods:
                time_slot = TimeSlot(day, period)
                assignment = test_schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject:
                    subject_name = assignment.subject.name
                    current_hours[subject_name] = current_hours.get(subject_name, 0) + 1
        
        logger.info(f"\n{class_ref}:")
        for subject_name, required in required_hours.items():
            current = current_hours.get(subject_name, 0)
            remaining = required - current
            if remaining > 0:
                logger.info(f"  {subject_name}: 必要{required}時間、現在{current}時間、残り{remaining}時間")
    
    # 配置可能なスロットを確認
    logger.info("\n=== 配置可能スロットの確認 ===")
    for class_ref in school.get_all_classes()[:3]:  # 最初の3クラスのみ
        available_slots = []
        for day in days:
            for period in periods:
                time_slot = TimeSlot(day, period)
                if not test_schedule.get_assignment(time_slot, class_ref):
                    available_slots.append(f"{day}{period}")
        
        logger.info(f"{class_ref}: {len(available_slots)}スロット空き - {', '.join(available_slots[:10])}...")

def main():
    """メイン処理"""
    logger.info("空きスロット問題のデバッグを開始")
    analyze_schedule_loading()
    
    # CSPオーケストレーターの動作確認
    logger.info("\n=== CSPオーケストレーターの動作テスト ===")
    
    from src.infrastructure.config.path_manager import PathManager
    from src.infrastructure.config.csp_config_loader import CSPConfigLoader
    from src.infrastructure.config.advanced_csp_config_loader import AdvancedCSPConfigLoader
    from src.domain.constraints.base import ConstraintChecker
    
    # パスマネージャー初期化
    path_manager = PathManager()
    
    # 制約チェッカー初期化
    constraint_checker = ConstraintChecker()
    
    # 設定読み込み
    config_loader = AdvancedCSPConfigLoader()
    config = config_loader.load()
    
    logger.info(f"固定科目: {config.fixed_subjects}")
    logger.info(f"優先配置科目: {config.priority_subjects}")
    
    # 実際の配置処理の一部をテスト
    base_path = Path("data")
    schedule_repo = CSVScheduleRepository(base_path)
    
    school = schedule_repo.load_school_data("config/base_timetable.csv")
    initial_schedule = schedule_repo.load_desired_schedule("input.csv", school)
    
    # CSPオーケストレーター初期化
    orchestrator = CSPOrchestrator(school, constraint_checker)
    
    # 統計情報を取得
    empty_count = 0
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            for class_ref in school.get_all_classes():
                time_slot = TimeSlot(day, period)
                if not initial_schedule.get_assignment(time_slot, class_ref):
                    empty_count += 1
    
    logger.info(f"\n初期スケジュールの空きスロット数: {empty_count}")
    
    # 実際に配置を試みる
    test_schedule = initial_schedule.copy()
    
    # 1つのクラスで配置をテスト
    test_class = school.get_all_classes()[0]
    logger.info(f"\n{test_class}での配置テスト:")
    
    # 必要時数を取得
    required_hours = orchestrator._get_required_hours(test_class)
    logger.info(f"必要時数: {required_hours}")
    
    # 現在の時数を計算
    current_hours = {}
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = test_schedule.get_assignment(time_slot, test_class)
            if assignment and assignment.subject:
                subject_name = assignment.subject.name
                current_hours[subject_name] = current_hours.get(subject_name, 0) + 1
    
    logger.info(f"現在の時数: {current_hours}")
    
    # 不足している科目を確認
    shortage = {}
    for subject_name, required in required_hours.items():
        current = current_hours.get(subject_name, 0)
        if current < required:
            shortage[subject_name] = required - current
    
    logger.info(f"不足時数: {shortage}")

if __name__ == "__main__":
    main()