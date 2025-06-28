#!/usr/bin/env python3
"""
シンプルな教師重複修正のテスト
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.domain.services.simple_teacher_conflict_fixer import SimpleTeacherConflictFixer
from src.application.services.data_loading_service import DataLoadingService
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.config.path_config import path_config
import logging

logging.basicConfig(level=logging.INFO)

def main():
    print("=== シンプルな教師重複修正のテスト ===\n")
    
    # データ読み込み
    data_loading_service = DataLoadingService()
    school, _ = data_loading_service.load_school_data(path_config.data_dir)
    
    # 現在の時間割を読み込む
    schedule_repo = CSVScheduleRepository(path_config.data_dir)
    schedule = schedule_repo.load("output/output.csv", school)
    
    # 修正サービスの作成
    fixer = SimpleTeacherConflictFixer()
    
    # 修正前のレポート
    print("【修正前の状態】")
    print(fixer.generate_report(schedule, school))
    
    # 修正実行
    print("\n修正を実行中...\n")
    fixed_count = fixer.fix_teacher_conflicts(schedule, school)
    
    # 修正後のレポート
    print("\n【修正後の状態】")
    print(fixer.generate_report(schedule, school))
    
    # 時間割を保存
    if fixed_count > 0:
        output_path = path_config.output_dir / "output_simple_fixed.csv"
        schedule_repo.save_schedule(schedule, str(output_path))
        print(f"\n修正後の時間割を保存: {output_path}")

if __name__ == "__main__":
    main()