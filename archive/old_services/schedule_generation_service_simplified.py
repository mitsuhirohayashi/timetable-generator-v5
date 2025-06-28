"""簡潔化されたスケジュール生成サービス（自動最適化統合版）

フェーズ5で自動最適化機能を統合した時間割生成サービス。
UltraOptimizedScheduleGeneratorの自動最適化機能を使用して、
システムが自動的に最適な設定を決定します。
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from ...domain.services.unified_constraint_system import UnifiedConstraintSystem
from ...infrastructure.config.path_manager import PathManager
from .learned_rule_application_service import LearnedRuleApplicationService

# 超最適化生成器と自動最適化システム
from ...domain.services.ultrathink.ultra_optimized_schedule_generator import (
    UltraOptimizedScheduleGenerator,
    UltraOptimizationConfig,
    OptimizationLevel
)
from ...domain.services.ultrathink.auto_optimizer import AutoOptimizer


class ScheduleGenerationService:
    """簡潔化されたスケジュール生成サービス（自動最適化統合版）"""
    
    def __init__(
        self,
        constraint_system: UnifiedConstraintSystem,
        path_manager: PathManager,
        learned_rule_service: Optional[LearnedRuleApplicationService] = None
    ):
        self.constraint_system = constraint_system
        self.path_manager = path_manager
        self.logger = logging.getLogger(__name__)
        self.learned_rule_service = learned_rule_service or LearnedRuleApplicationService()
        
        # 統計情報
        self.generation_stats: Dict[str, Any] = {}
    
    def generate_schedule(
        self,
        school: School,
        initial_schedule: Optional[Schedule] = None,
        max_iterations: int = 100,
        use_advanced_csp: bool = True,
        use_improved_csp: bool = False,
        use_ultrathink: bool = False,
        use_auto_optimization: bool = True,  # 自動最適化フラグ
        search_mode: str = "standard"
    ) -> Schedule:
        """スケジュールを生成
        
        Args:
            school: 学校情報
            initial_schedule: 初期スケジュール
            max_iterations: 最大反復回数
            use_advanced_csp: 高度なCSPアルゴリズムを使用するか
            use_improved_csp: 改良版CSPアルゴリズムを使用するか
            use_ultrathink: Ultrathink生成器を使用するか
            use_auto_optimization: 自動最適化を使用するか（Ultrathink時のみ有効）
            search_mode: 探索モード
            
        Returns:
            生成されたスケジュール
        """
        self.logger.info("=== スケジュール生成を開始 ===")
        self.generation_stats = {
            'start_time': datetime.now(),
            'algorithm_used': 'ultra_optimized' if use_ultrathink else 'improved_csp',
            'auto_optimization': use_auto_optimization and use_ultrathink
        }
        
        # QandAシステムから学習したルールを読み込む
        learned_rules_count = self.learned_rule_service.parse_and_load_rules()
        if learned_rules_count > 0:
            self.logger.info(f"QandAシステムから{learned_rules_count}個のルールを学習しました")
        
        try:
            if use_ultrathink:
                # UltraOptimizedScheduleGeneratorを使用
                self.logger.info("🚀 Ultrathink最適化モードを使用")
                schedule = self._generate_with_ultra_optimized(school, initial_schedule, use_auto_optimization)
            elif use_improved_csp:
                # 改良版CSPアルゴリズムを使用
                schedule = self._generate_with_improved_csp(school, max_iterations, initial_schedule, search_mode)
            elif use_advanced_csp:
                # 高度なCSPアルゴリズムを使用
                schedule = self._generate_with_advanced_csp(school, max_iterations, initial_schedule, search_mode)
            else:
                # レガシーアルゴリズムを使用
                schedule = self._generate_with_legacy_algorithm(school, max_iterations, initial_schedule)
            
            # 学習したルールを適用（Ultrathink以外の場合）
            if not use_ultrathink and learned_rules_count > 0:
                applied_count = self.learned_rule_service.apply_rules_to_schedule(schedule, school)
                if applied_count > 0:
                    self.logger.info(f"{applied_count}個の学習ルールを時間割に適用しました")
            
            # 最終検証
            validation_result = self.constraint_system.validate_schedule(schedule, school)
            self.generation_stats['final_violations'] = len(validation_result.violations)
            
            if not validation_result.is_valid:
                self.logger.warning(
                    f"生成完了しましたが、{len(validation_result.violations)}件の"
                    f"制約違反が残っています"
                )
                self._log_violations(validation_result.violations[:10])
            else:
                self.logger.info("すべての制約を満たすスケジュールを生成しました")
            
            return schedule
            
        finally:
            self.generation_stats['end_time'] = datetime.now()
            self._log_statistics()
    
    def _generate_with_ultra_optimized(
        self,
        school: School,
        initial_schedule: Optional[Schedule],
        use_auto_optimization: bool = True
    ) -> Schedule:
        """UltraOptimizedScheduleGeneratorでスケジュールを生成"""
        self.logger.info("=== UltraOptimizedScheduleGenerator を使用 ===")
        
        # Follow-upデータを読み込む
        followup_data = self._load_followup_data()
        
        if use_auto_optimization:
            # 自動最適化を使用して生成器を作成
            self.logger.info("🤖 自動最適化システムで最適な設定を決定中...")
            
            # AutoOptimizerを使用して最適な設定を決定
            auto_optimizer = AutoOptimizer()
            recommendation = auto_optimizer.recommend_config(
                school=school,
                initial_schedule=initial_schedule
            )
            
            # 決定された設定をログ出力
            self.logger.info(f"📊 推奨設定:")
            self.logger.info(f"  - 信頼度: {recommendation.confidence:.1%}")
            self.logger.info(f"  - 推定実行時間: {recommendation.expected_time:.1f}秒")
            self.logger.info(f"  - 推定品質: {recommendation.expected_quality:.1%}")
            self.logger.info(f"  - 推奨理由: {', '.join(recommendation.reasoning[:3])}")
            
            # 決定された設定で生成器を作成
            generator = UltraOptimizedScheduleGenerator(
                config=recommendation.config,
                enable_logging=True
            )
            
            # 統計情報に自動最適化の結果を記録
            self.generation_stats['auto_optimization_result'] = {
                'confidence': recommendation.confidence,
                'expected_time': recommendation.expected_time,
                'expected_quality': recommendation.expected_quality,
                'reasoning': recommendation.reasoning
            }
            
        else:
            # 手動設定（標準的な設定を使用）
            self.logger.info("標準設定でUltraOptimizedScheduleGeneratorを初期化")
            config = UltraOptimizationConfig(
                optimization_level=OptimizationLevel.BALANCED,
                max_workers=4,
                beam_width=50
            )
            generator = UltraOptimizedScheduleGenerator(
                config=config,
                enable_logging=True
            )
        
        try:
            # スケジュールを生成
            result = generator.generate(
                school=school,
                initial_schedule=initial_schedule,
                followup_data=followup_data
            )
            
            # 統計情報を更新
            self.generation_stats.update({
                'assignments_made': len(result.schedule.get_all_assignments()),
                'teacher_conflicts': result.teacher_conflicts,
                'execution_time': result.execution_time,
                'violations': result.violations,
                'improvements': result.improvements,
                'statistics': result.statistics
            })
            
            # 成功メッセージ
            if result.is_successful():
                self.logger.info("✅ 全ての制約を満たす完璧なスケジュールを生成しました！")
            
            # 教師満足度情報
            if 'teacher_satisfaction' in result.statistics:
                avg_sat = result.statistics['teacher_satisfaction']['average']
                self.logger.info(f"😊 教師満足度: {avg_sat:.1%}")
            
            # 自動最適化の効果を表示
            if use_auto_optimization and 'execution_time' in result.statistics:
                self.logger.info(
                    f"⚡ 自動最適化により最適な設定で生成完了 "
                    f"（実行時間: {result.execution_time:.2f}秒）"
                )
            
            return result.schedule
            
        except Exception as e:
            self.logger.error(f"UltraOptimizedScheduleGenerator でエラー: {e}")
            # シンプルなフォールバック（改良版CSP）
            self.logger.info("改良版CSPアルゴリズムにフォールバック")
            return self._generate_with_improved_csp(school, 100, initial_schedule, "standard")
    
    def _generate_with_improved_csp(
        self,
        school: School,
        max_iterations: int,
        initial_schedule: Optional[Schedule],
        search_mode: str
    ) -> Schedule:
        """改良版CSPアルゴリズムでスケジュールを生成"""
        from ...domain.services.implementations.improved_csp_generator import ImprovedCSPGenerator
        
        self.logger.info("改良版CSPアルゴリズムを使用します")
        generator = ImprovedCSPGenerator(self.constraint_system)
        
        # Follow-up制約を読み込む
        followup_constraints = self._load_followup_data()
        
        return generator.generate(
            school=school,
            initial_schedule=initial_schedule,
            followup_constraints=followup_constraints
        )
    
    def _generate_with_advanced_csp(
        self,
        school: School,
        max_iterations: int,
        initial_schedule: Optional[Schedule],
        search_mode: str
    ) -> Schedule:
        """高度なCSPアルゴリズムでスケジュールを生成"""
        from ...domain.services.csp_orchestrator import CSPOrchestrator
        
        self.logger.info("高度なCSPアルゴリズムを使用します")
        orchestrator = CSPOrchestrator()
        
        return orchestrator.generate(
            school,
            max_iterations,
            initial_schedule
        )
    
    def _generate_with_legacy_algorithm(
        self,
        school: School,
        max_iterations: int,
        initial_schedule: Optional[Schedule]
    ) -> Schedule:
        """レガシーアルゴリズムでスケジュールを生成"""
        from ...domain.services.scheduler import LegacyScheduler
        
        self.logger.info("レガシーアルゴリズムを使用します")
        scheduler = LegacyScheduler()
        
        return scheduler.generate(
            school,
            initial_schedule,
            max_iterations
        )
    
    def _load_followup_data(self) -> Dict[str, Any]:
        """Follow-upデータを読み込む"""
        try:
            from ...infrastructure.parsers.enhanced_followup_parser import EnhancedFollowupParser
            
            followup_path = self.path_manager.get_followup_file_path()
            parser = EnhancedFollowupParser()
            
            return parser.parse(str(followup_path))
            
        except Exception as e:
            self.logger.warning(f"Follow-upデータの読み込みに失敗: {e}")
            return {}
    
    def _log_violations(self, violations: list):
        """制約違反をログ出力"""
        for violation in violations:
            self.logger.warning(f"  - {violation}")
    
    def _log_statistics(self):
        """統計情報をログ出力"""
        stats = self.generation_stats
        
        if 'start_time' in stats and 'end_time' in stats:
            duration = (stats['end_time'] - stats['start_time']).total_seconds()
            self.logger.info(f"⏱️  生成時間: {duration:.2f}秒")
        
        if 'assignments_made' in stats:
            self.logger.info(f"📝 配置された授業数: {stats['assignments_made']}")
        
        if 'teacher_conflicts' in stats:
            self.logger.info(f"⚠️  教師重複: {stats['teacher_conflicts']}件")
        
        if 'final_violations' in stats:
            self.logger.info(f"❌ 最終的な制約違反: {stats['final_violations']}件")
        
        if 'auto_optimization_result' in stats:
            result = stats['auto_optimization_result']
            self.logger.info(f"🤖 自動最適化: 信頼度 {result.get('confidence', 0):.1%} "
                           f"（期待品質: {result.get('expected_quality', 0):.1%}）")
        
        if 'improvements' in stats:
            self.logger.info("📈 改善内容:")
            for improvement in stats['improvements']:
                self.logger.info(f"  ✓ {improvement}")