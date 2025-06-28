#!/usr/bin/env python3
"""スケジュール生成ユースケース統合テスト"""
import logging
from pathlib import Path
from src.application.use_cases.generate_schedule import (
    GenerateScheduleUseCase,
    GenerateScheduleRequest
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_standard_generation():
    """標準版のテスト"""
    print("\n=== 標準版のテスト ===")
    use_case = GenerateScheduleUseCase()
    request = GenerateScheduleRequest(
        data_directory=Path("data"),
        max_iterations=10  # テスト用に少なく設定
    )
    
    result = use_case.execute(request)
    print(f"結果: {result.message}")
    print(f"制約違反: {result.violations_count}件")
    return result.success

def test_with_meeting_optimization():
    """会議時間最適化のテスト"""
    print("\n=== 会議時間最適化のテスト ===")
    use_case = GenerateScheduleUseCase()
    request = GenerateScheduleRequest(
        data_directory=Path("data"),
        max_iterations=10,
        optimize_meeting_times=True
    )
    
    result = use_case.execute(request)
    print(f"結果: {result.message}")
    print(f"会議時間調整: {result.meeting_improvements}件")
    return result.success

def test_with_gym_optimization():
    """体育館使用最適化のテスト"""
    print("\n=== 体育館使用最適化のテスト ===")
    use_case = GenerateScheduleUseCase()
    request = GenerateScheduleRequest(
        data_directory=Path("data"),
        max_iterations=10,
        optimize_gym_usage=True
    )
    
    result = use_case.execute(request)
    print(f"結果: {result.message}")
    print(f"体育館使用最適化: {result.gym_improvements}件")
    return result.success

def test_with_workload_optimization():
    """教師負担最適化のテスト"""
    print("\n=== 教師負担最適化のテスト ===")
    use_case = GenerateScheduleUseCase()
    request = GenerateScheduleRequest(
        data_directory=Path("data"),
        max_iterations=10,
        optimize_workload=True
    )
    
    result = use_case.execute(request)
    print(f"結果: {result.message}")
    print(f"教師負担改善: {result.workload_improvements}件")
    return result.success

def test_with_all_optimizations():
    """全機能有効化のテスト"""
    print("\n=== 全機能有効化のテスト ===")
    use_case = GenerateScheduleUseCase()
    request = GenerateScheduleRequest(
        data_directory=Path("data"),
        max_iterations=10,
        optimize_meeting_times=True,
        optimize_gym_usage=True,
        optimize_workload=True,
        use_support_hours=True
    )
    
    result = use_case.execute(request)
    print(f"結果: {result.message}")
    print(f"会議時間調整: {result.meeting_improvements}件")
    print(f"体育館使用最適化: {result.gym_improvements}件")
    print(f"教師負担改善: {result.workload_improvements}件")
    return result.success

def main():
    """メイン実行"""
    print("スケジュール生成ユースケース統合テストを開始")
    
    tests = [
        ("標準版", test_standard_generation),
        ("会議時間最適化", test_with_meeting_optimization),
        ("体育館使用最適化", test_with_gym_optimization),
        ("教師負担最適化", test_with_workload_optimization),
        ("全機能有効", test_with_all_optimizations)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, "成功" if success else "失敗"))
        except Exception as e:
            print(f"エラー: {e}")
            results.append((test_name, f"エラー: {str(e)[:50]}"))
    
    print("\n=== テスト結果サマリー ===")
    for test_name, result in results:
        print(f"{test_name}: {result}")

if __name__ == "__main__":
    main()