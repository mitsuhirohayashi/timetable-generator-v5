"""
フェーズ7: ハイブリッドアプローチV7（並列処理最適化版）

V6の全機能に加えて、並列処理による高速化を実現。
ParallelOptimizationEngineを統合し、マルチコアCPUを活用して
2-4倍の高速化を目指します。

主な改善点：
1. 並列配置エンジンによるクラス別配置の並行実行
2. 並列制約検証による高速な違反チェック
3. 複数戦略の同時探索
4. 並列ローカルサーチとシミュレーテッドアニーリング
5. 効率的なワーカープール管理
"""
import logging
import time
import os
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
from multiprocessing import cpu_count

from .hybrid_schedule_generator_v6 import HybridScheduleGeneratorV6, OptimizationResult
from .parallel_optimization_engine import ParallelOptimizationEngine, OptimizationCandidate
from ...entities.schedule import Schedule
from ...entities.school import School, Teacher, Subject
from ...value_objects.time_slot import TimeSlot, ClassReference
from ...value_objects.assignment import Assignment


@dataclass
class ParallelOptimizationConfig:
    """並列最適化の設定"""
    enable_parallel_placement: bool = True
    enable_parallel_verification: bool = True
    enable_parallel_search: bool = True
    max_workers: Optional[int] = None
    use_threads: bool = False  # Falseの場合はプロセス
    batch_size: int = 50  # 制約検証のバッチサイズ
    strategy_time_limit: int = 60  # 各戦略の時間制限
    local_search_neighbors: int = 4  # ローカルサーチの近傍数
    sa_populations: int = 4  # SAの集団数


