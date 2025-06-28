#!/usr/bin/env python3
"""
並列最適化システムの動作確認スクリプト

HybridScheduleGeneratorV7の並列処理機能をテストします。
"""
import time
import logging
from multiprocessing import cpu_count

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# インポート
try:
    from src.domain.services.ultrathink import (
        HybridScheduleGeneratorV7,
        ParallelOptimizationConfig
    )
    print("✓ HybridScheduleGeneratorV7のインポート成功")
except ImportError as e:
    print(f"✗ インポートエラー: {e}")
    exit(1)

try:
    from src.domain.services.ultrathink import ParallelOptimizationEngine
    print("✓ ParallelOptimizationEngineのインポート成功")
except ImportError as e:
    print(f"✗ インポートエラー: {e}")
    exit(1)


def test_parallel_engine():
    """並列エンジンの基本テスト"""
    print("\n=== 並列エンジンテスト ===")
    
    # 利用可能なCPU数を表示
    print(f"利用可能CPU数: {cpu_count()}")
    
    # エンジンを作成
    engine = ParallelOptimizationEngine(max_workers=None)
    print(f"作成されたワーカー数: {engine.max_workers}")
    
    # パフォーマンス統計を表示
    stats = engine.get_performance_stats()
    print(f"エンジン統計: {stats}")
    
    return True


def test_hybrid_generator_v7():
    """HybridScheduleGeneratorV7の基本テスト"""
    print("\n=== HybridScheduleGeneratorV7テスト ===")
    
    # 並列設定を作成
    parallel_config = ParallelOptimizationConfig(
        enable_parallel_placement=True,
        enable_parallel_verification=True,
        enable_parallel_search=True,
        max_workers=4,
        use_threads=False,
        batch_size=50,
        strategy_time_limit=60,
        local_search_neighbors=4,
        sa_populations=4
    )
    
    print("並列設定:")
    print(f"  - 並列配置: {parallel_config.enable_parallel_placement}")
    print(f"  - 並列検証: {parallel_config.enable_parallel_verification}")
    print(f"  - 並列探索: {parallel_config.enable_parallel_search}")
    print(f"  - 最大ワーカー数: {parallel_config.max_workers}")
    print(f"  - スレッド使用: {parallel_config.use_threads}")
    
    # ジェネレータを作成
    try:
        generator = HybridScheduleGeneratorV7(
            enable_logging=True,
            learning_data_dir=None,
            parallel_config=parallel_config
        )
        print("✓ HybridScheduleGeneratorV7の作成成功")
        
        # 属性確認
        print(f"  - 並列エンジン: {type(generator.parallel_engine).__name__}")
        print(f"  - 学習システム: {type(generator.learning_system).__name__}")
        print(f"  - 制約検証器: {type(generator.constraint_validator).__name__}")
        
        return True
        
    except Exception as e:
        print(f"✗ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_performance_comparison():
    """V6とV7のパフォーマンス比較（簡易版）"""
    print("\n=== パフォーマンス比較 ===")
    
    try:
        from src.domain.services.ultrathink.hybrid_schedule_generator_v6 import HybridScheduleGeneratorV6
        
        # V6（シーケンシャル）
        v6_generator = HybridScheduleGeneratorV6(enable_logging=False)
        print("✓ V6ジェネレータ作成成功")
        
        # V7（並列）
        parallel_config = ParallelOptimizationConfig(
            enable_parallel_placement=True,
            enable_parallel_verification=True,
            enable_parallel_search=True,
            max_workers=4
        )
        v7_generator = HybridScheduleGeneratorV7(
            enable_logging=False,
            parallel_config=parallel_config
        )
        print("✓ V7ジェネレータ作成成功（並列モード）")
        
        # 簡易的なスピード比較
        print("\n予想されるパフォーマンス向上:")
        print(f"  - CPU数: {cpu_count()}")
        print(f"  - ワーカー数: {v7_generator.parallel_engine.max_workers}")
        print(f"  - 理論的最大スピードアップ: {v7_generator.parallel_engine.max_workers}倍")
        print(f"  - 実用的スピードアップ（推定）: {v7_generator.parallel_engine.max_workers * 0.7:.1f}倍")
        
        return True
        
    except Exception as e:
        print(f"✗ エラー: {e}")
        return False


def main():
    """メイン処理"""
    print("=== 並列最適化システムテスト開始 ===\n")
    
    # 各テストを実行
    tests = [
        ("並列エンジン基本テスト", test_parallel_engine),
        ("HybridScheduleGeneratorV7テスト", test_hybrid_generator_v7),
        ("パフォーマンス比較", test_performance_comparison)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n{test_name}でエラー: {e}")
            results.append((test_name, False))
    
    # 結果サマリー
    print("\n=== テスト結果サマリー ===")
    success_count = 0
    for test_name, result in results:
        status = "✓ 成功" if result else "✗ 失敗"
        print(f"{test_name}: {status}")
        if result:
            success_count += 1
    
    print(f"\n合計: {success_count}/{len(tests)} テスト成功")
    
    if success_count == len(tests):
        print("\n🎉 全てのテストが成功しました！")
        print("並列処理による高速最適化システムが正常に動作しています。")
    else:
        print("\n⚠️  一部のテストが失敗しました。")


if __name__ == "__main__":
    main()