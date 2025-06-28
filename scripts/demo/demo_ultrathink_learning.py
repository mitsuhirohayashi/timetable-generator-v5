#!/usr/bin/env python3
"""
Ultrathink学習システムのデモンストレーション

制約違反パターンの学習システムの使用方法を示すデモスクリプト。
"""

import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import logging
from datetime import datetime

from src.domain.entities import Schedule, School
from src.domain.constraints.base import ConstraintViolation, ConstraintPriority
from src.infrastructure.repositories import CSVRepository
from src.infrastructure.config import PathConfig
from src.application.services.ultrathink_learning_adapter import UltrathinkLearningAdapter
from src.domain.services.violation_collector import ViolationCollector
from src.domain.constraints import (
    TeacherConflictConstraintRefactored,
    DailyDuplicateConstraint,
    ExchangeClassSyncConstraint
)


# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_sample_violations() -> list[ConstraintViolation]:
    """デモ用のサンプル違反を作成"""
    violations = []
    
    # 教師競合違反
    violations.append(ConstraintViolation(
        constraint_type="TeacherConflict",
        message="井上先生 is assigned to multiple classes at 火曜日 5限",
        priority=ConstraintPriority.HIGH,
        details={
            "day": 1,  # 火曜日
            "period": 4,  # 5限
            "teacher": "井上",
            "classes": ["2-1", "2-2"],
            "subject": "数学"
        }
    ))
    
    # 日内重複違反
    violations.append(ConstraintViolation(
        constraint_type="DailyDuplicate",
        message="3-3 has 数学 multiple times on 木曜日",
        priority=ConstraintPriority.HIGH,
        details={
            "day": 3,  # 木曜日
            "period": 2,  # 3限
            "class_id": "3-3",
            "subject": "数学",
            "duplicate_periods": [1, 2]  # 2限と3限
        }
    ))
    
    # 交流学級自立活動違反
    violations.append(ConstraintViolation(
        constraint_type="ExchangeClassJiritsu",
        message="3-6 has 自立 but parent class 3-3 has 理科 (not 数/英)",
        priority=ConstraintPriority.HIGH,
        details={
            "day": 2,  # 水曜日
            "period": 3,  # 4限
            "class_id": "3-6",
            "parent_class": "3-3",
            "subject": "自立",
            "parent_subject": "理科"
        }
    ))
    
    return violations


def demonstrate_learning_system():
    """学習システムのデモンストレーション"""
    print("=" * 80)
    print("Ultrathink Constraint Violation Learning System - Demonstration")
    print("=" * 80)
    
    # パス設定とリポジトリの初期化
    path_config = PathConfig()
    repository = CSVRepository(path_config)
    
    # 学校データとスケジュールを読み込み
    print("\n1. Loading school data and schedule...")
    school = repository.load_school()
    schedule = repository.load_schedule()
    
    # 学習アダプターを初期化
    print("\n2. Initializing Ultrathink learning adapter...")
    adapter = UltrathinkLearningAdapter(learning_dir="data/learning/demo")
    
    # 初期状態を表示
    initial_report = adapter.learning_system.get_learning_report()
    print(f"\nInitial state:")
    print(f"  - Total generations: {initial_report['summary']['generation_count']}")
    print(f"  - Total violations learned: {initial_report['summary']['total_violations']}")
    print(f"  - Unique patterns: {initial_report['summary']['unique_patterns']}")
    
    # 生成前分析
    print("\n3. Running pre-generation analysis...")
    pre_analysis = adapter.pre_generation_analysis(schedule, school)
    print(f"\nPre-generation analysis results:")
    print(f"  - High-risk slots identified: {len(pre_analysis['high_risk_slots'])}")
    print(f"  - Active strategies: {pre_analysis['active_strategies']}")
    print(f"  - Suggestions: {len(pre_analysis['suggestions'])}")
    
    if pre_analysis['suggestions']:
        print("\nTop suggestions:")
        for i, suggestion in enumerate(pre_analysis['suggestions'][:3], 1):
            print(f"  {i}. {suggestion}")
    
    # サンプル違反で学習（実際のシステムでは制約チェックから違反を取得）
    print("\n4. Simulating constraint violations...")
    violations = create_sample_violations()
    print(f"  - Generated {len(violations)} sample violations")
    
    for v in violations:
        print(f"    * {v.constraint_type}: {v.message}")
    
    # 生成後学習
    print("\n5. Running post-generation learning...")
    post_result = adapter.post_generation_learning(violations, schedule, school)
    print(f"\nPost-generation learning results:")
    print(f"  - Violations learned: {post_result['violations_learned']}")
    print(f"  - Strategy effectiveness: {post_result['strategy_effectiveness']:.2%}")
    print(f"  - Improvement rate: {post_result['improvement_rate']:.2%}")
    
    # 学習後の統計を表示
    print("\n6. Learning statistics after processing:")
    stats = adapter.learning_system.get_learning_report()
    print(f"  - Total generations: {stats['summary']['generation_count']}")
    print(f"  - Total violations: {stats['summary']['total_violations']}")
    print(f"  - Avoided violations: {stats['summary']['avoided_violations']}")
    print(f"  - Avoidance rate: {stats['summary']['avoidance_rate']:.2%}")
    
    # 高頻度パターンを表示
    if stats['high_frequency_patterns']:
        print("\n7. High-frequency violation patterns:")
        for i, pattern in enumerate(stats['high_frequency_patterns'][:5], 1):
            print(f"  {i}. Pattern {pattern['pattern_id']}:")
            print(f"     - Frequency: {pattern['frequency']}")
            print(f"     - Confidence: {pattern['confidence']:.2f}")
            print(f"     - Description: {pattern['description']}")
    
    # 効果的な戦略を表示
    if stats['effective_strategies']:
        print("\n8. Most effective avoidance strategies:")
        for i, strategy in enumerate(stats['effective_strategies'][:5], 1):
            print(f"  {i}. Strategy {strategy['strategy_id']}:")
            print(f"     - Success rate: {strategy['success_rate']:.2%}")
            print(f"     - Usage count: {strategy['usage_count']}")
            print(f"     - Description: {strategy['description']}")
    
    # 違反ヒートマップを表示
    print("\n9. Violation heatmap visualization:")
    print(adapter.get_violation_heatmap())
    
    # 推奨制約を表示
    print("\n10. Suggested new constraints based on learning:")
    suggestions = adapter.get_suggested_constraints()
    if suggestions:
        for i, constraint in enumerate(suggestions, 1):
            print(f"  {i}. {constraint['description']}")
            print(f"     - Based on pattern: {constraint['pattern_id']}")
            print(f"     - Confidence: {constraint['confidence']:.2f}")
            print(f"     - Frequency: {constraint['frequency']}")
    else:
        print("  No constraints suggested yet (need more learning data)")
    
    # 学習データのエクスポート
    print("\n11. Exporting learning data...")
    export_path = adapter.export_learning_data()
    print(f"  - Data exported to: {export_path}")
    
    print("\n" + "=" * 80)
    print("Demonstration complete!")
    print("The system will continue to learn and improve with each generation.")
    print("=" * 80)


