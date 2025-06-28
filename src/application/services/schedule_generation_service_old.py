"""スケジュール生成サービス

高度なCSPアルゴリズムを使用した時間割生成を管理するサービス。
このサービスは時間割生成の中心的な役割を担い、アルゴリズムの選択、
制約の管理、空きスロットの埋め込みなどを統合的に処理します。
"""
import logging
from typing import Optional, Dict, List, TYPE_CHECKING, Any
from datetime import datetime

if TYPE_CHECKING:
    from ...domain.entities.schedule import Schedule
    from ...domain.entities.school import School
    from ...domain.entities.time_slot import ClassReference
    from ...domain.value_objects.constraint_violation import ConstraintViolation
    from ...domain.services.core.unified_constraint_system import UnifiedConstraintSystem
    from ...infrastructure.config.path_manager import PathManager

from .learned_rule_application_service import LearnedRuleApplicationService
from ...domain.value_objects.time_slot import TimeSlot

class ScheduleGenerationService:
    """スケジュール生成サービス
    
    時間割生成の統合的な管理を行うサービスクラス。
    高度なCSPアルゴリズムとレガシーアルゴリズムの両方をサポートし、
    空きスロットの自動埋め込み機能も提供します。
    
    Attributes:
        constraint_system: 制約システム
        path_manager: パス管理
        logger: ロガー
        generation_stats: 生成統計情報
    """
    
    def __init__(self, 
                 constraint_system: 'UnifiedConstraintSystem',
                 path_manager: 'PathManager',
                 learned_rule_service: Optional[LearnedRuleApplicationService] = None) -> None:
        """ScheduleGenerationServiceを初期化
        
        Args:
            constraint_system: 統一制約システムのインスタンス
            path_manager: パス管理のインスタンス
            learned_rule_service: 学習ルール適用サービス（オプション）
        """
        self.constraint_system = constraint_system
        self.path_manager = path_manager
        self.logger = logging.getLogger(__name__)
        
        # 学習ルール適用サービスの初期化（外部から提供されない場合は新規作成）
        self.learned_rule_service = learned_rule_service or LearnedRuleApplicationService()
        
        # 統計情報の初期化
        self.generation_stats: Dict[str, Any] = {
            'start_time': None,
            'end_time': None,
            'iterations': 0,
            'assignments_made': 0,
            'assignments_failed': 0,
            'violations_fixed': 0,
            'final_violations': 0,
            'empty_slots_filled': 0,
            'algorithm_used': 'advanced_csp'
        }
    
    def generate_schedule(self, 
                         school: 'School',
                         initial_schedule: Optional['Schedule'] = None,
                         max_iterations: int = 100,
                         use_advanced_csp: bool = True,
                         use_improved_csp: bool = False,  # 改良版CSPアルゴリズムを使用するか
                         use_ultrathink: bool = False,  # Ultrathink Perfect Generatorを使用するか
                         use_grade5_priority: bool = False,  # 5組優先配置アルゴリズムを使用するか
                         search_mode: str = "standard"
                         ) -> 'Schedule':
        """スケジュールを生成
        
        Args:
            school: 学校情報
            initial_schedule: 初期スケジュール
            max_iterations: 最大反復回数
            use_advanced_csp: 高度なCSPアルゴリズムを使用するか（デフォルト: True）
            use_ultrathink: Ultrathink Perfect Generatorを使用するか
            
        Returns:
            Schedule: 生成されたスケジュール
        """
        self.logger.info("=== スケジュール生成を開始 ===")
        self.generation_stats['start_time'] = datetime.now()
        
        # QandAシステムから学習したルールを読み込む
        learned_rules_count = self.learned_rule_service.parse_and_load_rules()
        if learned_rules_count > 0:
            self.logger.info(f"QandAシステムから{learned_rules_count}個のルールを学習しました")
        
        try:
            if use_ultrathink:
                # Ultrathink Perfect Generatorを使用
                self.logger.info("Ultrathink Perfect Generatorを使用してスケジュールを生成します")
                self.generation_stats['algorithm_used'] = 'ultrathink_perfect'
                schedule = self._generate_with_ultrathink(school, initial_schedule)
            elif use_grade5_priority:
                # 5組優先配置アルゴリズムを使用
                self.logger.info("5組優先配置アルゴリズムを使用してスケジュールを生成します")
                self.generation_stats['algorithm_used'] = 'grade5_priority'
                schedule = self._generate_with_grade5_priority(school, initial_schedule)
            elif use_improved_csp:
                # 改良版CSPアルゴリズムを使用
                self.logger.info("改良版CSPアルゴリズムを使用してスケジュールを生成します")
                self.generation_stats['algorithm_used'] = 'improved_csp'
                schedule = self._generate_with_improved_csp(school, max_iterations, initial_schedule, search_mode)
            elif use_advanced_csp:
                # 高度なCSPアルゴリズムを使用（デフォルト）
                self.logger.info("高度なCSPアルゴリズムを使用してスケジュールを生成します")
                self.generation_stats['algorithm_used'] = 'advanced_csp'
                schedule = self._generate_with_advanced_csp(school, max_iterations, initial_schedule, search_mode)
            else:
                # レガシーアルゴリズムを使用
                self.logger.info("レガシーアルゴリズムを使用してスケジュールを生成します")
                self.generation_stats['algorithm_used'] = 'legacy'
                schedule = self._generate_with_legacy_algorithm(school, max_iterations, initial_schedule)
            
            # Ultrathinkの場合は学習ルール適用と空きスロット埋めをスキップ
            if not use_ultrathink:
                # 学習したルールを適用して問題を修正
                if learned_rules_count > 0:
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
    
    def _generate_with_ultrathink(self, school: 'School',
                                 initial_schedule: Optional['Schedule']) -> 'Schedule':
        """Ultrathink Perfect Generatorでスケジュールを生成
        
        フェーズ5ハイブリッドアプローチを使用して、柔軟な標準時数保証を実現します。
        """
        # Follow-upデータを読み込む
        followup_data = self._load_followup_data()
        
        # V8の教師満足度最適化版を試す
        try:
            from .ultrathink.hybrid_schedule_generator_v8 import HybridScheduleGeneratorV8
            from .ultrathink.preference.teacher_preference_learning_system import TeacherOptimizationConfig
            
            self.logger.info("=== Ultrathink ハイブリッドアプローチV8（教師満足度最適化版）を使用 ===")
            
            # 教師最適化設定
            teacher_config = TeacherOptimizationConfig(
                enable_teacher_preference=True,
                satisfaction_weight=0.3,
                min_teacher_satisfaction=0.6,
                max_daily_hours=5,
                prefer_continuous_classes=0.7,
                collaborative_teaching_bonus=0.1,
                new_teacher_support=True,
                workload_balance_weight=0.2
            )
            
            generator = HybridScheduleGeneratorV8(
                enable_logging=True,
                teacher_config=teacher_config
            )
            
            result = generator.generate(
                school=school,
                initial_schedule=initial_schedule,
                target_violations=0,
                time_limit=300,
                followup_data=followup_data  # Follow-upデータを渡す
            )
            
            schedule = result.schedule
            
            # 統計情報を更新
            self.generation_stats['assignments_made'] = len(schedule.get_all_assignments())
            self.generation_stats['phase2_attempts'] = result.statistics.get('phase2_attempts', 0)
            self.generation_stats['phase3_iterations'] = result.statistics.get('phase3_iterations', 0)
            self.generation_stats['teacher_conflicts'] = result.teacher_conflicts
            self.generation_stats['standard_hours_met'] = result.statistics.get('standard_hours_met', {})
            
            # 最終検証
            validation_result = self.constraint_system.validate_schedule(schedule, school)
            self.generation_stats['final_violations'] = len(validation_result.violations)
            
            if result.teacher_conflicts == 0:
                self.logger.info("✓ 教師重複が完全に解消されました！")
            
            # 標準時数の達成状況を表示
            hours_info = result.statistics.get('standard_hours_met', {})
            if hours_info.get('total_subjects', 0) > 0:
                met_rate = hours_info['met'] / hours_info['total_subjects'] * 100
                self.logger.info(f"✓ 標準時数達成率: {met_rate:.1f}%")
            
            if not validation_result.is_valid:
                self.logger.warning(
                    f"ハイブリッドV3生成完了しましたが、{len(validation_result.violations)}件の"
                    f"制約違反が残っています"
                )
                self._log_violations(validation_result.violations[:10])
            else:
                self.logger.info("ハイブリッドアプローチV3により全ての制約を満たす完璧なスケジュールを生成しました！")
                
            # 統計情報を更新
            self.generation_stats['assignments_made'] = len(schedule.get_all_assignments())
            self.generation_stats['phase2_attempts'] = result.statistics.get('phase2_attempts', 0)
            self.generation_stats['phase3_iterations'] = result.statistics.get('phase3_iterations', 0)
            self.generation_stats['teacher_conflicts'] = result.teacher_conflicts
            self.generation_stats['standard_hours_met'] = result.statistics.get('standard_hours_met', {})
            self.generation_stats['flexible_satisfaction'] = result.statistics.get('flexible_satisfaction_rate', 0)
            
            # 学習統計を追加
            if 'learning_stats' in result.statistics:
                self.generation_stats['learning_stats'] = result.statistics['learning_stats']
                self.logger.info("✓ 学習機能が動作しています")
                self.logger.info(f"  学習済みパターン: {result.statistics['learning_stats'].get('total_patterns', 0)}個")
                self.logger.info(f"  回避された違反: {result.statistics['learning_stats'].get('avoided_violations', 0)}件")
            
            # 最終検証
            validation_result = self.constraint_system.validate_schedule(schedule, school)
            self.generation_stats['final_violations'] = len(validation_result.violations)
            
            if result.teacher_conflicts == 0:
                self.logger.info("✓ 教師重複が完全に解消されました！")
            
            # 柔軟な標準時数の達成状況を表示
            if 'flexible_satisfaction_rate' in result.statistics:
                rate = result.statistics['flexible_satisfaction_rate'] * 100
                self.logger.info(f"✓ 柔軟な標準時数満足度: {rate:.1f}%")
                if 'special_circumstances' in result.statistics:
                    self.logger.info(f"  特別な状況: {result.statistics['special_circumstances']}件")
            
            if not validation_result.is_valid:
                self.logger.warning(
                    f"ハイブリッドV6生成完了しましたが、{len(validation_result.violations)}件の"
                    f"制約違反が残っています"
                )
                self._log_violations(validation_result.violations[:10])
            else:
                self.logger.info("ハイブリッドアプローチV6により全ての制約を満たす完璧なスケジュールを生成しました！")
            
            return schedule
            
        except Exception as e:
            self.logger.warning(f"V8生成でエラー: {e}. V7にフォールバック")
        
        # V7の並列処理高速版にフォールバック
        try:
            from .ultrathink.hybrid_schedule_generator_v7 import HybridScheduleGeneratorV7
            from .ultrathink.parallel.parallel_optimization_engine import ParallelOptimizationConfig
            
            self.logger.info("=== Ultrathink ハイブリッドアプローチV7（並列処理高速版）を使用 ===")
            
            # 並列処理設定
            parallel_config = ParallelOptimizationConfig(
                enable_parallel_placement=True,
                enable_parallel_verification=True,
                enable_parallel_search=True,
                max_workers=4,  # 安定性のため4ワーカーに制限
                use_threads=False,
                batch_size=50,
                strategy_time_limit=60,
                local_search_neighbors=4,
                sa_populations=4
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
            
            schedule = result.schedule
            
            # 統計情報を更新
            self.generation_stats['assignments_made'] = len(schedule.get_all_assignments())
            self.generation_stats['phase2_attempts'] = result.statistics.get('phase2_attempts', 0)
            self.generation_stats['phase3_iterations'] = result.statistics.get('phase3_iterations', 0)
            self.generation_stats['teacher_conflicts'] = result.teacher_conflicts
            self.generation_stats['standard_hours_met'] = result.statistics.get('standard_hours_met', {})
            self.generation_stats['flexible_satisfaction'] = result.statistics.get('flexible_satisfaction_rate', 0)
            
            # 並列処理統計を追加
            if 'parallel_stats' in result.statistics:
                self.generation_stats['parallel_stats'] = result.statistics['parallel_stats']
                self.logger.info("✓ 並列処理が動作しています")
                self.logger.info(f"  使用ワーカー数: {result.statistics['parallel_stats'].get('workers', 0)}個")
                self.logger.info(f"  並列タスク数: {result.statistics['parallel_stats'].get('total_tasks', 0)}件")
            
            # 最終検証
            validation_result = self.constraint_system.validate_schedule(schedule, school)
            self.generation_stats['final_violations'] = len(validation_result.violations)
            
            if result.teacher_conflicts == 0:
                self.logger.info("✓ 教師重複が完全に解消されました！")
            
            # 柔軟な標準時数の達成状況を表示
            if 'flexible_satisfaction_rate' in result.statistics:
                rate = result.statistics['flexible_satisfaction_rate'] * 100
                self.logger.info(f"✓ 柔軟な標準時数満足度: {rate:.1f}%")
                if 'special_circumstances' in result.statistics:
                    self.logger.info(f"  特別な状況: {result.statistics['special_circumstances']}件")
            
            if not validation_result.is_valid:
                self.logger.warning(
                    f"ハイブリッドV7生成完了しましたが、{len(validation_result.violations)}件の"
                    f"制約違反が残っています"
                )
                self._log_violations(validation_result.violations[:10])
            else:
                self.logger.info("ハイブリッドアプローチV7により全ての制約を満たす完璧なスケジュールを生成しました！")
            
            return schedule
            
        except Exception as e:
            self.logger.warning(f"V7生成でエラー: {e}. V6にフォールバック")
        
        # V6の学習機能付き版にフォールバック
        try:
            from .ultrathink.hybrid_schedule_generator_v6 import HybridScheduleGeneratorV6
            
            self.logger.info("=== Ultrathink ハイブリッドアプローチV6（学習機能付き版）を使用 ===")
            
            generator = HybridScheduleGeneratorV6(enable_logging=True)
            
            result = generator.generate(
                school=school,
                initial_schedule=initial_schedule,
                target_violations=0,
                time_limit=300,
                followup_data=followup_data
            )
            
            schedule = result.schedule
            
            # 統計情報を更新
            self.generation_stats['assignments_made'] = len(schedule.get_all_assignments())
            self.generation_stats['phase2_attempts'] = result.statistics.get('phase2_attempts', 0)
            self.generation_stats['phase3_iterations'] = result.statistics.get('phase3_iterations', 0)
            self.generation_stats['teacher_conflicts'] = result.teacher_conflicts
            self.generation_stats['standard_hours_met'] = result.statistics.get('standard_hours_met', {})
            self.generation_stats['flexible_satisfaction'] = result.statistics.get('flexible_satisfaction_rate', 0)
            
            # 学習統計を追加
            if 'learning_stats' in result.statistics:
                self.generation_stats['learning_stats'] = result.statistics['learning_stats']
                self.logger.info("✓ 学習機能が動作しています")
                self.logger.info(f"  学習済みパターン: {result.statistics['learning_stats'].get('total_patterns', 0)}個")
                self.logger.info(f"  回避された違反: {result.statistics['learning_stats'].get('avoided_violations', 0)}件")
            
            # 最終検証
            validation_result = self.constraint_system.validate_schedule(schedule, school)
            self.generation_stats['final_violations'] = len(validation_result.violations)
            
            if result.teacher_conflicts == 0:
                self.logger.info("✓ 教師重複が完全に解消されました！")
            
            # 柔軟な標準時数の達成状況を表示
            if 'flexible_satisfaction_rate' in result.statistics:
                rate = result.statistics['flexible_satisfaction_rate'] * 100
                self.logger.info(f"✓ 柔軟な標準時数満足度: {rate:.1f}%")
                if 'special_circumstances' in result.statistics:
                    self.logger.info(f"  特別な状況: {result.statistics['special_circumstances']}件")
            
            if not validation_result.is_valid:
                self.logger.warning(
                    f"ハイブリッドV6生成完了しましたが、{len(validation_result.violations)}件の"
                    f"制約違反が残っています"
                )
                self._log_violations(validation_result.violations[:10])
            else:
                self.logger.info("ハイブリッドアプローチV6により全ての制約を満たす完璧なスケジュールを生成しました！")
            
            return schedule
            
        except Exception as e:
            self.logger.warning(f"V6生成でエラー: {e}. V5にフォールバック")
        
        # V5の柔軟な標準時数保証版にフォールバック
        try:
            from .ultrathink.hybrid_schedule_generator_v5 import HybridScheduleGeneratorV5
            
            self.logger.info("=== Ultrathink ハイブリッドアプローチV5（柔軟な標準時数保証版）を使用 ===")
            
            generator = HybridScheduleGeneratorV5(enable_logging=True)
            
            result = generator.generate(
                school=school,
                initial_schedule=initial_schedule,
                target_violations=0,
                time_limit=300,
                followup_data=followup_data
            )
            
            schedule = result.schedule
            
            # 統計情報を更新
            self.generation_stats['assignments_made'] = len(schedule.get_all_assignments())
            self.generation_stats['phase2_attempts'] = result.statistics.get('phase2_attempts', 0)
            self.generation_stats['phase3_iterations'] = result.statistics.get('phase3_iterations', 0)
            self.generation_stats['teacher_conflicts'] = result.teacher_conflicts
            self.generation_stats['standard_hours_met'] = result.statistics.get('standard_hours_met', {})
            self.generation_stats['flexible_satisfaction'] = result.statistics.get('flexible_satisfaction_rate', 0)
            
            # 最終検証
            validation_result = self.constraint_system.validate_schedule(schedule, school)
            self.generation_stats['final_violations'] = len(validation_result.violations)
            
            if result.teacher_conflicts == 0:
                self.logger.info("✓ 教師重複が完全に解消されました！")
            
            # 柔軟な標準時数の達成状況を表示
            if 'flexible_satisfaction_rate' in result.statistics:
                rate = result.statistics['flexible_satisfaction_rate'] * 100
                self.logger.info(f"✓ 柔軟な標準時数満足度: {rate:.1f}%")
                if 'special_circumstances' in result.statistics:
                    self.logger.info(f"  特別な状況: {result.statistics['special_circumstances']}件")
            
            if not validation_result.is_valid:
                self.logger.warning(
                    f"ハイブリッドV5生成完了しましたが、{len(validation_result.violations)}件の"
                    f"制約違反が残っています"
                )
                self._log_violations(validation_result.violations[:10])
            else:
                self.logger.info("ハイブリッドアプローチV5により全ての制約を満たす完璧なスケジュールを生成しました！")
            
            return schedule
            
        except Exception as e:
            self.logger.warning(f"V5生成でエラー: {e}. V3にフォールバック")
            
            # V3にフォールバック
            try:
                from .ultrathink.hybrid_schedule_generator_v3 import HybridScheduleGeneratorV3
                
                self.logger.info("=== Ultrathink ハイブリッドアプローチV3（完全最適化版）を使用 ===")
                
                generator = HybridScheduleGeneratorV3(enable_logging=True)
                
                result = generator.generate(
                    school=school,
                    initial_schedule=initial_schedule,
                    target_violations=0,
                    time_limit=300
                )
                
                schedule = result.schedule
                
                # 統計情報を更新
                self.generation_stats['assignments_made'] = len(schedule.get_all_assignments())
                self.generation_stats['phase2_attempts'] = result.statistics.get('phase2_attempts', 0)
                self.generation_stats['phase3_iterations'] = result.statistics.get('phase3_iterations', 0)
                self.generation_stats['teacher_conflicts'] = result.teacher_conflicts
                
                # 最終検証
                validation_result = self.constraint_system.validate_schedule(schedule, school)
                self.generation_stats['final_violations'] = len(validation_result.violations)
                
                if result.teacher_conflicts == 0:
                    self.logger.info("✓ 教師重複が完全に解消されました！")
                
                if not validation_result.is_valid:
                    self.logger.warning(
                        f"ハイブリッドV2生成完了しましたが、{len(validation_result.violations)}件の"
                        f"制約違反が残っています"
                    )
                    self._log_violations(validation_result.violations[:10])
                else:
                    self.logger.info("ハイブリッドアプローチV2により全ての制約を満たす完璧なスケジュールを生成しました！")
                    
            except Exception as e2:
                self.logger.warning(f"V2生成でもエラー: {e2}. 標準ハイブリッドにフォールバック")
            
            from .ultrathink.hybrid_schedule_generator import HybridScheduleGenerator
            
            self.logger.info("=== Ultrathink ハイブリッドアプローチ（フェーズ4）を使用 ===")
            
            # ハイブリッド生成器を初期化
            generator = HybridScheduleGenerator(
                learning_file="phase4_learning.json",
                enable_logging=True
            )
            
            # ハイブリッドアプローチで生成
            try:
                result = generator.generate(
                    school=school,
                    initial_schedule=initial_schedule,
                    target_violations=0,  # 違反0を目標
                    time_limit=180       # 3分制限
                )
                
                schedule = result.schedule
                
                # 統計情報を更新
                self.generation_stats['assignments_made'] = len(schedule.get_all_assignments())
                self.generation_stats['phase2_attempts'] = result.statistics.get('phase2_attempts', 0)
                self.generation_stats['phase3_iterations'] = result.statistics.get('phase3_iterations', 0)
                self.generation_stats['teacher_conflicts'] = result.statistics.get('teacher_conflicts', 0)
                
                # 最終検証
                validation_result = self.constraint_system.validate_schedule(schedule, school)
                self.generation_stats['final_violations'] = len(validation_result.violations)
                
                if result.statistics.get('teacher_conflicts', 0) == 0:
                    self.logger.info("✓ 教師重複が完全に解消されました！")
                
                if not validation_result.is_valid:
                    self.logger.warning(
                        f"ハイブリッド生成完了しましたが、{len(validation_result.violations)}件の"
                        f"制約違反が残っています"
                    )
                    self._log_violations(validation_result.violations[:10])
                else:
                    self.logger.info("ハイブリッドアプローチにより全ての制約を満たす完璧なスケジュールを生成しました！")
                    
            except Exception as e:
                self.logger.error(f"ハイブリッド生成中にエラーが発生しました: {e}")
                # フォールバックとしてV12を使用
                self.logger.info("フォールバック: V12ジェネレーターを使用します")
                from .ultrathink.ultrathink_perfect_generator_v12 import UltrathinkPerfectGeneratorV12
                
                constraints = []
                from ...domain.constraints.base import ConstraintPriority
                for priority in sorted(ConstraintPriority, key=lambda p: p.value, reverse=True):
                    for constraint in self.constraint_system.constraints[priority]:
                        constraints.append(constraint)
                
                generator_v12 = UltrathinkPerfectGeneratorV12()
                schedule = generator_v12.generate(school, constraints, initial_schedule)
                
                self.generation_stats['assignments_made'] = len(schedule.get_all_assignments())
                validation_result = self.constraint_system.validate_schedule(schedule, school)
                self.generation_stats['final_violations'] = len(validation_result.violations)
        
        return schedule
    
    def _generate_with_improved_csp(self, school: 'School',
                                   max_iterations: int,
                                   initial_schedule: Optional['Schedule'],
                                   search_mode: str = "standard") -> 'Schedule':
        """改良版CSPアルゴリズムでスケジュールを生成
        
        キャッシング、バックトラッキング、優先度ベース配置を活用した
        高度な制約充足アルゴリズムを使用します。
        """
        
        self.logger.info("=== 改良版CSPアルゴリズムを使用 ===")
        
        # テスト期間保持チェッカーを初期化
        from ...domain.services.core.test_period_preservation_check import TestPeriodPreservationChecker
        preservation_checker = TestPeriodPreservationChecker()
        
        # 入力データの補正（初期スケジュールがある場合）
        if initial_schedule:
            from ..input_data_corrector import InputDataCorrector
            corrector = InputDataCorrector()
            corrections = corrector.correct_input_schedule(initial_schedule, school)
            if corrections > 0:
                self.logger.info(f"入力データを{corrections}箇所補正しました")
        
        # 改良版コンポーネントを使用
        from ...domain.services.unified_constraint_validator import UnifiedConstraintValidator
        from .csp_orchestrator import CSPOrchestratorImproved
        from ...domain.services.implementations.priority_based_placement_service_improved import PriorityBasedPlacementServiceImproved
        
        # 統合制約検証器を作成
        improved_validator = UnifiedConstraintValidator(
            unified_system=self.constraint_system
        )
        
        # 改良版CSPオーケストレーターを作成
        csp_orchestrator = CSPOrchestratorImproved(improved_validator)
        
        # 生成実行
        schedule = csp_orchestrator.generate(school, max_iterations, initial_schedule)
        
        # テスト期間データ保持チェック（CSP生成後）
        if initial_schedule:
            self.logger.warning("=== CSP生成後のテスト期間データチェック ===")
            preservation_checker.check_test_period_preservation(initial_schedule, schedule, school)
        
        # 統計情報を更新
        self.generation_stats['assignments_made'] = len(schedule.get_all_assignments())
        
        # 空きスロット埋め（常に実行）
        self._fill_empty_slots_smartly(schedule, school)
        
        # テスト期間データ保持チェック（空きスロット埋め後）
        if initial_schedule:
            self.logger.warning("=== 空きスロット埋め後のテスト期間データチェック ===")
            preservation_checker.check_test_period_preservation(initial_schedule, schedule, school)
        
        return schedule
    
    def _generate_with_grade5_priority(self, school: 'School',
                                      initial_schedule: Optional['Schedule']) -> 'Schedule':
        """5組優先配置アルゴリズムでスケジュールを生成
        
        5組を最初に一括配置することで、教師重複を大幅に削減します。
        """
        self.logger.info("=== 5組優先配置アルゴリズムを使用 ===")
        
        # 改善版CSP生成器を使用
        from ...domain.services.implementations.improved_csp_generator import ImprovedCSPGenerator
        
        # 生成器を初期化
        generator = ImprovedCSPGenerator(self.constraint_system)
        
        # Follow-up制約を読み込む
        followup_constraints = self._load_followup_data()
        
        # 生成実行
        schedule = generator.generate(
            school=school,
            initial_schedule=initial_schedule,
            followup_constraints=followup_constraints
        )
        
        # 統計情報を更新
        self.generation_stats['assignments_made'] = len(schedule.get_all_assignments())
        
        return schedule
    
    def _generate_with_advanced_csp(self, school: 'School', 
                                    max_iterations: int,
                                    initial_schedule: Optional['Schedule'],
                                    search_mode: str = "standard") -> 'Schedule':
        """高度なCSPアルゴリズムでスケジュールを生成"""
        # テスト期間保持チェッカーを初期化
        from ...domain.services.core.test_period_preservation_check import TestPeriodPreservationChecker
        preservation_checker = TestPeriodPreservationChecker()
        
        # 入力データの補正（初期スケジュールがある場合）
        if initial_schedule:
            # デバッグ: 補正前のテスト期間データを確認
            test_period_count = 0
            test_days = ["月", "火", "水"]
            test_periods_map = {("月", 1), ("月", 2), ("月", 3), ("火", 1), ("火", 2), ("火", 3), ("水", 1), ("水", 2)}
            for day, period in test_periods_map:
                time_slot = TimeSlot(day, period)
                for class_ref in school.get_all_classes():
                    assignment = initial_schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        test_period_count += 1
            self.logger.info(f"InputDataCorrector呼び出し前のテスト期間データ数: {test_period_count}")
            
            from ..input_data_corrector import InputDataCorrector
            corrector = InputDataCorrector()
            corrections = corrector.correct_input_schedule(initial_schedule, school)
            if corrections > 0:
                self.logger.info(f"入力データを{corrections}箇所補正しました")
        
        # ConstraintValidatorアダプターを作成
        class ConstraintValidatorAdapter:
            def __init__(self, unified_system):
                self.unified_system = unified_system
                self.logger = logging.getLogger(__name__ + '.ConstraintValidatorAdapter')
            
            def check_assignment(self, schedule, school, time_slot, assignment):
                """UnifiedConstraintSystemのcheck_before_assignmentメソッドをConstraintValidatorインターフェースに適合させる"""
                from ...domain.services.core.unified_constraint_system import AssignmentContext
                context = AssignmentContext(
                    schedule=schedule,
                    school=school,
                    time_slot=time_slot,
                    assignment=assignment
                )
                result, reasons = self.unified_system.check_before_assignment(context)
                # タプル(bool, str)を返す
                error_msg = "; ".join(reasons) if reasons else None
                
                # デバッグログ
                if not result and reasons:
                    self.logger.debug(f"制約違反: {assignment.class_ref} {assignment.subject.name} @ {time_slot} - {error_msg}")
                
                return result, error_msg
            
            def validate_all(self, schedule, school):
                """スケジュール全体の検証"""
                validation_result = self.unified_system.validate_schedule(schedule, school)
                return validation_result.violations
            
            def clear_cache(self):
                """キャッシュクリア（互換性のため空実装）"""
                pass
            
            def validate_all_constraints(self, schedule, school):
                """全ての制約を検証（互換性のため）"""
                return self.validate_all(schedule, school)
        
        # アダプターを作成
        adapter = ConstraintValidatorAdapter(self.constraint_system)
        
        # search_modeに基づいて適切なOrchestratorを選択
        if search_mode != "standard":
            # 高度な探索モードを使用
            from .csp_orchestrator import AdvancedCSPOrchestrator, SearchMode
            
            # search_modeをSearchMode列挙型に変換
            mode_map = {
                "priority": SearchMode.PRIORITY,
                "smart": SearchMode.SMART,
                "hybrid": SearchMode.HYBRID
            }
            search_enum = mode_map.get(search_mode, SearchMode.HYBRID)
            
            self.logger.info(f"高度な探索モード ({search_enum.value}) を使用します")
            csp_orchestrator = AdvancedCSPOrchestrator(adapter, None, search_enum)
        else:
            # 標準のCSPOrchestratorを使用
            from .csp_orchestrator import CSPOrchestrator
            csp_orchestrator = CSPOrchestrator(adapter)
        
        # 生成実行
        schedule = csp_orchestrator.generate(school, max_iterations, initial_schedule)
        
        # テスト期間データ保持チェック（CSP生成後）
        if initial_schedule:
            self.logger.warning("=== CSP生成後のテスト期間データチェック ===")
            preservation_checker.check_test_period_preservation(initial_schedule, schedule, school)
        
        # 統計情報を更新
        self.generation_stats['assignments_made'] = len(schedule.get_all_assignments())
        
        # 空きスロット埋め（常に実行）
        self._fill_empty_slots_smartly(schedule, school)
        
        # テスト期間データ保持チェック（空きスロット埋め後）
        if initial_schedule:
            self.logger.warning("=== 空きスロット埋め後のテスト期間データチェック ===")
            preservation_checker.check_test_period_preservation(initial_schedule, schedule, school)
        
        return schedule
    
    def _generate_with_legacy_algorithm(self, school: 'School',
                                      max_iterations: int,
                                      initial_schedule: Optional['Schedule']) -> 'Schedule':
        """レガシーアルゴリズムでスケジュールを生成"""
        # 1. 初期スケジュールの準備
        if initial_schedule:
            schedule = self._prepare_initial_schedule(initial_schedule, school)
        else:
            from ...domain.entities.schedule import Schedule
            schedule = Schedule()
        
        # 2. 必須配置の実行
        self._place_required_subjects(schedule, school)
        
        # 3. 空きコマの埋め込み
        self._fill_empty_slots(schedule, school)
        
        # 4. 制約違反の修正
        self._fix_violations(schedule, school, max_iterations)
        
        return schedule
    
    def _prepare_initial_schedule(self, initial_schedule: 'Schedule', 
                                 school: 'School') -> 'Schedule':
        """初期スケジュールの準備
        
        初期スケジュールをコピーし、固定教科のロックと初期違反の削除を行います。
        
        Args:
            initial_schedule: 元となる初期スケジュール
            school: 学校情報
            
        Returns:
            準備された初期スケジュール（元のスケジュールは変更されません）
        """
        self.logger.info("初期スケジュールを準備中...")
        
        # 初期スケジュールのコピーを作成
        schedule = self._copy_schedule(initial_schedule)
        
        # 固定教科のロック
        self._lock_fixed_subjects(schedule)
        
        # 初期違反の削除
        self._remove_initial_violations(schedule, school)
        
        return schedule
    
    def _place_required_subjects(self, schedule: 'Schedule', school: 'School') -> None:
        """必須教科の配置"""
        self.logger.info("必須教科を配置中...")
        
        # 各クラスの必須教科を配置
        for class_ref in school.get_all_classes():
            self._place_class_requirements(schedule, school, class_ref)
    
    def _fill_empty_slots(self, schedule: 'Schedule', school: 'School') -> None:
        """空きコマの埋め込み"""
        self.logger.info("空きコマを埋め込み中...")
        
        # 5組の同期処理
        self._synchronize_grade5(schedule, school)
        
        # 交流学級の同期処理
        self._synchronize_exchange_classes(schedule, school)
        
        # 人間の時間割作成方法で空きコマを埋める
        self._fill_with_human_method(schedule, school)
    
    def _fix_violations(self, schedule: 'Schedule', school: 'School', 
                       max_iterations: int) -> None:
        """制約違反の修正"""
        self.logger.info("制約違反を修正中...")
        
        for iteration in range(max_iterations):
            self.generation_stats['iterations'] = iteration + 1
            
            # 現在の違反を検証
            validation_result = self.constraint_system.validate_schedule(schedule, school)
            
            if validation_result.is_valid:
                self.logger.info(f"反復{iteration + 1}回で全制約を満たしました")
                break
            
            # 違反を修正
            fixed_count = self._fix_specific_violations(
                schedule, school, validation_result.violations
            )
            
            if fixed_count == 0:
                self.logger.warning("これ以上の修正ができません")
                break
            
            self.generation_stats['violations_fixed'] += fixed_count
    
    def _copy_schedule(self, original: 'Schedule') -> 'Schedule':
        """スケジュールのコピーを作成"""
        from ...domain.entities.schedule import Schedule
        
        copy = Schedule()
        
        # すべての割り当てをコピー
        for time_slot, assignment in original.get_all_assignments():
            copy.assign(time_slot, assignment)
        
        # ロック状態をコピー
        for time_slot, assignment in original.get_all_assignments():
            if original.is_locked(time_slot, assignment.class_ref):
                copy.lock_cell(time_slot, assignment.class_ref)
        
        return copy
    
    def _lock_fixed_subjects(self, schedule: 'Schedule') -> None:
        """固定教科をロック"""
        fixed_subjects = ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"]
        
        locked_count = 0
        for time_slot, assignment in schedule.get_all_assignments():
            if assignment.subject.name in fixed_subjects:
                if not schedule.is_locked(time_slot, assignment.class_ref):
                    schedule.lock_cell(time_slot, assignment.class_ref)
                    locked_count += 1
        
        self.logger.info(f"{locked_count}個の固定教科をロックしました")
    
    def _remove_initial_violations(self, schedule: 'Schedule', school: 'School') -> None:
        """初期違反を削除"""
        # 教員不在違反の削除
        removed = self._remove_teacher_absence_violations(schedule, school)
        
        # 体育館制約違反の削除
        removed += self._remove_gym_violations(schedule, school)
        
        self.logger.info(f"初期違反を{removed}件削除しました")
    
    def _place_class_requirements(self, schedule: 'Schedule', school: 'School',
                                 class_ref: 'ClassReference') -> None:
        """クラスの必須教科を配置"""
        # レガシー実装の詳細は省略
        pass
    
    def _synchronize_grade5(self, schedule: 'Schedule', school: 'School') -> None:
        """5組の同期処理"""
        from ...domain.services.grade5_synchronizer_refactored import RefactoredGrade5Synchronizer
        
        synchronizer = RefactoredGrade5Synchronizer(self.constraint_system)
        synchronizer.synchronize_grade5_classes(schedule, school)
    
    def _synchronize_exchange_classes(self, schedule: 'Schedule', school: 'School') -> None:
        """交流学級の同期処理"""
        from ...domain.services.exchange_class_synchronizer import ExchangeClassSynchronizer
        
        synchronizer = ExchangeClassSynchronizer()
        synchronizer.synchronize_all_exchange_classes(schedule, school)
    
    def _fill_with_human_method(self, schedule: 'Schedule', school: 'School') -> None:
        """人間の時間割作成方法で空きコマを埋める"""
        from ...domain.services.human_like_scheduler import HumanLikeScheduler
        
        self.logger.info("人間の時間割作成方法で最適化中...")
        
        # HumanLikeSchedulerを使用
        human_scheduler = HumanLikeScheduler(self.constraint_system)
        
        # 人間の方法でスケジュールを最適化
        human_scheduler.optimize_schedule(schedule, school)
        
        # 結果を反映（scheduleは参照渡しなので、変更が反映される）
        self.logger.info("人間の時間割作成方法での最適化が完了しました")
    
    def _fix_specific_violations(self, schedule: 'Schedule', school: 'School',
                               violations: List['ConstraintViolation']) -> int:
        """特定の違反を修正"""
        fixed_count = 0
        
        for violation in violations:
            if self._try_fix_violation(schedule, school, violation):
                fixed_count += 1
        
        return fixed_count
    
    def _try_fix_violation(self, schedule: 'Schedule', school: 'School',
                          violation: 'ConstraintViolation') -> bool:
        """違反の修正を試みる"""
        # レガシー実装の詳細は省略
        return False
    
    def _remove_teacher_absence_violations(self, schedule: 'Schedule', 
                                         school: 'School') -> int:
        """教員不在違反を削除"""
        removed_count = 0
        
        # 固定科目のセット
        fixed_subjects = {"欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行", "行事"}
        
        for time_slot, assignment in list(schedule.get_all_assignments()):
            # 固定科目は削除しない
            if assignment.subject.name in fixed_subjects:
                continue
                
            if assignment.teacher and school.is_teacher_unavailable(
                time_slot.day, time_slot.period, assignment.teacher
            ):
                if not schedule.is_locked(time_slot, assignment.class_ref):
                    schedule.remove_assignment(time_slot, assignment.class_ref)
                    removed_count += 1
        
        return removed_count
    
    def _remove_gym_violations(self, schedule: 'Schedule', school: 'School') -> int:
        """体育館制約違反を削除"""
        removed_count = 0
        
        from ...domain.value_objects.time_slot import TimeSlot
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # この時間のPEクラスを収集
                pe_classes = []
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name == "保":
                        pe_classes.append(class_ref)
                
                # 2つ目以降を削除
                if len(pe_classes) > 1:
                    for class_ref in pe_classes[1:]:
                        if not schedule.is_locked(time_slot, class_ref):
                            schedule.remove_assignment(time_slot, class_ref)
                            removed_count += 1
        
        return removed_count
    
    def _log_violations(self, violations: List['ConstraintViolation']) -> None:
        """違反をログ出力"""
        for violation in violations:
            self.logger.warning(f"  - {violation.description}")
    
    def _fill_empty_slots_smartly(self, schedule: 'Schedule', school: 'School') -> None:
        """スマート空きスロット埋め"""
        self.logger.info("=== 空きスロットを埋めています ===")
        
        # Follow-up.csvから教師不在情報を取得
        from ...infrastructure.parsers.natural_followup_parser import NaturalFollowUpParser
        from ...infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
        
        natural_parser = NaturalFollowUpParser(self.path_manager.input_dir)
        natural_result = natural_parser.parse_file("Follow-up.csv")
        
        # 教師不在情報のロード
        absence_loader = TeacherAbsenceLoader()
        if natural_result["parse_success"] and natural_result.get("teacher_absences"):
            absence_loader.update_absences_from_parsed_data(natural_result["teacher_absences"])
        
        # SmartEmptySlotFillerを使用（リファクタリング版）
        from ...domain.services.smart_empty_slot_filler import SmartEmptySlotFiller
        
        # リファクタリングされたFillerを使用
        filler = SmartEmptySlotFiller(self.constraint_system, absence_loader)
        
        # 空きスロットを埋める（最大10パス）
        filled_count = filler.fill_empty_slots_smartly(schedule, school, max_passes=10)
        
        if filled_count > 0:
            self.logger.info(f"合計 {filled_count} 個の空きスロットを埋めました")
            self.generation_stats['empty_slots_filled'] = filled_count
        else:
            self.logger.info("埋められる空きスロットはありませんでした")
    
    def _load_followup_data(self) -> Optional[Dict[str, Any]]:
        """Follow-up.csvからデータを読み込む"""
        try:
            followup_path = self.path_manager.get_input_path('Follow-up.csv')
            
            from ...shared.utils.csv_operations import CSVOperations
            csv_ops = CSVOperations()
            followup_data = {}
            
            # CSVOperationsを使用して読み込み
            rows = csv_ops.read_csv(followup_path)
            for row in rows:
                if '曜日' in row:
                    day = row['曜日'].strip()
                    content = []
                    for key, value in row.items():
                        if key != '曜日' and value and value.strip():
                            content.append(value.strip())
                    if content:
                        followup_data[day] = ' '.join(content)
            
            return followup_data if followup_data else None
            
        except Exception as e:
            self.logger.warning(f"Follow-upデータの読み込みに失敗しました: {e}")
            return None
    
    def _log_statistics(self) -> None:
        """統計情報をログ出力"""
        stats = self.generation_stats
        
        if stats['start_time'] and stats['end_time']:
            duration = (stats['end_time'] - stats['start_time']).total_seconds()
        else:
            duration = 0
        
        self.logger.info("=== 生成統計 ===")
        self.logger.info(f"使用アルゴリズム: {stats['algorithm_used']}")
        self.logger.info(f"実行時間: {duration:.2f}秒")
        self.logger.info(f"反復回数: {stats['iterations']}")
        self.logger.info(f"配置成功: {stats['assignments_made']}")
        self.logger.info(f"配置失敗: {stats['assignments_failed']}")
        self.logger.info(f"違反修正: {stats['violations_fixed']}")
        self.logger.info(f"最終違反: {stats['final_violations']}")
        
        # 空きスロット埋め統計
        if 'empty_slots_filled' in stats:
            self.logger.info(f"空きスロット埋め: {stats['empty_slots_filled']}")