"""Ultrathink生成戦略

複数のバージョンのUltrathinkジェネレーターを使用し、
フォールバック機構により最適なスケジュールを生成します。
"""
import logging
from typing import Optional, TYPE_CHECKING

from .base_generation_strategy import BaseGenerationStrategy

if TYPE_CHECKING:
    from ....domain.entities.schedule import Schedule
    from ....domain.entities.school import School


class UltrathinkStrategy(BaseGenerationStrategy):
    """Ultrathink Perfect Generatorを使用した生成戦略"""
    
    def __init__(self, constraint_system, followup_loader=None):
        super().__init__(constraint_system)
        self.logger = logging.getLogger(__name__)
        self.followup_loader = followup_loader
        
    def get_name(self) -> str:
        return "ultrathink"
    
    def generate(
        self,
        school: 'School',
        initial_schedule: Optional['Schedule'] = None,
        max_iterations: int = 100,
        **kwargs
    ) -> 'Schedule':
        """Ultrathinkアルゴリズムでスケジュールを生成"""
        followup_data = self._load_followup_data()
        
        # 利用可能なバージョンのみを使用
        versions = [
            (14, self._try_v14),
            (8, self._try_v8),
            (0, self._try_simplified)
        ]
        
        # 各バージョンを順番に試す
        for version, method in versions:
            try:
                schedule = method(school, initial_schedule, followup_data)
                if schedule:
                    self.logger.info(f"V{version if version > 0 else 'Simplified'}での生成に成功しました")
                    return schedule
            except Exception as e:
                self.logger.warning(f"V{version if version > 0 else 'Simplified'}生成でエラー: {e}")
                continue
        
        # 全て失敗した場合は、Advanced CSPにフォールバック
        self.logger.warning("全てのUltrathinkバージョンで失敗。Advanced CSPにフォールバックします。")
        return self._fallback_to_advanced_csp(school, initial_schedule, max_iterations)
    
    def _load_followup_data(self):
        """Follow-upデータを読み込む"""
        if self.followup_loader:
            return self.followup_loader()
        return None
    
    def _try_v8(self, school, initial_schedule, followup_data):
        """V8（教師満足度最適化版）を試す"""
        from ..ultrathink.hybrid_schedule_generator_v8 import HybridScheduleGeneratorV8
        
        self.logger.info("=== Ultrathink V8（教師満足度最適化版）を使用 ===")
        
        generator = HybridScheduleGeneratorV8()
        
        result = generator.generate(
            school=school,
            initial_schedule=initial_schedule
        )
        
        # resultがScheduleオブジェクトか、resultオブジェクトか確認
        schedule = result.schedule if hasattr(result, 'schedule') else result
        
        self._validate_and_log(schedule, school, "V8")
        return schedule
    
    def _try_v7(self, school, initial_schedule, followup_data):
        """V7（並列処理高速版）を試す"""
        from ..ultrathink.hybrid_schedule_generator_v7 import HybridScheduleGeneratorV7
        from ..ultrathink.parallel.parallel_optimization_engine import ParallelOptimizationConfig
        
        self.logger.info("=== Ultrathink V7（並列処理高速版）を使用 ===")
        
        parallel_config = ParallelOptimizationConfig(
            enable_parallel_placement=True,
            max_workers=4
        )
        
        generator = HybridScheduleGeneratorV7(
            enable_logging=True,
            parallel_config=parallel_config
        )
        
        result = generator.generate(
            school=school,
            initial_schedule=initial_schedule,
            target_violations=0,
            time_limit=300,
            followup_data=followup_data
        )
        
        self._validate_and_log(result.schedule, school, "V7")
        return result.schedule
    
    def _try_v6(self, school, initial_schedule, followup_data):
        """V6（学習機能付き版）を試す"""
        from ..ultrathink.hybrid_schedule_generator_v6 import HybridScheduleGeneratorV6
        
        self.logger.info("=== Ultrathink V6（学習機能付き版）を使用 ===")
        
        generator = HybridScheduleGeneratorV6(enable_logging=True)
        result = generator.generate(
            school=school,
            initial_schedule=initial_schedule,
            target_violations=0,
            time_limit=300,
            followup_data=followup_data
        )
        
        self._validate_and_log(result.schedule, school, "V6")
        return result.schedule
    
    def _try_v5(self, school, initial_schedule, followup_data):
        """V5（柔軟な標準時数保証版）を試す"""
        from ..ultrathink.hybrid_schedule_generator_v5 import HybridScheduleGeneratorV5
        
        self.logger.info("=== Ultrathink V5（柔軟な標準時数保証版）を使用 ===")
        
        generator = HybridScheduleGeneratorV5(enable_logging=True)
        result = generator.generate(
            school=school,
            initial_schedule=initial_schedule,
            target_violations=0,
            time_limit=300,
            followup_data=followup_data
        )
        
        self._validate_and_log(result.schedule, school, "V5")
        return result.schedule
    
    def _try_v3(self, school, initial_schedule, followup_data):
        """V3（完全最適化版）を試す"""
        from ..ultrathink.hybrid_schedule_generator_v3 import HybridScheduleGeneratorV3
        
        self.logger.info("=== Ultrathink V3（完全最適化版）を使用 ===")
        
        generator = HybridScheduleGeneratorV3(enable_logging=True)
        result = generator.generate(
            school=school,
            initial_schedule=initial_schedule,
            target_violations=0,
            time_limit=300
        )
        
        self._validate_and_log(result.schedule, school, "V3")
        return result.schedule
    
    def _try_hybrid(self, school, initial_schedule, followup_data):
        """標準ハイブリッド版を試す"""
        from ..ultrathink.hybrid_schedule_generator import HybridScheduleGenerator
        
        self.logger.info("=== Ultrathink ハイブリッドアプローチを使用 ===")
        
        generator = HybridScheduleGenerator(
            learning_file="phase4_learning.json",
            enable_logging=True
        )
        
        result = generator.generate(
            school=school,
            initial_schedule=initial_schedule,
            target_violations=0,
            time_limit=180
        )
        
        self._validate_and_log(result.schedule, school, "Hybrid")
        return result.schedule
    
    def _try_v12(self, school, initial_schedule, followup_data):
        """V12を最終フォールバックとして試す"""
        from ..ultrathink.ultrathink_perfect_generator_v12 import UltrathinkPerfectGeneratorV12
        from ....domain.constraints.base import ConstraintPriority
        
        self.logger.info("=== Ultrathink V12（最終フォールバック）を使用 ===")
        
        # 制約リストを作成
        constraints = []
        for priority in sorted(ConstraintPriority, key=lambda p: p.value, reverse=True):
            for constraint in self.constraint_system.constraints[priority]:
                constraints.append(constraint)
        
        generator = UltrathinkPerfectGeneratorV12()
        schedule = generator.generate(school, constraints, initial_schedule)
        
        self._validate_and_log(schedule, school, "V12")
        return schedule
    
    def _try_v14(self, school, initial_schedule, followup_data):
        """V14（最新版）を試す"""
        from ..ultrathink.ultrathink_perfect_generator_v14 import UltrathinkPerfectGeneratorV14
        
        self.logger.info("=== Ultrathink V14（最新版）を使用 ===")
        
        generator = UltrathinkPerfectGeneratorV14()
        schedule = generator.generate(school, initial_schedule)
        
        self._validate_and_log(schedule, school, "V14")
        return schedule
    
    def _try_simplified(self, school, initial_schedule, followup_data):
        """簡易版を試す"""
        from ..ultrathink.simplified_ultrathink_generator import SimplifiedUltrathinkGenerator
        
        self.logger.info("=== Simplified Ultrathink Generatorを使用 ===")
        
        generator = SimplifiedUltrathinkGenerator()
        schedule = generator.generate(school, initial_schedule)
        
        self._validate_and_log(schedule, school, "Simplified")
        return schedule
    
    def _fallback_to_advanced_csp(self, school, initial_schedule, max_iterations):
        """Advanced CSPアルゴリズムにフォールバック"""
        from ..csp_orchestrator import CSPOrchestrator
        from .constraint_validator_adapter import ConstraintValidatorAdapter
        
        self.logger.info("=== Advanced CSPアルゴリズムを使用 ===")
        
        # UnifiedConstraintSystemをConstraintValidatorImproved互換にアダプト
        constraint_validator = ConstraintValidatorAdapter(self.constraint_system)
        csp_orchestrator = CSPOrchestrator(constraint_validator)
        schedule = csp_orchestrator.generate(school, max_iterations, initial_schedule)
        
        self._validate_and_log(schedule, school, "Advanced CSP")
        return schedule
    
    def _validate_and_log(self, schedule, school, version_name):
        """スケジュールを検証しログ出力"""
        violations = self.validate_schedule(schedule, school)
        
        if not violations:
            self.logger.info(f"✓ {version_name}により全ての制約を満たす完璧なスケジュールを生成しました！")
        else:
            self.logger.warning(f"{version_name}生成完了しましたが、{len(violations)}件の制約違反が残っています")
            self.log_violations(violations)