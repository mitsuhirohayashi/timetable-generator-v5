#!/usr/bin/env python3
"""シンプルな空きスロット埋めスクリプト"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.application.use_cases.generate_schedule import GenerateScheduleRequest
from src.application.use_cases.use_case_factory import UseCaseFactory
from src.infrastructure.config.logging_config import setup_logging

def main():
    """メイン処理"""
    # ロギング設定
    setup_logging(verbose=True)
    
    print("=== 空きスロット自動埋めシステム ===\n")
    
    # 既存の時間割を読み込んで再生成（空きスロットを埋める）
    request = GenerateScheduleRequest(
        base_timetable_file="data/config/base_timetable.csv",
        desired_timetable_file="data/input/input.csv",  # 既存の時間割を初期値として使用
        followup_prompt_file="data/input/Follow-up.csv",
        output_file="data/output/output.csv",
        data_directory=Path("data"),
        max_iterations=100,
        enable_soft_constraints=False,
        use_random=False,
        randomness_level=0.0,
        start_empty=False,  # 既存の時間割から開始
        use_advanced_csp=True,
        use_improved_csp=False,
        optimize_meeting_times=False,
        optimize_gym_usage=False,
        optimize_workload=False,
        use_support_hours=False,
        search_mode="greedy"
    )
    
    # 時間割生成（空きスロット埋め）を実行
    use_case = UseCaseFactory.create_generate_schedule_use_case()
    result = use_case.execute(request)
    
    # 結果表示
    print(f"\n生成結果:")
    print(f"  - 成功: {result.success}")
    print(f"  - 総コマ数: {result.total_slots}")
    print(f"  - 空きコマ数: {result.empty_slots}")
    print(f"  - 制約違反数: {result.violations_count}")
    
    if result.success:
        print(f"\n✅ 空きスロットの埋め込みが完了しました。")
        print(f"   出力: {request.output_file}")
    else:
        print(f"\n❌ エラーが発生しました: {result.error_message}")
    
    return 0 if result.success else 1

if __name__ == "__main__":
    sys.exit(main())