def demonstrate_continuous_learning():
    """連続学習のデモンストレーション"""
    print("\n" + "=" * 80)
    print("Continuous Learning Demonstration")
    print("=" * 80)
    
    path_config = PathConfig()
    repository = CSVRepository(path_config)
    school = repository.load_school()
    schedule = repository.load_schedule()
    
    adapter = UltrathinkLearningAdapter(learning_dir="data/learning/continuous")
    
    # 5世代のシミュレーション
    print("\nSimulating 5 generations of schedule generation...")
    
    for generation in range(1, 6):
        print(f"\n--- Generation {generation} ---")
        
        # ランダムな違反を生成（実際の使用では制約チェックから取得）
        import random
        num_violations = random.randint(3, 8)
        violations = []
        
        # 違反タイプをランダムに選択
        violation_types = [
            ("TeacherConflict", "教師競合"),
            ("DailyDuplicate", "日内重複"),
            ("ExchangeClassJiritsu", "交流学級自立")
        ]
        
        for _ in range(num_violations):
            vtype, vname = random.choice(violation_types)
            violations.append(ConstraintViolation(
                constraint_type=vtype,
                message=f"{vname} violation in generation {generation}",
                priority=ConstraintPriority.HIGH,
                details={
                    "day": random.randint(0, 4),
                    "period": random.randint(0, 5),
                    "class_id": f"{random.randint(1, 3)}-{random.randint(1, 3)}",
                    "subject": random.choice(["数学", "英語", "理科", "社会"])
                }
            ))
        
        # 学習
        adapter.post_generation_learning(violations, schedule, school)
        
        # 統計を表示
        stats = adapter.learning_system.get_learning_report()
        print(f"  Violations: {num_violations}")
        print(f"  Total learned: {stats['summary']['total_violations']}")
        print(f"  Avoidance rate: {stats['summary']['avoidance_rate']:.2%}")
        print(f"  Unique patterns: {stats['summary']['unique_patterns']}")
        
        # トレンドを表示
        if 'recent_trends' in stats and 'trend' in stats['recent_trends']:
            print(f"  Trend: {stats['recent_trends']['trend']}")
    
    print("\n" + "=" * 80)
    print("Continuous learning demonstration complete!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        # 基本的なデモンストレーション
        demonstrate_learning_system()
        
        # 連続学習のデモンストレーション
        demonstrate_continuous_learning()
        
    except Exception as e:
        logger.error(f"Error during demonstration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)