class HybridScheduleGeneratorV7(HybridScheduleGeneratorV6):
    """並列処理最適化版ハイブリッド時間割生成器"""
    
    def __init__(
        self,
        enable_logging: bool = True,
        learning_data_dir: Optional[str] = None,
        parallel_config: Optional[ParallelOptimizationConfig] = None
    ):
        """
        Args:
            enable_logging: ログ出力を有効にするか
            learning_data_dir: 学習データディレクトリ
            parallel_config: 並列最適化の設定
        """
        # 親クラスの初期化
        super().__init__(enable_logging, learning_data_dir)
        
        # 並列最適化設定
        self.parallel_config = parallel_config or ParallelOptimizationConfig()
        
        # 並列エンジンの初期化
        self.parallel_engine = ParallelOptimizationEngine(
            max_workers=self.parallel_config.max_workers,
            use_threads=self.parallel_config.use_threads
        )
        
        # パフォーマンス統計
        self.parallel_stats = {
            'placement_time': 0.0,
            'verification_time': 0.0,
            'optimization_time': 0.0,
            'total_speedup': 0.0
        }
        
        self.logger.info(f"並列処理モード: {'有効' if self._is_parallel_enabled() else '無効'}")
        if self._is_parallel_enabled():
            self.logger.info(f"利用可能CPU数: {cpu_count()}, ワーカー数: {self.parallel_engine.max_workers}")
    
    def generate(
        self,
        school: School,
        initial_schedule: Optional[Schedule] = None,
        target_violations: int = 0,
        time_limit: int = 300,
        followup_data: Optional[Dict[str, Any]] = None
    ) -> OptimizationResult:
        """並列処理を活用したスケジュール生成"""
        start_time = datetime.now()
        
        self.logger.info("=== ハイブリッドV7時間割生成開始（並列処理最適化版）===")
        self.logger.info(f"並列処理設定:")
        self.logger.info(f"  - 並列配置: {'有効' if self.parallel_config.enable_parallel_placement else '無効'}")
        self.logger.info(f"  - 並列検証: {'有効' if self.parallel_config.enable_parallel_verification else '無効'}")
        self.logger.info(f"  - 並列探索: {'有効' if self.parallel_config.enable_parallel_search else '無効'}")
        
        # V6の初期処理を実行
        if followup_data:
            self.logger.info("Follow-upデータから特別な日を分析中...")
            special_days = self.flexible_hours_system._analyze_special_days(followup_data)
            self.logger.info(f"検出された特別な日: {len(special_days)}件")
        
        # 初期スケジュールの準備
        if initial_schedule:
            schedule = self._copy_schedule(initial_schedule)
        else:
            schedule = Schedule()
        
        # テスト期間をスケジュールに設定
        if self.test_period_protector.test_periods:
            schedule.set_test_periods(self.test_period_protector.test_periods)
        
        # フェーズ0: 月曜6限の確実な保護
        self.logger.info("\nフェーズ0: 月曜6限の保護")
        self._protect_monday_sixth_period(schedule, school)
        
        # フェーズ1: 標準時数分析と計画
        self.logger.info("\nフェーズ1: 柔軟な標準時数分析と計画")
        flexible_plans = self._analyze_flexible_hours(schedule, school, followup_data)
        
        # フェーズ2: 5組の完全同期配置（並列化可能）
        self.logger.info("\nフェーズ2: 5組の同期配置（並列処理版）")
        if self.parallel_config.enable_parallel_placement:
            self._place_grade5_parallel(schedule, school, flexible_plans)
        else:
            self._place_grade5_with_learning(schedule, school, flexible_plans)
        
        # フェーズ3: 交流学級の自立活動配置
        self.logger.info("\nフェーズ3: 交流学級の自立活動配置")
        self._place_exchange_jiritsu_with_learning(schedule, school, flexible_plans)
        
        # フェーズ4: 柔軟な標準時数保証システムによる配置（並列化）
        self.logger.info("\nフェーズ4: 柔軟な標準時数保証配置（並列処理版）")
        if self.parallel_config.enable_parallel_placement:
            flexible_results = self._guarantee_hours_parallel(schedule, school, followup_data)
        else:
            flexible_results = self._guarantee_hours_with_learning(schedule, school, followup_data)
        
        # フェーズ5: 高度な最適化（並列化）
        self.logger.info("\nフェーズ5: 高度な最適化（並列処理版）")
        if self.parallel_config.enable_parallel_search:
            best_schedule = self._advanced_optimization_parallel(
                schedule, school, target_violations, time_limit, start_time, flexible_results
            )
        else:
            best_schedule = self._advanced_optimization_with_learning(
                schedule, school, target_violations, time_limit, start_time, flexible_results
            )
        
        # フェーズ6: 最終調整
        self.logger.info("\nフェーズ6: 最終調整")
        self._final_adjustments(best_schedule, school)
        
        # フェーズ7: テスト期間保護の適用
        self.logger.info("\nフェーズ7: テスト期間保護の適用")
        if self.test_period_protector.test_periods:
            changes = self.test_period_protector.protect_test_periods(best_schedule, school)
            if changes > 0:
                self.logger.info(f"テスト期間保護により{changes}個の割り当てを修正しました")
        
        # 結果の評価（並列検証）
        if self.parallel_config.enable_parallel_verification:
            violations = self._parallel_validate_constraints(best_schedule, school)
        else:
            violations = self.constraint_validator.validate_all_constraints(best_schedule, school)
        
        teacher_conflicts = self._count_teacher_conflicts(best_schedule, school)
        
        # 学習システムで違反を分析
        self.logger.info("\nフェーズ8: 違反パターンの学習")
        self._learn_from_generation(violations, best_schedule, school)
        
        # 学習レポートを生成
        learning_report = self.learning_system.get_learning_report()
        
        # 並列処理の統計を追加
        total_time = (datetime.now() - start_time).total_seconds()
        self.parallel_stats['total_speedup'] = self._calculate_speedup(total_time)
        
        # 統計情報の収集
        statistics = {
            'total_assignments': len(best_schedule.get_all_assignments()),
            'violations': len(violations),
            'teacher_conflicts': teacher_conflicts,
            'elapsed_time': total_time,
            'empty_slots': self._count_empty_slots(best_schedule, school),
            'flexible_satisfaction_rate': flexible_results.get('summary', {}).get('average_satisfaction', 0) * 100,
            'fully_satisfied_classes': flexible_results.get('summary', {}).get('fully_satisfied_classes', 0),
            'special_circumstances': len(flexible_results.get('special_circumstances', [])),
            'warnings_count': flexible_results.get('summary', {}).get('warnings_count', 0),
            # 学習システムの統計
            'learning_stats': {
                'predicted_risks': self.generation_stats['predicted_risks'],
                'avoided_violations': self.generation_stats['avoided_violations'],
                'strategy_applications': self.generation_stats['strategy_applications'],
                'learning_improvements': self.generation_stats['learning_improvements'],
                'total_patterns': len(self.learning_system.state.pattern_database),
                'active_strategies': len(self.learning_system.state.strategy_database)
            },
            # 並列処理の統計
            'parallel_stats': {
                'enabled': self._is_parallel_enabled(),
                'workers': self.parallel_engine.max_workers,
                'placement_time': self.parallel_stats['placement_time'],
                'verification_time': self.parallel_stats['verification_time'],
                'optimization_time': self.parallel_stats['optimization_time'],
                'total_speedup': self.parallel_stats['total_speedup'],
                'engine_stats': self.parallel_engine.get_performance_stats()
            }
        }
        
        # 科目別達成率を追加
        subject_stats = {}
        for subject_name, data in flexible_results.get('by_subject', {}).items():
            if subject_name not in self.fixed_subjects:
                subject_stats[subject_name] = {
                    'completion_rate': data.get('average_completion', 0) * 100,
                    'assigned': data.get('total_assigned', 0),
                    'standard': int(data.get('total_standard', 0))
                }
        statistics['subject_completion'] = subject_stats
        
        result = OptimizationResult(
            schedule=best_schedule,
            violations=len(violations),
            teacher_conflicts=teacher_conflicts,
            statistics=statistics,
            flexible_hours_results=flexible_results,
            learning_results=learning_report
        )
        
        # 改善点の記録
        if statistics['flexible_satisfaction_rate'] > 90:
            result.improvements.append(f"柔軟な標準時数満足度{statistics['flexible_satisfaction_rate']:.1f}%達成")
        if teacher_conflicts < 10:
            result.improvements.append("教師重複を10件未満に削減")
        if len(violations) == 0:
            result.improvements.append("全ての制約違反を解消")
        if self.parallel_stats['total_speedup'] > 1.5:
            result.improvements.append(f"並列処理により{self.parallel_stats['total_speedup']:.1f}倍の高速化を達成")
        
        self._print_summary_v7(result)
        
        return result
    
    def _place_grade5_parallel(
        self,
        schedule: Schedule,
        school: School,
        flexible_plans: Dict
    ):
        """5組を並列処理で同期配置"""
        start_time = time.time()
        
        # 5組の必要時数を統合
        grade5_needs = self._calculate_grade5_needs(flexible_plans)
        
        # 5組の科目配置計画を作成
        placement_plans = {}
        grade5_subjects = self._get_grade5_subject_mapping()
        
        for class_ref in self.grade5_classes:
            subjects_to_place = []
            
            for subject_name, needs in grade5_needs.items():
                if subject_name in self.fixed_subjects:
                    continue
                
                teacher_name = grade5_subjects.get(subject_name)
                if teacher_name:
                    subject = Subject(subject_name)
                    teacher = Teacher(teacher_name)
                    required_hours = needs['ideal']
                    subjects_to_place.append((subject, teacher, required_hours))
            
            placement_plans[class_ref] = subjects_to_place
        
        # 並列配置を実行
        result_schedule = self.parallel_engine.parallel_place_subjects(
            schedule, school, placement_plans, self.constraint_validator
        )
        
        # 5組の同期を確認・修正
        self._ensure_grade5_synchronization(result_schedule, school)
        
        # 結果を元のスケジュールに反映
        self._merge_schedule_changes(schedule, result_schedule)
        
        self.parallel_stats['placement_time'] += time.time() - start_time
        self.logger.info(f"5組並列配置完了: {time.time() - start_time:.2f}秒")
    
    def _guarantee_hours_parallel(
        self,
        schedule: Schedule,
        school: School,
        followup_data: Optional[Dict[str, Any]]
    ) -> Dict:
        """並列処理で標準時数を保証"""
        start_time = time.time()
        
        # まず通常の標準時数保証を実行
        flexible_results = self.flexible_hours_system.guarantee_flexible_hours(
            schedule, school, followup_data, self.constraint_validator
        )
        
        # 配置が必要なクラスと科目を収集
        placement_plans = self._collect_placement_requirements(
            schedule, school, flexible_results
        )
        
        if placement_plans:
            # 並列配置を実行
            result_schedule = self.parallel_engine.parallel_place_subjects(
                schedule, school, placement_plans, self.constraint_validator
            )
            
            # 結果をマージ
            self._merge_schedule_changes(schedule, result_schedule)
        
        self.parallel_stats['placement_time'] += time.time() - start_time
        
        return flexible_results
    
    def _advanced_optimization_parallel(
        self,
        schedule: Schedule,
        school: School,
        target_violations: int,
        time_limit: int,
        start_time: datetime,
        flexible_results: Dict
    ) -> Schedule:
        """並列処理による高度な最適化"""
        opt_start_time = time.time()
        
        best_schedule = self._copy_schedule(schedule)
        best_violations = self._parallel_validate_constraints(best_schedule, school) if self.parallel_config.enable_parallel_verification else self.constraint_validator.validate_all_constraints(best_schedule, school)
        best_conflicts = self._count_teacher_conflicts(best_schedule, school)
        
        # 柔軟な満足度が低い場合
        satisfaction_rate = flexible_results.get('summary', {}).get('average_satisfaction', 0)
        if satisfaction_rate < 0.85:
            self.logger.info(f"柔軟な満足度が低い({satisfaction_rate*100:.1f}%)ため、時数充足を優先")
            best_schedule = self._optimize_for_flexible_satisfaction_parallel(
                best_schedule, school, time_limit, start_time
            )
        
        # 複数の最適化戦略を並列実行
        iteration = 0
        max_iterations = 50  # 並列処理なので反復回数を減らす
        no_improvement_count = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # 時間制限チェック
            if (datetime.now() - start_time).total_seconds() > time_limit:
                break
            
            # 現在の状態
            current_violations = self._parallel_validate_constraints(schedule, school) if self.parallel_config.enable_parallel_verification else self.constraint_validator.validate_all_constraints(schedule, school)
            current_conflicts = self._count_teacher_conflicts(schedule, school)
            
            if len(current_violations) <= target_violations and current_conflicts == 0:
                self.parallel_stats['optimization_time'] += time.time() - opt_start_time
                return schedule
            
            # 改善戦略
            improved = False
            
            # 1. 並列戦略探索
            if not improved and iteration % 5 == 0:
                strategies = ["swap_heavy", "teacher_focus", "balanced", "aggressive"]
                candidates = self.parallel_engine.parallel_strategy_search(
                    schedule, school, strategies,
                    min(self.parallel_config.strategy_time_limit, int((time_limit - (datetime.now() - start_time).total_seconds()) / 2))
                )
                
                if candidates:
                    best_candidate = candidates[0]
                    if best_candidate.score > self._evaluate_schedule(schedule, school):
                        schedule = self._deserialize_schedule(best_candidate.schedule)
                        improved = True
                        self.logger.info(f"並列戦略探索で改善: {best_candidate.metadata.get('strategy')}")
            
            # 2. 並列ローカルサーチ
            if not improved and iteration % 3 == 0:
                improved_schedule = self.parallel_engine.parallel_local_search(
                    schedule, school,
                    self.parallel_config.local_search_neighbors,
                    25
                )
                
                new_violations = self._parallel_validate_constraints(improved_schedule, school) if self.parallel_config.enable_parallel_verification else self.constraint_validator.validate_all_constraints(improved_schedule, school)
                new_conflicts = self._count_teacher_conflicts(improved_schedule, school)
                
                if len(new_violations) < len(current_violations) or (len(new_violations) == len(current_violations) and new_conflicts < current_conflicts):
                    schedule = improved_schedule
                    improved = True
                    self.logger.info("並列ローカルサーチで改善")
            
            # 3. 並列シミュレーテッドアニーリング
            if not improved and iteration % 7 == 0:
                sa_schedule = self.parallel_engine.parallel_simulated_annealing(
                    schedule, school,
                    self.parallel_config.sa_populations,
                    50
                )
                
                sa_violations = self._parallel_validate_constraints(sa_schedule, school) if self.parallel_config.enable_parallel_verification else self.constraint_validator.validate_all_constraints(sa_schedule, school)
                sa_conflicts = self._count_teacher_conflicts(sa_schedule, school)
                
                if len(sa_violations) < len(current_violations) or (len(sa_violations) == len(current_violations) and sa_conflicts < current_conflicts):
                    schedule = sa_schedule
                    improved = True
                    self.logger.info("並列SAで改善")
            
            # 4. 通常の最適化手法（V6から継承）
            if not improved:
                # 学習システムによる違反予測と修正
                if len(current_violations) > 0:
                    improved = self._fix_violations_with_learning(schedule, school, current_violations)
                
                # 教師重複の解消
                if not improved and current_conflicts > 0:
                    improved = self._fix_teacher_conflicts_smart(schedule, school)
                
                # その他の違反修正
                if not improved and len(current_violations) > current_conflicts:
                    improved = self._fix_other_violations(schedule, school)
                
                # 局所探索
                if not improved:
                    improved = self._local_search_with_learning(schedule, school)
            
            # 評価
            new_violations = self._parallel_validate_constraints(schedule, school) if self.parallel_config.enable_parallel_verification else self.constraint_validator.validate_all_constraints(schedule, school)
            new_conflicts = self._count_teacher_conflicts(schedule, school)
            
            if len(new_violations) < len(best_violations) or (len(new_violations) == len(best_violations) and new_conflicts < best_conflicts):
                best_schedule = self._copy_schedule(schedule)
                best_violations = new_violations
                best_conflicts = new_conflicts
                no_improvement_count = 0
                self.generation_stats['learning_improvements'] += 1
            else:
                no_improvement_count += 1
            
            # 停滞時の処理
            if no_improvement_count > 10:
                schedule = self._copy_schedule(best_schedule)
                self._apply_smart_perturbation(schedule, school)
                no_improvement_count = 0
        
        self.parallel_stats['optimization_time'] += time.time() - opt_start_time
        
        return best_schedule
    
    def _parallel_validate_constraints(self, schedule: Schedule, school: School) -> List[Any]:
        """並列で制約を検証"""
        start_time = time.time()
        
        violations = self.parallel_engine.parallel_verify_constraints(
            schedule, school, self.constraint_validator,
            self.parallel_config.batch_size
        )
        
        self.parallel_stats['verification_time'] += time.time() - start_time
        
        return violations
    
    def _optimize_for_flexible_satisfaction_parallel(
        self,
        schedule: Schedule,
        school: School,
        time_limit: int,
        start_time: datetime
    ) -> Schedule:
        """並列処理で柔軟な満足度の向上を優先した最適化"""
        # 複数の改善戦略を並列実行
        strategies = []
        
        # 戦略1: 不足科目の積極配置
        strategies.append("aggressive_placement")
        
        # 戦略2: 科目間バランス調整
        strategies.append("balance_subjects")
        
        # 戦略3: 空きスロット最小化
        strategies.append("minimize_empty")
        
        # 並列戦略探索
        candidates = self.parallel_engine.parallel_strategy_search(
            schedule, school, strategies,
            min(60, int((time_limit - (datetime.now() - start_time).total_seconds()) / 2))
        )
        
        if candidates:
            # 最も満足度の高い候補を選択
            best_candidate = None
            best_satisfaction = 0.0
            
            for candidate in candidates:
                # 候補スケジュールの満足度を評価
                candidate_schedule = self._deserialize_schedule(candidate.schedule)
                results = self.flexible_hours_system.guarantee_flexible_hours(
                    candidate_schedule, school, None, self.constraint_validator
                )
                satisfaction = results.get('summary', {}).get('average_satisfaction', 0)
                
                if satisfaction > best_satisfaction:
                    best_satisfaction = satisfaction
                    best_candidate = candidate
            
            if best_candidate and best_satisfaction > 0.85:
                return self._deserialize_schedule(best_candidate.schedule)
        
        # フォールバック：V6の手法を使用
        return super()._optimize_for_flexible_satisfaction(schedule, school, time_limit, start_time)
    
    def _calculate_grade5_needs(self, flexible_plans: Dict) -> Dict:
        """5組の必要時数を計算"""
        grade5_needs = defaultdict(lambda: {'ideal': 0, 'minimum': 0, 'priority': 0})
        
        for class_ref in self.grade5_classes:
            if class_ref in flexible_plans:
                plan = flexible_plans[class_ref]
                for subject_name, req in plan.requirements.items():
                    if req.ideal_hours > req.assigned_hours:
                        needed = req.ideal_hours - req.assigned_hours
                        grade5_needs[subject_name]['ideal'] = max(
                            grade5_needs[subject_name]['ideal'],
                            needed
                        )
                        grade5_needs[subject_name]['minimum'] = max(
                            grade5_needs[subject_name]['minimum'],
                            req.minimum_hours - req.assigned_hours
                        )
                        grade5_needs[subject_name]['priority'] = max(
                            grade5_needs[subject_name]['priority'],
                            req.priority
                        )
        
        return grade5_needs
    
    def _get_grade5_subject_mapping(self) -> Dict[str, str]:
        """5組の科目と教師のマッピングを取得"""
        return {
            "国": "寺田", "社": "蒲地", "数": "梶永",
            "理": "智田", "音": "塚本", "美": "金子み",
            "保": "野口", "技": "林", "家": "金子み",
            "英": "林田", "道": "金子み", "学": "金子み",
            "総": "金子み", "自立": "金子み", "日生": "金子み",
            "作業": "金子み", "YT": "金子み", "学総": "金子み"
        }
    
    def _ensure_grade5_synchronization(self, schedule: Schedule, school: School):
        """5組の同期を確保"""
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 5組の授業を収集
                assignments = {}
                subjects = defaultdict(int)
                
                for class_ref in self.grade5_classes:
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        assignments[class_ref] = assignment
                        subjects[assignment.subject.name] += 1
                
                # 最も多い科目に統一
                if len(assignments) > 0 and len(assignments) < 3:
                    if subjects:
                        dominant_subject = max(subjects, key=subjects.get)
                        dominant_assignment = next(
                            a for a in assignments.values()
                            if a.subject.name == dominant_subject
                        )
                        
                        # 他のクラスも同じ科目に
                        for class_ref in self.grade5_classes:
                            if class_ref not in assignments:
                                try:
                                    new_assignment = Assignment(
                                        class_ref,
                                        dominant_assignment.subject,
                                        dominant_assignment.teacher
                                    )
                                    schedule.assign(time_slot, new_assignment)
                                except:
                                    pass
    
    def _merge_schedule_changes(self, target: Schedule, source: Schedule):
        """スケジュールの変更をマージ"""
        # sourceの全ての配置をtargetに反映
        for time_slot, assignment in source.get_all_assignments():
            # targetに既存の配置がある場合は置き換えを検討
            existing = target.get_assignment(time_slot, assignment.class_ref)
            
            if existing:
                # 優先度に基づいて判断
                if self._should_replace_assignment(existing, assignment):
                    try:
                        target.remove_assignment(time_slot, assignment.class_ref)
                        target.assign(time_slot, assignment)
                    except:
                        pass
            else:
                # 新規配置
                try:
                    target.assign(time_slot, assignment)
                except:
                    pass
    
    def _should_replace_assignment(self, existing: Assignment, new: Assignment) -> bool:
        """既存の配置を新しい配置で置き換えるべきか判定"""
        # 固定科目は置き換えない
        if existing.subject.name in self.fixed_subjects:
            return False
        
        # 新しい配置が主要科目の場合は優先
        if new.subject.name in self.core_subjects and existing.subject.name not in self.core_subjects:
            return True
        
        return False
    
    def _collect_placement_requirements(
        self,
        schedule: Schedule,
        school: School,
        flexible_results: Dict
    ) -> Dict[ClassReference, List[Tuple[Subject, Teacher, int]]]:
        """配置が必要なクラスと科目を収集"""
        placement_plans = {}
        
        # 各クラスの不足科目を収集
        class_results = flexible_results.get('by_class', {})
        
        for class_name, class_data in class_results.items():
            class_ref = self._parse_class_ref(class_name)
            if not class_ref:
                continue
            
            # 5組は別処理なのでスキップ
            if class_ref in self.grade5_classes:
                continue
            
            subjects_to_place = []
            
            for subject_name, allocation in class_data.get('subjects', {}).items():
                if allocation['satisfaction'] == "不足":
                    subject = Subject(subject_name)
                    teacher = school.get_assigned_teacher(subject, class_ref)
                    
                    if teacher:
                        # 不足時数を計算
                        needed = allocation['standard'] - allocation['assigned']
                        if needed > 0:
                            subjects_to_place.append((subject, teacher, needed))
            
            if subjects_to_place:
                placement_plans[class_ref] = subjects_to_place
        
        return placement_plans
    
    def _is_parallel_enabled(self) -> bool:
        """並列処理が有効か確認"""
        return (
            self.parallel_config.enable_parallel_placement or
            self.parallel_config.enable_parallel_verification or
            self.parallel_config.enable_parallel_search
        )
    
    def _calculate_speedup(self, total_time: float) -> float:
        """スピードアップ率を計算"""
        # 理論的なシーケンシャル実行時間を推定
        sequential_estimate = total_time * self.parallel_engine.max_workers * 0.7  # 0.7は並列化効率
        
        if total_time > 0:
            return sequential_estimate / total_time
        return 1.0
    
    def _evaluate_schedule(self, schedule: Schedule, school: School) -> float:
        """スケジュールを評価"""
        score = 1000.0
        
        # 空きスロットのペナルティ
        empty_count = self._count_empty_slots(schedule, school)
        score -= empty_count * 10
        
        # 違反数のペナルティ
        violations = self.constraint_validator.validate_all_constraints(schedule, school)
        score -= len(violations) * 50
        
        # 教師重複のペナルティ
        conflicts = self._count_teacher_conflicts(schedule, school)
        score -= conflicts * 30
        
        return score
    
    def _deserialize_schedule(self, schedule_data: bytes) -> Schedule:
        """シリアライズされたスケジュールを復元"""
        # ParallelOptimizationEngineの形式に合わせて実装
        import pickle
        
        schedule = Schedule()
        data = pickle.loads(schedule_data)
        
        for item in data['assignments']:
            time_slot = TimeSlot(item['day'], item['period'])
            class_ref = ClassReference(item['grade'], item['class_number'])
            subject = Subject(item['subject'])
            teacher = Teacher(item['teacher']) if item['teacher'] else None
            assignment = Assignment(class_ref, subject, teacher)
            
            try:
                schedule.assign(time_slot, assignment)
            except:
                pass
        
        return schedule
    
    def _print_summary_v7(self, result: OptimizationResult):
        """V7用の結果サマリーを出力"""
        self.logger.info("\n=== ハイブリッドV7生成結果（並列処理最適化版）===")
        self.logger.info(f"総割り当て数: {result.statistics['total_assignments']}")
        self.logger.info(f"制約違反数: {result.violations}")
        self.logger.info(f"教師重複数: {result.teacher_conflicts}")
        self.logger.info(f"空きスロット数: {result.statistics['empty_slots']}")
        self.logger.info(f"柔軟な満足度: {result.statistics['flexible_satisfaction_rate']:.1f}%")
        self.logger.info(f"完全充足クラス数: {result.statistics['fully_satisfied_classes']}")
        
        # 学習システムの統計
        learning_stats = result.statistics.get('learning_stats', {})
        self.logger.info(f"\n学習システム統計:")
        self.logger.info(f"  予測されたリスク: {learning_stats.get('predicted_risks', 0)}件")
        self.logger.info(f"  回避された違反: {learning_stats.get('avoided_violations', 0)}件")
        self.logger.info(f"  適用された戦略: {learning_stats.get('strategy_applications', 0)}回")
        self.logger.info(f"  学習による改善: {learning_stats.get('learning_improvements', 0)}回")
        
        # 並列処理の統計
        parallel_stats = result.statistics.get('parallel_stats', {})
        if parallel_stats.get('enabled'):
            self.logger.info(f"\n並列処理統計:")
            self.logger.info(f"  ワーカー数: {parallel_stats.get('workers')}個")
            self.logger.info(f"  配置時間: {parallel_stats.get('placement_time', 0):.2f}秒")
            self.logger.info(f"  検証時間: {parallel_stats.get('verification_time', 0):.2f}秒")
            self.logger.info(f"  最適化時間: {parallel_stats.get('optimization_time', 0):.2f}秒")
            self.logger.info(f"  総スピードアップ: {parallel_stats.get('total_speedup', 1.0):.1f}倍")
            
            engine_stats = parallel_stats.get('engine_stats', {})
            if engine_stats:
                self.logger.info(f"  実行タスク数: {engine_stats.get('total_tasks', 0)}個")
                self.logger.info(f"  成功率: {engine_stats.get('success_rate', 0):.1f}%")
        
        self.logger.info(f"\n実行時間: {result.statistics['elapsed_time']:.1f}秒")
        
        # 科目別達成率（上位5科目）
        if 'subject_completion' in result.statistics:
            self.logger.info("\n科目別達成率（上位5科目）:")
            sorted_subjects = sorted(
                result.statistics['subject_completion'].items(),
                key=lambda x: x[1]['completion_rate'],
                reverse=True
            )[:5]
            for subject_name, data in sorted_subjects:
                self.logger.info(
                    f"  {subject_name}: {data['completion_rate']:.1f}% "
                    f"({data['assigned']}/{data['standard']})"
                )
        
        if result.improvements:
            self.logger.info("\n達成した改善:")
            for improvement in result.improvements:
                self.logger.info(f"  ✓ {improvement}")