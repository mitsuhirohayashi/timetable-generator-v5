#!/usr/bin/env python3
"""UltrathinkPerfectGeneratorV2のテスト"""

import logging
from pathlib import Path
import sys

# プロジェクトのルートをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# ロギング設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.services.ultrathink.ultrathink_perfect_generator_v3 import UltrathinkPerfectGeneratorV3
from src.domain.constraints.base import Constraint

def main():
    """V3ジェネレーターをテスト"""
    print("=== UltrathinkPerfectGeneratorV3テスト ===")
    
    # データロード
    school_repo = CSVSchoolRepository("data")
    school = school_repo.load_school_data()
    
    schedule_repo = CSVScheduleRepository()
    initial_schedule = schedule_repo.load_desired_schedule("data/input/input.csv", school)
    
    print(f"学校データ: {len(school.get_all_classes())}クラス, {len(school.get_all_teachers())}教師")
    print(f"初期スケジュール: {len(initial_schedule.get_all_assignments())}割り当て")
    
    # 制約は空リストで簡単にテスト
    constraints = []
    
    # ジェネレーター作成
    generator = UltrathinkPerfectGeneratorV3()
    
    try:
        # 生成実行
        print("\n生成開始...")
        schedule = generator.generate(school, constraints, initial_schedule)
        print(f"\n生成完了: {len(schedule.get_all_assignments())}割り当て")
        
        # 統計情報を表示
        print("\n=== 統計情報 ===")
        for key, value in generator.stats.items():
            print(f"{key}: {value}")
        
    except Exception as e:
        print(f"\nエラー発生: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()