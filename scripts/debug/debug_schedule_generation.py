#!/usr/bin/env python3
"""スケジュール生成のデバッグスクリプト"""

import sys
import logging
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# ロギング設定
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from src.application.use_cases.generate_schedule import GenerateScheduleUseCase, GenerateScheduleRequest
from src.domain.value_objects.time_slot import TimeSlot, ClassReference

def debug_schedule_at_key_points():
    """スケジュール生成の各段階でテスト期間データを確認"""
    
    # テスト期間の定義
    test_periods = [
        ("月", 1), ("月", 2), ("月", 3),
        ("火", 1), ("火", 2), ("火", 3),
        ("水", 1), ("水", 2)
    ]
    
    # リクエストを作成
    request = GenerateScheduleRequest(
        data_directory=Path("data"),
        base_timetable_file="config/base_timetable.csv",  # 正しいパス
        max_iterations=1,  # デバッグのため1回のみ
        use_advanced_csp=True
    )
    
    # ユースケースを作成
    use_case = GenerateScheduleUseCase()
    
    # 元のメソッドを保存
    original_generate = use_case.generation_service.generate_schedule
    original_csp_generate = None
    
    def debug_generate_schedule(school, initial_schedule=None, **kwargs):
        """generate_scheduleメソッドをフック"""
        print("\n=== ScheduleGenerationService.generate_schedule called ===")
        
        if initial_schedule:
            print(f"Initial schedule assignments: {len(initial_schedule.get_all_assignments())}")
            # テスト期間のデータを確認
            test_data_count = 0
            for day, period in test_periods:
                time_slot = TimeSlot(day, period)
                for grade in [1, 2, 3]:
                    for class_num in [1, 2, 3, 6, 7]:
                        class_ref = ClassReference(grade, class_num)
                        assignment = initial_schedule.get_assignment(time_slot, class_ref)
                        if assignment:
                            test_data_count += 1
            print(f"Test period data in initial schedule: {test_data_count}")
        else:
            print("No initial schedule provided")
        
        # 元のメソッドを呼び出す
        result = original_generate(school, initial_schedule, **kwargs)
        
        # 結果を確認
        print(f"\nGenerated schedule assignments: {len(result.get_all_assignments())}")
        test_data_count = 0
        for day, period in test_periods:
            time_slot = TimeSlot(day, period)
            for grade in [1, 2, 3]:
                for class_num in [1, 2, 3, 6, 7]:
                    class_ref = ClassReference(grade, class_num)
                    assignment = result.get_assignment(time_slot, class_ref)
                    if assignment:
                        test_data_count += 1
        print(f"Test period data in generated schedule: {test_data_count}")
        
        return result
    
    # メソッドを置き換え
    use_case.generation_service.generate_schedule = debug_generate_schedule
    
    # 実行
    print("=== Starting debug schedule generation ===")
    try:
        result = use_case.execute(request)
        print(f"\n=== Generation completed ===")
        print(f"Success: {result.success}")
        print(f"Message: {result.message}")
        print(f"Violations: {result.violations_count}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_schedule_at_key_points()