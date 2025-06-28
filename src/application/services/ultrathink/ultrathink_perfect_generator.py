#!/usr/bin/env python3
"""
Ultrathink Perfect Generator（リファクタリング版）
最初から完璧な時間割を生成するための革新的なジェネレーター

主要な改善点：
1. 制約違反を事前に防ぐプロアクティブな配置戦略
2. テスト期間の完全保護
3. 教師不在情報の厳格な適用
4. 体育館使用の最適化
5. 交流学級の完全同期
6. インテリジェントなバックトラッキング

リファクタリング内容：
- 責任の分離（メタデータ収集、配置戦略、ヘルパー）
- 単一責任原則の適用
- 戦略パターンによる配置ロジックの分離
- 可読性と保守性の向上
"""

from typing import List, Optional
import logging

from ....domain.entities import School, Schedule
from ....domain.constraints.base import Constraint

from .metadata_collector import MetadataCollector
from .constraint_categorizer import ConstraintCategorizer
from .schedule_helpers import ScheduleHelpers
from .placement_strategies import (
    TestPeriodProtectionStrategy,
    FixedSubjectPlacementStrategy,
    JiritsuPlacementStrategy,
    Grade5SynchronizationStrategy,
    RegularSubjectPlacementStrategy,
    ExchangeClassSynchronizationStrategy
)

logger = logging.getLogger(__name__)


class UltrathinkPerfectGenerator:
    """最初から完璧な時間割を生成する革新的ジェネレーター（リファクタリング版）"""
    
    def __init__(self):
        # コンポーネントの初期化
        self.metadata = MetadataCollector()
        self.constraint_categorizer = ConstraintCategorizer()
        self.helpers = ScheduleHelpers(self.metadata)
        
        # 配置戦略の初期化は遅延
        self._strategies = None
    
    def generate(self, school: School, constraints: List[Constraint],
                 initial_schedule: Optional[Schedule] = None) -> Schedule:
        """完璧な時間割を生成
        
        Args:
            school: 学校情報
            constraints: 制約リスト
            initial_schedule: 初期スケジュール（あれば）
            
        Returns:
            Schedule: 生成されたスケジュール
        """
        logger.info("=== Ultrathink Perfect Generator 開始 ===")
        
        # 1. 初期化とデータ収集
        schedule = initial_schedule or Schedule()
        self._collect_metadata(school, constraints, schedule)
        self._categorize_constraints(constraints)
        self._initialize_strategies(constraints)
        
        # 2. 段階的な配置戦略の実行
        self._execute_placement_strategies(schedule, school)
        
        # 3. 最終検証
        self._final_validation(schedule, school)
        
        logger.info(f"=== 生成完了: 割り当て数={len(schedule.get_all_assignments())} ===")
        return schedule
    
    def _collect_metadata(self, school: School, constraints: List[Constraint], 
                         schedule: Schedule) -> None:
        """メタデータの収集"""
        self.metadata.collect_from_schedule(schedule)
        self.metadata.collect_from_constraints(constraints)
    
    def _categorize_constraints(self, constraints: List[Constraint]) -> None:
        """制約を優先度別に分類"""
        self.constraint_categorizer.categorize(constraints)
    
    def _initialize_strategies(self, constraints: List[Constraint]) -> None:
        """配置戦略を初期化"""
        self._strategies = [
            TestPeriodProtectionStrategy(self.helpers, self.metadata),
            FixedSubjectPlacementStrategy(self.helpers, self.metadata),
            JiritsuPlacementStrategy(self.helpers, self.metadata),
            Grade5SynchronizationStrategy(self.helpers, self.metadata),
            RegularSubjectPlacementStrategy(
                self.helpers, self.metadata, constraints
            ),
            ExchangeClassSynchronizationStrategy(self.helpers, self.metadata)
        ]
    
    def _execute_placement_strategies(self, schedule: Schedule, school: School) -> None:
        """配置戦略を順番に実行"""
        total_placed = 0
        
        for strategy in self._strategies:
            strategy_name = strategy.__class__.__name__
            logger.info(f"実行中: {strategy_name}")
            
            placed = strategy.execute(schedule, school)
            total_placed += placed
            
        logger.info(f"総配置数: {total_placed}")
    
    def _final_validation(self, schedule: Schedule, school: School) -> None:
        """最終検証"""
        violations = []
        
        # 全制約をチェック
        all_constraints = self.constraint_categorizer.get_all_constraints()
        
        for constraint in all_constraints:
            result = constraint.validate(schedule, school)
            # ConstraintResultオブジェクトからviolationsを取得
            if hasattr(result, 'violations'):
                violations.extend(result.violations)
        
        if violations:
            logger.warning(f"最終検証で{len(violations)}件の違反を検出")
            # 違反の詳細をログ出力
            for i, violation in enumerate(violations[:5]):
                logger.warning(f"  {i+1}. {violation}")
            if len(violations) > 5:
                logger.warning(f"  ... 他 {len(violations)-5} 件")
        else:
            logger.info("最終検証: 違反なし！")