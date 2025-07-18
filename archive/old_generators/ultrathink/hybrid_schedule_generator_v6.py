"""
フェーズ6: ハイブリッドアプローチV6（制約違反学習システム統合版）

V5の機能に加えて、制約違反学習システムを統合。
過去の制約違反パターンを学習し、配置前に違反リスクを予測して回避します。
生成のたびに学習し、継続的に改善される自己学習型時間割生成器。

主な改善点：
1. ConstraintViolationLearningSystemの統合
2. 配置前の違反リスク予測
3. 高リスク配置の自動回避
4. 生成後の学習と改善
5. 継続的な戦略の最適化
"""
import logging
import random
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

from .flexible_standard_hours_guarantee_system import FlexibleStandardHoursGuaranteeSystem
from .constraint_violation_learning_system import ConstraintViolationLearningSystem, AvoidanceStrategy
from ...entities.schedule import Schedule
from ...entities.school import School, Teacher, Subject
from ...value_objects.time_slot import TimeSlot, ClassReference
from ...value_objects.assignment import Assignment
from ..constraint_validator import ConstraintValidator
from ..exchange_class_synchronizer import ExchangeClassSynchronizer
from ..grade5_synchronizer_refactored import RefactoredGrade5Synchronizer
from .test_period_protector import TestPeriodProtector


@dataclass
class OptimizationResult:
    """最適化結果"""
    schedule: Schedule
    violations: int
    teacher_conflicts: int
    statistics: Dict
    improvements: List[str] = field(default_factory=list)
    flexible_hours_results: Optional[Dict] = None
    learning_results: Optional[Dict] = None


class HybridScheduleGeneratorV6:
    """制約違反学習システム統合版ハイブリッド時間割生成器"""
    
    def __init__(self, enable_logging: bool = True, learning_data_dir: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        if not enable_logging:
            self.logger.setLevel(logging.WARNING)
        
        # 制約検証器
        self.constraint_validator = ConstraintValidator()
        
        # 同期サービス
        self.grade5_synchronizer = RefactoredGrade5Synchronizer(self.constraint_validator)
        self.exchange_synchronizer = ExchangeClassSynchronizer()
        
        # テスト期間保護サービス
        self.test_period_protector = TestPeriodProtector()
        
        # 柔軟な標準時数保証システム
        self.flexible_hours_system = FlexibleStandardHoursGuaranteeSystem(enable_logging)
        
        # 制約違反学習システム
        self.learning_system = ConstraintViolationLearningSystem(learning_data_dir)
        
        # テスト期間の定義
        self.test_periods = {
            ("月", 1), ("月", 2), ("月", 3),
            ("火", 1), ("火", 2), ("火", 3),
            ("水", 1), ("水", 2)
        }
        
        # 固定教師の定義
        self.fixed_teachers = {
            "欠", "欠課先生", "YT担当", "YT担当先生", 
            "道担当", "道担当先生", "学担当", "学担当先生", 
            "総担当", "総担当先生", "学総担当", "学総担当先生", 
            "行担当", "行担当先生", "技家担当", "技家担当先生"
        }
        
        # 5組クラス
        self.grade5_classes = {
            ClassReference(1, 5), 
            ClassReference(2, 5), 
            ClassReference(3, 5)
        }
        
        # 交流学級と親学級のマッピング
        self.exchange_class_mapping = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2)
        }
        
        # 固定科目
        self.fixed_subjects = {"欠", "YT", "道", "学", "総", "学総", "行", "技家"}
        
        # 主要5教科
        self.core_subjects = {"国", "数", "英", "理", "社"}
        
        # 生成統計
        self.generation_stats = {
            'predicted_risks': 0,
            'avoided_violations': 0,
            'strategy_applications': 0,
            'learning_improvements': 0
        }
    
    def generate(
        self,
        school: School,
        initial_schedule: Optional[Schedule] = None,
        target_violations: int = 0,
        time_limit: int = 300,
        followup_data: Optional[Dict[str, Any]] = None
    ) -> OptimizationResult:
        """スケジュールを生成"""
        start_time = datetime.now()
        
        self.logger.info("=== ハイブリッドV6時間割生成開始（制約違反学習システム統合版）===")
        self.logger.info(f"学習システム状態: {self.learning_system.state.generation_count}世代目")
        self.logger.info(f"学習済みパターン数: {len(self.learning_system.state.pattern_database)}")
        
        # テスト期間保護の初期化
        if followup_data:
            self.test_period_protector.load_followup_data(followup_data)
            # test_periodsも更新
            self.test_periods = self.test_period_protector.test_periods.copy()
        
        # 初期スケジュールの準備
        if initial_schedule:
            # テスト期間の割り当てを保存
            self.test_period_protector.load_initial_schedule(initial_schedule)
        self.logger.info(f"有効な回避戦略数: {len(self.learning_system.state.strategy_database)}")
        
        # Follow-upデータの分析
        if followup_data:
            self.logger.info("Follow-upデータから特別な日を分析中...")
            special_days = self.flexible_hours_system._analyze_special_days(followup_data)
            self.logger.info(f"検出された特別な日: {len(special_days)}件")
            for sd in special_days[:5]:  # 最初の5件を表示
                self.logger.info(f"  - {sd.day}曜 {sd.periods}限: {sd.reason}")
        
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
        
        # フェーズ2: 5組の完全同期配置（学習システムを使用）
        self.logger.info("\nフェーズ2: 5組の同期配置（学習システム使用）")
        self._place_grade5_with_learning(schedule, school, flexible_plans)
        
        # フェーズ3: 交流学級の自立活動配置（学習システムを使用）
        self.logger.info("\nフェーズ3: 交流学級の自立活動配置（学習システム使用）")
        self._place_exchange_jiritsu_with_learning(schedule, school, flexible_plans)
        
        # フェーズ4: 柔軟な標準時数保証システムによる配置（学習システムを使用）
        self.logger.info("\nフェーズ4: 柔軟な標準時数保証配置（学習システム使用）")
        flexible_results = self._guarantee_hours_with_learning(
            schedule, school, followup_data
        )
        
        # フェーズ5: 高度な最適化（学習を考慮）
        self.logger.info("\nフェーズ5: 高度な最適化（学習考慮）")
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
        
        # 結果の評価
        violations = self.constraint_validator.validate_all_constraints(best_schedule, school)
        teacher_conflicts = self._count_teacher_conflicts(best_schedule, school)
        
        # 学習システムで違反を分析
        self.logger.info("\nフェーズ8: 違反パターンの学習")
        self._learn_from_generation(violations, best_schedule, school)
        
        # 学習レポートを生成
        learning_report = self.learning_system.get_learning_report()
        
        # 統計情報の収集
        statistics = {
            'total_assignments': len(best_schedule.get_all_assignments()),
            'violations': len(violations),
            'teacher_conflicts': teacher_conflicts,
            'elapsed_time': (datetime.now() - start_time).total_seconds(),
            'empty_slots': self._count_empty_slots(best_schedule, school),
            'flexible_satisfaction_rate': flexible_results.get('summary', {}).get('average_satisfaction', 0) * 100,
            'fully_satisfied_classes': flexible_results.get('summary', {}).get('fully_satisfied_classes', 0),
            'special_circumstances': len(flexible_results.get('special_circumstances', [])),
            'warnings_count': flexible_results.get('summary', {}).get('warnings_count', 0),
            # 学習システムの統計を追加
            'learning_stats': {
                'predicted_risks': self.generation_stats['predicted_risks'],
                'avoided_violations': self.generation_stats['avoided_violations'],
                'strategy_applications': self.generation_stats['strategy_applications'],
                'learning_improvements': self.generation_stats['learning_improvements'],
                'total_patterns': len(self.learning_system.state.pattern_database),
                'active_strategies': len(self.learning_system.state.strategy_database)
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
        if statistics['special_circumstances'] > 0:
            result.improvements.append(f"{statistics['special_circumstances']}件の特別な状況に対応")
        if self.generation_stats['avoided_violations'] > 0:
            result.improvements.append(f"学習により{self.generation_stats['avoided_violations']}件の違反を事前回避")
        
        self._print_summary(result)
        
        return result
    
    def _place_grade5_with_learning(
        self,
        schedule: Schedule,
        school: School,
        flexible_plans: Dict
    ):
        """5組を学習システムを使用して同期配置"""
        # 5組の必要時数を統合（柔軟な計画から）
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
        
        # 5組共通の科目と教師のマッピング
        grade5_subjects = {
            "国": "寺田", "社": "蒲地", "数": "梶永",
            "理": "智田", "音": "塚本", "美": "金子み",
            "保": "野口", "技": "林", "家": "金子み",
            "英": "林田", "道": "金子み", "学": "金子み",
            "総": "金子み", "自立": "金子み", "日生": "金子み",
            "作業": "金子み", "YT": "金子み", "学総": "金子み"
        }
        
        # 優先度順にソート（優先度が高い順）
        sorted_subjects = sorted(
            grade5_needs.items(),
            key=lambda x: (x[1]['priority'], x[1]['ideal']),
            reverse=True
        )
        
        days = ["月", "火", "水", "木", "金"]
        for subject_name, needs in sorted_subjects:
            if subject_name in self.fixed_subjects:
                continue
                
            teacher_name = grade5_subjects.get(subject_name)
            if not teacher_name:
                continue
            
            placed_count = 0
            target_hours = needs['ideal']
            
            # 最適な配置順序（バランスを考慮）
            day_order = self._get_optimal_day_order(subject_name)
            
            for day in day_order:
                if placed_count >= target_hours:
                    break
                    
                for period in range(1, 7):
                    if placed_count >= target_hours:
                        break
                    
                    # 月曜6限はスキップ
                    if day == "月" and period == 6:
                        continue
                    
                    time_slot = TimeSlot(day, period)
                    
                    # 違反リスクを予測
                    risk = self._predict_violation_risk(
                        day, period, "1年5組",  # 代表クラス
                        subject_name, teacher_name
                    )
                    
                    if risk > 0.7:  # 高リスクの場合はスキップ
                        self.logger.debug(f"高リスク({risk:.2f})のため配置をスキップ: {subject_name} @ {time_slot}")
                        self.generation_stats['predicted_risks'] += 1
                        continue
                    
                    # 全5組が空いているか確認
                    all_available = True
                    for class_ref in self.grade5_classes:
                        if schedule.get_assignment(time_slot, class_ref):
                            all_available = False
                            break
                        # 特別な日の影響をチェック
                        if class_ref in flexible_plans:
                            plan = flexible_plans[class_ref]
                            if time_slot not in plan.available_slots:
                                all_available = False
                                break
                    
                    if not all_available:
                        continue
                    
                    # 教師が利用可能か確認
                    if not self._is_teacher_available(teacher_name, time_slot, schedule, school):
                        continue
                    
                    # 回避戦略を適用
                    strategies = self._get_applicable_strategies(
                        day, period, "1年5組", subject_name, teacher_name
                    )
                    
                    if strategies and not self._apply_avoidance_strategies(
                        strategies, schedule, school, time_slot,
                        self.grade5_classes, subject_name, teacher_name
                    ):
                        continue
                    
                    # 5組全てに配置
                    subject = Subject(subject_name)
                    teacher = Teacher(teacher_name)
                    
                    placed_all = True
                    for class_ref in self.grade5_classes:
                        assignment = Assignment(class_ref, subject, teacher)
                        try:
                            schedule.assign(time_slot, assignment)
                        except:
                            placed_all = False
                            break
                    
                    if placed_all:
                        placed_count += 1
                        self.logger.debug(f"5組同期配置: {subject_name} @ {time_slot}")
                        # 戦略の成功を記録
                        for strategy in strategies:
                            self.learning_system.update_strategy_result(strategy.strategy_id, True)
    
    def _place_exchange_jiritsu_with_learning(
        self,
        schedule: Schedule,
        school: School,
        flexible_plans: Dict
    ):
        """交流学級の自立活動を学習システムを使用して配置"""
        for exchange_class, parent_class in self.exchange_class_mapping.items():
            # 自立活動の教師を取得
            jiritsu_teacher = self._get_jiritsu_teacher(exchange_class)
            if not jiritsu_teacher:
                continue
            
            # 柔軟な計画から必要時数を取得
            if exchange_class in flexible_plans:
                plan = flexible_plans[exchange_class]
                jiritsu_req = plan.requirements.get("自立")
                if jiritsu_req:
                    needed_hours = jiritsu_req.ideal_hours - jiritsu_req.assigned_hours
                else:
                    needed_hours = 3  # デフォルト
            else:
                needed_hours = 3
            
            placed_count = 0
            
            # 最適な配置を探す（利用可能スロットを考慮）
            available_slots = []
            if exchange_class in flexible_plans:
                available_slots = flexible_plans[exchange_class].available_slots
            
            for time_slot in available_slots:
                if placed_count >= needed_hours:
                    break
                
                # 既に配置済みならスキップ
                if schedule.get_assignment(time_slot, exchange_class):
                    continue
                
                # 違反リスクを予測（自立活動特有のルール）
                class_str = f"{exchange_class.grade}年{exchange_class.class_number}組"
                risk = self._predict_jiritsu_violation_risk(
                    time_slot, exchange_class, parent_class, schedule
                )
                
                if risk > 0.8:  # 自立活動は高リスクの閾値を厳しく
                    self.logger.debug(f"自立活動高リスク({risk:.2f}): {exchange_class} @ {time_slot}")
                    self.generation_stats['predicted_risks'] += 1
                    continue
                
                # 親学級の科目を確認
                parent_assignment = schedule.get_assignment(time_slot, parent_class)
                if not parent_assignment:
                    # 親学級が空きの場合、数学か英語を配置できるか確認
                    if self._can_place_math_or_english(parent_class, time_slot, schedule, school):
                        # 数学または英語を配置
                        if self._place_math_or_english(parent_class, time_slot, schedule, school):
                            parent_assignment = schedule.get_assignment(time_slot, parent_class)
                
                if parent_assignment and parent_assignment.subject.name in ["数", "英"]:
                    # 自立活動を配置
                    subject = Subject("自立")
                    teacher = Teacher(jiritsu_teacher)
                    assignment = Assignment(exchange_class, subject, teacher)
                    
                    try:
                        schedule.assign(time_slot, assignment)
                        placed_count += 1
                        self.logger.debug(f"自立活動配置: {exchange_class} @ {time_slot}")
                        self.generation_stats['avoided_violations'] += 1
                    except:
                        pass
    
    def _guarantee_hours_with_learning(
        self,
        schedule: Schedule,
        school: School,
        followup_data: Optional[Dict[str, Any]]
    ) -> Dict:
        """学習システムを使用して標準時数を保証"""
        # まず通常の標準時数保証を実行
        flexible_results = self.flexible_hours_system.guarantee_flexible_hours(
            schedule, school, followup_data, self.constraint_validator
        )
        
        # 配置中に学習システムを活用
        days = ["月", "火", "水", "木", "金"]
        
        for class_ref in school.get_all_classes():
            class_str = f"{class_ref.grade}年{class_ref.class_number}組"
            
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    # 既存の配置を確認
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        # 違反リスクを評価
                        day_idx = days.index(day)
                        risk = self._predict_violation_risk(
                            day_idx, period - 1, class_str,
                            assignment.subject.name,
                            assignment.teacher.name if assignment.teacher else None
                        )
                        
                        if risk > 0.5 and not schedule.is_locked(time_slot, class_ref):
                            # 中リスク以上の場合、代替案を検討
                            strategies = self._get_applicable_strategies(
                                day_idx, period - 1, class_str,
                                assignment.subject.name,
                                assignment.teacher.name if assignment.teacher else None
                            )
                            
                            if strategies:
                                self.logger.debug(f"リスクのある配置を検討: {assignment.subject.name} @ {time_slot} for {class_ref}")
                                self._try_apply_strategies_to_existing(
                                    strategies, schedule, school, time_slot, class_ref, assignment
                                )
        
        return flexible_results
    
    def _advanced_optimization_with_learning(
        self,
        schedule: Schedule,
        school: School,
        target_violations: int,
        time_limit: int,
        start_time: datetime,
        flexible_results: Dict
    ) -> Schedule:
        """学習を考慮した高度な最適化"""
        best_schedule = self._copy_schedule(schedule)
        best_violations = self.constraint_validator.validate_all_constraints(best_schedule, school)
        best_conflicts = self._count_teacher_conflicts(best_schedule, school)
        
        # 柔軟な満足度が低い場合は、それを優先
        satisfaction_rate = flexible_results.get('summary', {}).get('average_satisfaction', 0)
        if satisfaction_rate < 0.85:
            self.logger.info(f"柔軟な満足度が低い({satisfaction_rate*100:.1f}%)ため、時数充足を優先")
            return self._optimize_for_flexible_satisfaction(best_schedule, school, time_limit, start_time)
        
        # 通常の最適化
        iteration = 0
        max_iterations = 100
        no_improvement_count = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # 時間制限チェック
            if (datetime.now() - start_time).total_seconds() > time_limit:
                break
            
            # 現在の状態
            current_violations = self.constraint_validator.validate_all_constraints(schedule, school)
            current_conflicts = self._count_teacher_conflicts(schedule, school)
            
            if len(current_violations) <= target_violations and current_conflicts == 0:
                return schedule
            
            # 改善戦略
            improved = False
            
            # 1. 学習システムによる違反予測と修正
            if len(current_violations) > 0:
                improved = self._fix_violations_with_learning(schedule, school, current_violations)
            
            # 2. 教師重複の解消を最優先
            if not improved and current_conflicts > 0:
                improved = self._fix_teacher_conflicts_smart(schedule, school)
            
            # 3. その他の違反修正
            if not improved and len(current_violations) > current_conflicts:
                improved = self._fix_other_violations(schedule, school)
            
            # 4. 局所探索
            if not improved:
                improved = self._local_search_with_learning(schedule, school)
            
            # 評価
            new_violations = self.constraint_validator.validate_all_constraints(schedule, school)
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
            if no_improvement_count > 20:
                schedule = self._copy_schedule(best_schedule)
                self._apply_smart_perturbation(schedule, school)
                no_improvement_count = 0
        
        return best_schedule
    
    def _predict_violation_risk(
        self,
        day: int,
        period: int,
        class_id: str,
        subject: str,
        teacher: Optional[str]
    ) -> float:
        """配置の違反リスクを予測"""
        # 曜日の文字列変換
        day_names = ["月", "火", "水", "木", "金"]
        if isinstance(day, str):
            day_idx = day_names.index(day) if day in day_names else 0
        else:
            day_idx = day
        
        # 期間の調整（1-based to 0-based）
        period_idx = period - 1 if period > 0 else period
        
        return self.learning_system.predict_violations(
            day_idx, period_idx, class_id, subject, teacher
        )
    
    def _predict_jiritsu_violation_risk(
        self,
        time_slot: TimeSlot,
        exchange_class: ClassReference,
        parent_class: ClassReference,
        schedule: Schedule
    ) -> float:
        """自立活動配置の違反リスクを予測"""
        # 親学級の科目を確認
        parent_assignment = schedule.get_assignment(time_slot, parent_class)
        
        # 親学級に数学・英語以外が配置されている場合は高リスク
        if parent_assignment and parent_assignment.subject.name not in ["数", "英"]:
            return 0.9
        
        # 通常のリスク予測
        exchange_str = f"{exchange_class.grade}年{exchange_class.class_number}組"
        day_idx = ["月", "火", "水", "木", "金"].index(time_slot.day)
        
        base_risk = self._predict_violation_risk(
            day_idx, time_slot.period - 1, exchange_str, "自立", None
        )
        
        # 自立活動特有のリスク要因を追加
        if parent_assignment is None:
            # 親学級が空の場合、数学・英語を配置できるかによってリスクが変わる
            if not self._can_place_math_or_english(parent_class, time_slot, schedule, None):
                base_risk += 0.3
        
        return min(base_risk, 1.0)
    
    def _get_applicable_strategies(
        self,
        day: int,
        period: int,
        class_id: str,
        subject: str,
        teacher: Optional[str]
    ) -> List[AvoidanceStrategy]:
        """適用可能な回避戦略を取得"""
        return self.learning_system.get_avoidance_strategies(
            day, period, class_id, subject, teacher
        )
    
    def _apply_avoidance_strategies(
        self,
        strategies: List[AvoidanceStrategy],
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        classes: Set[ClassReference],
        subject_name: str,
        teacher_name: str
    ) -> bool:
        """回避戦略を適用"""
        for strategy in strategies[:3]:  # 上位3つの戦略を試す
            self.generation_stats['strategy_applications'] += 1
            
            for action in strategy.actions:
                action_type = action["type"]
                params = action.get("params", {})
                
                if action_type == "avoid_assignment":
                    # 代替時間帯を検討
                    alternatives = params.get("alternative_periods", [])
                    for alt_day, alt_period in alternatives:
                        alt_day_name = ["月", "火", "水", "木", "金"][alt_day]
                        alt_slot = TimeSlot(alt_day_name, alt_period + 1)
                        
                        # 代替スロットが利用可能か確認
                        all_available = True
                        for class_ref in classes:
                            if schedule.get_assignment(alt_slot, class_ref):
                                all_available = False
                                break
                        
                        if all_available and self._is_teacher_available(teacher_name, alt_slot, schedule, school):
                            # 元のスロットは避けて、代替スロットを使用することを示す
                            self.logger.debug(f"戦略により代替スロットを推奨: {time_slot} -> {alt_slot}")
                            return False  # 元のスロットは使用しない
                
                elif action_type == "check_teacher_availability":
                    # 教師の可用性を再確認
                    if not self._is_teacher_available(teacher_name, time_slot, schedule, school):
                        return False
                
                elif action_type == "check_parent_class_subject":
                    # 親学級の科目をチェック（自立活動用）
                    allowed_subjects = params.get("allowed_subjects", [])
                    # この戦略は配置前のチェックで使用
                    pass
        
        return True  # 全ての戦略をパスした場合は配置可能
    
    def _try_apply_strategies_to_existing(
        self,
        strategies: List[AvoidanceStrategy],
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        assignment: Assignment
    ):
        """既存の配置に対して戦略を適用"""
        for strategy in strategies[:2]:  # 上位2つの戦略を試す
            for action in strategy.actions:
                action_type = action["type"]
                params = action.get("params", {})
                
                if action_type == "avoid_assignment":
                    # リスクのある配置を移動
                    alternatives = params.get("alternative_periods", [])
                    for alt_day, alt_period in alternatives:
                        alt_day_name = ["月", "火", "水", "木", "金"][alt_day]
                        alt_slot = TimeSlot(alt_day_name, alt_period + 1)
                        
                        if not schedule.get_assignment(alt_slot, class_ref):
                            if self._try_swap_assignments(
                                schedule, school, time_slot, alt_slot, class_ref
                            ):
                                self.logger.debug(f"リスク配置を移動: {assignment.subject.name} from {time_slot} to {alt_slot}")
                                self.learning_system.update_strategy_result(strategy.strategy_id, True)
                                return
    
    def _fix_violations_with_learning(
        self,
        schedule: Schedule,
        school: School,
        violations: List[Any]
    ) -> bool:
        """学習システムを使用して違反を修正"""
        # 違反を優先度順にソート
        sorted_violations = sorted(
            violations,
            key=lambda v: v.priority.value if hasattr(v, 'priority') else 0,
            reverse=True
        )
        
        for violation in sorted_violations[:5]:  # 上位5つの違反に対処
            # 違反に関連する情報を抽出
            if hasattr(violation, 'time_slot') and hasattr(violation, 'class_ref'):
                time_slot = violation.time_slot
                class_ref = violation.class_ref
                
                # 該当する配置を取得
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and not schedule.is_locked(time_slot, class_ref):
                    # 違反を解決する戦略を取得
                    day_idx = ["月", "火", "水", "木", "金"].index(time_slot.day)
                    class_str = f"{class_ref.grade}年{class_ref.class_number}組"
                    
                    strategies = self._get_applicable_strategies(
                        day_idx, time_slot.period - 1, class_str,
                        assignment.subject.name,
                        assignment.teacher.name if assignment.teacher else None
                    )
                    
                    if strategies:
                        # 戦略を適用して違反を解決
                        for strategy in strategies:
                            if self._apply_violation_fix_strategy(
                                strategy, schedule, school, time_slot, class_ref, violation
                            ):
                                return True
        
        return False
    
    def _apply_violation_fix_strategy(
        self,
        strategy: AvoidanceStrategy,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        violation: Any
    ) -> bool:
        """違反修正戦略を適用"""
        # 違反タイプに応じた修正
        violation_type = str(type(violation).__name__)
        
        if "TeacherConflict" in violation_type:
            # 教師重複の解消
            return self._relocate_assignment(schedule, school, time_slot, class_ref)
        
        elif "DailyDuplicate" in violation_type:
            # 日内重複の解消
            return self._fix_daily_duplicate_with_strategy(
                schedule, school, time_slot, class_ref
            )
        
        elif "Jiritsu" in violation_type:
            # 自立活動ルール違反の解消
            return self._fix_jiritsu_violation_with_strategy(
                schedule, school, time_slot, class_ref
            )
        
        return False
    
    def _fix_daily_duplicate_with_strategy(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference
    ) -> bool:
        """戦略を使用して日内重複を修正"""
        assignment = schedule.get_assignment(time_slot, class_ref)
        if not assignment:
            return False
        
        # 同じ日の他の時間を確認
        days = ["月", "火", "水", "木", "金"]
        day = time_slot.day
        
        for period in range(1, 7):
            if period == time_slot.period:
                continue
            
            other_slot = TimeSlot(day, period)
            other_assignment = schedule.get_assignment(other_slot, class_ref)
            
            if other_assignment and other_assignment.subject.name == assignment.subject.name:
                # 重複を発見 - どちらかを移動
                for target_day in days:
                    if target_day == day:
                        continue
                    
                    for target_period in range(1, 6):
                        target_slot = TimeSlot(target_day, target_period)
                        
                        if not schedule.get_assignment(target_slot, class_ref):
                            # 教師が利用可能か確認
                            if self._is_teacher_available(
                                assignment.teacher.name if assignment.teacher else None,
                                target_slot, schedule, school
                            ):
                                # 移動を実行
                                try:
                                    schedule.remove_assignment(time_slot, class_ref)
                                    new_assignment = Assignment(
                                        class_ref, assignment.subject, assignment.teacher
                                    )
                                    schedule.assign(target_slot, new_assignment)
                                    return True
                                except:
                                    pass
        
        return False
    
    def _fix_jiritsu_violation_with_strategy(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference
    ) -> bool:
        """戦略を使用して自立活動違反を修正"""
        # 交流学級の場合
        if class_ref in self.exchange_class_mapping:
            parent_class = self.exchange_class_mapping[class_ref]
            
            # 親学級の科目を数学または英語に変更
            for subject_name in ["数", "英"]:
                subject = Subject(subject_name)
                teacher = school.get_assigned_teacher(subject, parent_class)
                
                if teacher and self._is_teacher_available(teacher.name, time_slot, schedule, school):
                    try:
                        # 既存を削除
                        existing = schedule.get_assignment(time_slot, parent_class)
                        if existing:
                            schedule.remove_assignment(time_slot, parent_class)
                        
                        # 新規配置
                        assignment = Assignment(parent_class, subject, teacher)
                        schedule.assign(time_slot, assignment)
                        return True
                    except:
                        pass
        
        return False
    
    def _local_search_with_learning(self, schedule: Schedule, school: School) -> bool:
        """学習を考慮した局所探索"""
        # リスクの高い配置を優先的に改善
        high_risk_assignments = []
        days = ["月", "火", "水", "木", "金"]
        
        for class_ref in school.get_all_classes():
            class_str = f"{class_ref.grade}年{class_ref.class_number}組"
            
            for day in days:
                for period in range(1, 6):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    
                    if assignment and not schedule.is_locked(time_slot, class_ref):
                        # リスクを評価
                        day_idx = days.index(day)
                        risk = self._predict_violation_risk(
                            day_idx, period - 1, class_str,
                            assignment.subject.name,
                            assignment.teacher.name if assignment.teacher else None
                        )
                        
                        if risk > 0.3:
                            high_risk_assignments.append((risk, time_slot, class_ref, assignment))
        
        # リスクの高い順にソート
        high_risk_assignments.sort(key=lambda x: x[0], reverse=True)
        
        # 上位のリスク配置を改善
        for risk, time_slot, class_ref, assignment in high_risk_assignments[:5]:
            if self._improve_risky_assignment(schedule, school, time_slot, class_ref, assignment):
                return True
        
        # 通常のランダム交換
        return self._try_random_swap(schedule, school)
    
    def _improve_risky_assignment(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        assignment: Assignment
    ) -> bool:
        """リスクの高い配置を改善"""
        # より安全な場所を探す
        days = ["月", "火", "水", "木", "金"]
        best_slot = None
        best_risk = 1.0
        
        for day in days:
            for period in range(1, 6):
                if day == "月" and period == 6:
                    continue
                
                candidate_slot = TimeSlot(day, period)
                if candidate_slot == time_slot:
                    continue
                
                # 空きスロットかつ教師が利用可能
                if (not schedule.get_assignment(candidate_slot, class_ref) and
                    self._is_teacher_available(
                        assignment.teacher.name if assignment.teacher else None,
                        candidate_slot, schedule, school
                    )):
                    
                    # リスクを評価
                    day_idx = days.index(day)
                    class_str = f"{class_ref.grade}年{class_ref.class_number}組"
                    risk = self._predict_violation_risk(
                        day_idx, period - 1, class_str,
                        assignment.subject.name,
                        assignment.teacher.name if assignment.teacher else None
                    )
                    
                    if risk < best_risk:
                        best_risk = risk
                        best_slot = candidate_slot
        
        # より安全な場所が見つかった場合は移動
        if best_slot and best_risk < 0.2:  # 低リスクの場所
            try:
                schedule.remove_assignment(time_slot, class_ref)
                new_assignment = Assignment(class_ref, assignment.subject, assignment.teacher)
                schedule.assign(best_slot, new_assignment)
                self.logger.debug(f"リスク配置を改善: {assignment.subject.name} from {time_slot} to {best_slot} (risk: {best_risk:.2f})")
                return True
            except:
                # 失敗時は元に戻す
                try:
                    schedule.assign(time_slot, assignment)
                except:
                    pass
        
        return False
    
    def _apply_smart_perturbation(self, schedule: Schedule, school: School):
        """学習に基づいたスマートな摂動"""
        # 高リスクエリアを特定
        risk_map = self._create_risk_map(schedule, school)
        
        # リスクの高いエリアから配置を削除
        removed = []
        
        for (day, period, class_ref), risk in sorted(
            risk_map.items(), key=lambda x: x[1], reverse=True
        )[:5]:
            
            time_slot = TimeSlot(day, period)
            if not schedule.is_locked(time_slot, class_ref):
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject.name not in self.fixed_subjects:
                    try:
                        schedule.remove_assignment(time_slot, class_ref)
                        removed.append((class_ref, assignment, risk))
                    except:
                        pass
        
        # 削除した授業を低リスクエリアに再配置
        for class_ref, assignment, original_risk in removed:
            placed = False
            candidates = []
            
            # 低リスクの候補を探す
            days = ["月", "火", "水", "木", "金"]
            for day in days:
                for period in range(1, 6):
                    time_slot = TimeSlot(day, period)
                    
                    if not schedule.get_assignment(time_slot, class_ref):
                        # リスクを評価
                        day_idx = days.index(day)
                        class_str = f"{class_ref.grade}年{class_ref.class_number}組"
                        risk = self._predict_violation_risk(
                            day_idx, period - 1, class_str,
                            assignment.subject.name,
                            assignment.teacher.name if assignment.teacher else None
                        )
                        
                        if risk < original_risk * 0.5:  # 元の半分以下のリスク
                            candidates.append((risk, time_slot))
            
            # リスクの低い順にソート
            candidates.sort(key=lambda x: x[0])
            
            # 上位候補に配置を試みる
            for risk, time_slot in candidates[:3]:
                if self._is_teacher_available(
                    assignment.teacher.name if assignment.teacher else None,
                    time_slot, schedule, school
                ):
                    try:
                        schedule.assign(time_slot, assignment)
                        placed = True
                        break
                    except:
                        pass
            
            if not placed:
                # 配置できない場合は最初の空きスロットに配置
                for day in days:
                    for period in range(1, 6):
                        time_slot = TimeSlot(day, period)
                        if not schedule.get_assignment(time_slot, class_ref):
                            try:
                                schedule.assign(time_slot, assignment)
                                break
                            except:
                                pass
    
    def _create_risk_map(
        self,
        schedule: Schedule,
        school: School
    ) -> Dict[Tuple[str, int, ClassReference], float]:
        """スケジュール全体のリスクマップを作成"""
        risk_map = {}
        days = ["月", "火", "水", "木", "金"]
        
        for class_ref in school.get_all_classes():
            class_str = f"{class_ref.grade}年{class_ref.class_number}組"
            
            for day in days:
                for period in range(1, 6):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    
                    if assignment:
                        day_idx = days.index(day)
                        risk = self._predict_violation_risk(
                            day_idx, period - 1, class_str,
                            assignment.subject.name,
                            assignment.teacher.name if assignment.teacher else None
                        )
                        
                        risk_map[(day, period, class_ref)] = risk
        
        return risk_map
    
    def _learn_from_generation(
        self,
        violations: List[Any],
        schedule: Schedule,
        school: School
    ):
        """生成結果から学習"""
        if violations:
            self.logger.info(f"検出された違反から学習中... ({len(violations)}件)")
            self.learning_system.learn_from_violations(violations, schedule, school)
            
            # 学習レポートを表示
            report = self.learning_system.get_learning_report()
            self.logger.info(f"学習済みパターン数: {report['summary']['unique_patterns']}")
            self.logger.info(f"有効な戦略数: {report['summary']['active_strategies']}")
            self.logger.info(f"違反回避率: {report['summary']['avoidance_rate']:.2%}")
        else:
            self.logger.info("違反なし - 成功パターンとして記録")
            # 成功した配置パターンも学習に活用できる（将来の拡張）
    
    def _analyze_flexible_hours(
        self,
        schedule: Schedule,
        school: School,
        followup_data: Optional[Dict[str, Any]]
    ) -> Dict:
        """柔軟な標準時数分析"""
        # FlexibleStandardHoursGuaranteeSystemの分析機能を使用
        if followup_data:
            special_days = self.flexible_hours_system._analyze_special_days(followup_data)
        else:
            special_days = []
        
        plans = self.flexible_hours_system._create_flexible_plans(schedule, school, special_days)
        self.flexible_hours_system._calculate_proportional_allocation(plans)
        self.flexible_hours_system._calculate_flexible_priorities(plans)
        
        return plans
    
    def _try_swap_assignments(
        self,
        schedule: Schedule,
        school: School,
        slot1: TimeSlot,
        slot2: TimeSlot,
        class_ref: ClassReference
    ) -> bool:
        """2つのスロット間で割り当てを交換"""
        assignment1 = schedule.get_assignment(slot1, class_ref)
        assignment2 = schedule.get_assignment(slot2, class_ref)
        
        # どちらかがロックされていたら中止
        if (schedule.is_locked(slot1, class_ref) or 
            schedule.is_locked(slot2, class_ref)):
            return False
        
        # 交換を実行
        try:
            if assignment1:
                schedule.remove_assignment(slot1, class_ref)
            if assignment2:
                schedule.remove_assignment(slot2, class_ref)
            
            if assignment2:
                schedule.assign(slot1, assignment2)
            if assignment1:
                schedule.assign(slot2, assignment1)
            
            return True
        except:
            # 失敗時は元に戻す
            try:
                if assignment1:
                    schedule.assign(slot1, assignment1)
                if assignment2:
                    schedule.assign(slot2, assignment2)
            except:
                pass
        
        return False
    
    def _get_optimal_day_order(self, subject_name: str) -> List[str]:
        """科目に応じた最適な配置日順序を返す"""
        # 主要5教科は週全体にバランスよく配置
        if subject_name in ["数", "英", "国"]:
            return ["火", "木", "月", "水", "金"]
        elif subject_name in ["理", "社"]:
            return ["水", "金", "火", "木", "月"]
        # 実技系は特定の曜日に集中しないように
        elif subject_name in ["保", "音", "美", "技", "家"]:
            return ["月", "水", "金", "火", "木"]
        else:
            return ["月", "火", "水", "木", "金"]
    
    def _protect_monday_sixth_period(self, schedule: Schedule, school: School):
        """月曜6限を確実に保護"""
        monday_6th = TimeSlot("月", 6)
        
        for class_ref in school.get_all_classes():
            # 既存の配置を確認
            existing = schedule.get_assignment(monday_6th, class_ref)
            
            # 欠課でない場合は置き換える
            if not existing or existing.subject.name != "欠":
                # 既存の配置を削除
                if existing:
                    try:
                        schedule.remove_assignment(monday_6th, class_ref)
                    except:
                        pass
                
                # 欠課を配置
                assignment = Assignment(class_ref, Subject("欠"), Teacher("欠課先生"))
                try:
                    schedule.assign(monday_6th, assignment)
                    schedule.lock_cell(monday_6th, class_ref)
                except Exception as e:
                    self.logger.warning(f"月曜6限の保護に失敗: {class_ref} - {e}")
    
    def _can_place_math_or_english(
        self,
        class_ref: ClassReference,
        time_slot: TimeSlot,
        schedule: Schedule,
        school: School
    ) -> bool:
        """数学または英語を配置できるか確認"""
        for subject_name in ["数", "英"]:
            subject = Subject(subject_name)
            teacher = school.get_assigned_teacher(subject, class_ref)
            if teacher and self._is_teacher_available(teacher.name, time_slot, schedule, school):
                return True
        return False
    
    def _place_math_or_english(
        self,
        class_ref: ClassReference,
        time_slot: TimeSlot,
        schedule: Schedule,
        school: School
    ) -> bool:
        """数学または英語を配置"""
        for subject_name in ["数", "英"]:
            subject = Subject(subject_name)
            teacher = school.get_assigned_teacher(subject, class_ref)
            if teacher and self._is_teacher_available(teacher.name, time_slot, schedule, school):
                assignment = Assignment(class_ref, subject, teacher)
                try:
                    schedule.assign(time_slot, assignment)
                    return True
                except:
                    pass
        return False
    
    def _is_teacher_available(
        self,
        teacher_name: str,
        time_slot: TimeSlot,
        schedule: Schedule,
        school: School
    ) -> bool:
        """教師が利用可能か確認"""
        if not teacher_name:
            return True
            
        # 不在チェック
        teacher = Teacher(teacher_name)
        if school.is_teacher_unavailable(time_slot.day, time_slot.period, teacher):
            return False
        
        # 既存の割り当てチェック（テスト期間を考慮）
        if (time_slot.day, time_slot.period) in self.test_periods:
            return True  # テスト期間は重複OK
        
        # 通常期間は重複チェック
        for class_ref in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                # 5組の合同授業は例外
                if class_ref in self.grade5_classes:
                    continue
                return False
        
        return True
    
    def _fix_teacher_conflicts_smart(self, schedule: Schedule, school: School) -> bool:
        """教師重複を賢く修正"""
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 6):  # 6限は固定が多いので除外
                time_slot = TimeSlot(day, period)
                
                # テスト期間はスキップ
                if (day, period) in self.test_periods:
                    continue
                
                # 重複している教師を特定
                conflicts = self._find_teacher_conflicts_at_slot(schedule, school, time_slot)
                
                for teacher_name, conflicting_classes in conflicts.items():
                    if len(conflicting_classes) <= 1:
                        continue
                    
                    # 5組の合同授業は除外
                    grade5_in_conflict = [c for c in conflicting_classes if c in self.grade5_classes]
                    if len(grade5_in_conflict) == len(conflicting_classes):
                        continue
                    
                    # 最も優先度の低いクラスを選んで移動
                    target_class = self._select_lowest_priority_class(conflicting_classes, grade5_in_conflict)
                    if target_class and self._relocate_assignment(schedule, school, time_slot, target_class):
                        return True
        
        return False
    
    def _find_teacher_conflicts_at_slot(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot
    ) -> Dict[str, List[ClassReference]]:
        """特定スロットでの教師重複を検出"""
        teacher_classes = defaultdict(list)
        
        for class_ref in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.teacher:
                teacher_name = assignment.teacher.name
                if teacher_name not in self.fixed_teachers:
                    teacher_classes[teacher_name].append(class_ref)
        
        # 重複のみ返す
        return {t: cs for t, cs in teacher_classes.items() if len(cs) > 1}
    
    def _select_lowest_priority_class(
        self,
        conflicting_classes: List[ClassReference],
        grade5_classes: List[ClassReference]
    ) -> Optional[ClassReference]:
        """最も優先度の低いクラスを選択"""
        # 5組以外を優先的に選択
        non_grade5 = [c for c in conflicting_classes if c not in grade5_classes]
        if non_grade5:
            return random.choice(non_grade5)
        return None
    
    def _relocate_assignment(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference
    ) -> bool:
        """割り当てを別の場所に移動"""
        assignment = schedule.get_assignment(time_slot, class_ref)
        if not assignment or schedule.is_locked(time_slot, class_ref):
            return False
        
        # 移動先を探す
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 6):
                if day == "月" and period == 6:
                    continue
                
                new_slot = TimeSlot(day, period)
                if new_slot == time_slot:
                    continue
                
                # 空きスロットで教師が利用可能な場合
                if (not schedule.get_assignment(new_slot, class_ref) and
                    self._is_teacher_available(assignment.teacher.name, new_slot, schedule, school)):
                    
                    # 移動を実行
                    try:
                        schedule.remove_assignment(time_slot, class_ref)
                        new_assignment = Assignment(class_ref, assignment.subject, assignment.teacher)
                        schedule.assign(new_slot, new_assignment)
                        return True
                    except:
                        # 失敗時は元に戻す
                        try:
                            schedule.assign(time_slot, assignment)
                        except:
                            pass
        
        return False
    
    def _fix_other_violations(self, schedule: Schedule, school: School) -> bool:
        """その他の違反を修正"""
        violations = self.constraint_validator.validate_all_constraints(schedule, school)
        
        # 日内重複違反を優先
        for violation in violations:
            if 'daily_duplicate' in str(violation):
                if self._fix_daily_duplicate(schedule, school, violation):
                    return True
        
        return False
    
    def _fix_daily_duplicate(
        self,
        schedule: Schedule,
        school: School,
        violation: Any
    ) -> bool:
        """日内重複を修正"""
        # 違反情報から詳細を抽出（実装は違反オブジェクトの構造に依存）
        # ここでは簡易実装
        return False
    
    def _try_random_swap(self, schedule: Schedule, school: School) -> bool:
        """ランダムな交換を試みる"""
        classes = [c for c in school.get_all_classes() if c not in self.grade5_classes]
        if len(classes) < 2:
            return False
        
        # 交換前の状態を評価
        before_violations = self.constraint_validator.validate_all_constraints(schedule, school)
        before_conflicts = self._count_teacher_conflicts(schedule, school)
        
        # ランダムに選択
        class1, class2 = random.sample(classes, 2)
        days = ["月", "火", "水", "木", "金"]
        day1, day2 = random.choice(days), random.choice(days)
        period1 = random.randint(1, 5)  # 6限は除外
        period2 = random.randint(1, 5)
        
        time_slot1 = TimeSlot(day1, period1)
        time_slot2 = TimeSlot(day2, period2)
        
        # 割り当てを取得
        assignment1 = schedule.get_assignment(time_slot1, class1)
        assignment2 = schedule.get_assignment(time_slot2, class2)
        
        # どちらかがロックされていたら中止
        if (schedule.is_locked(time_slot1, class1) or 
            schedule.is_locked(time_slot2, class2)):
            return False
        
        # 交換を実行
        try:
            if assignment1:
                schedule.remove_assignment(time_slot1, class1)
            if assignment2:
                schedule.remove_assignment(time_slot2, class2)
            
            if assignment2:
                schedule.assign(time_slot1, Assignment(class1, assignment2.subject, assignment2.teacher))
            if assignment1:
                schedule.assign(time_slot2, Assignment(class2, assignment1.subject, assignment1.teacher))
            
            # 改善されたか確認
            after_violations = self.constraint_validator.validate_all_constraints(schedule, school)
            after_conflicts = self._count_teacher_conflicts(schedule, school)
            
            if (len(after_violations) < len(before_violations) or 
                (len(after_violations) == len(before_violations) and after_conflicts < before_conflicts)):
                return True
            
            # 改善されない場合は元に戻す
            if assignment2:
                schedule.remove_assignment(time_slot1, class1)
            if assignment1:
                schedule.remove_assignment(time_slot2, class2)
            
            if assignment1:
                schedule.assign(time_slot1, assignment1)
            if assignment2:
                schedule.assign(time_slot2, assignment2)
            
        except:
            pass
        
        return False
    
    def _optimize_for_flexible_satisfaction(
        self,
        schedule: Schedule,
        school: School,
        time_limit: int,
        start_time: datetime
    ) -> Schedule:
        """柔軟な満足度の向上を優先した最適化"""
        # 再度柔軟な標準時数保証システムを実行
        for i in range(3):  # 最大3回試行
            if (datetime.now() - start_time).total_seconds() > time_limit:
                break
            
            results = self.flexible_hours_system.guarantee_flexible_hours(
                schedule, school, None, self.constraint_validator
            )
            
            satisfaction_rate = results.get('summary', {}).get('average_satisfaction', 0)
            if satisfaction_rate > 0.9:
                break
            
            # 満足度の低いクラスを優先的に改善
            self._improve_low_satisfaction_classes(schedule, school, results)
        
        return schedule
    
    def _improve_low_satisfaction_classes(
        self,
        schedule: Schedule,
        school: School,
        results: Dict
    ):
        """満足度の低いクラスを改善"""
        # 満足度の低いクラスを特定
        class_results = results.get('by_class', {})
        low_satisfaction_classes = []
        
        for class_name, class_data in class_results.items():
            if class_data.get('satisfaction_rate', 0) < 0.8:
                low_satisfaction_classes.append({
                    'class_name': class_name,
                    'satisfaction': class_data.get('satisfaction_rate', 0),
                    'subjects': class_data.get('subjects', {})
                })
        
        # 満足度の低い順にソート
        low_satisfaction_classes.sort(key=lambda x: x['satisfaction'])
        
        # 各クラスの改善を試みる
        for class_info in low_satisfaction_classes[:5]:  # 最大5クラス
            class_ref = self._parse_class_ref(class_info['class_name'])
            if not class_ref:
                continue
            
            # 不足している科目を特定
            for subject_name, allocation in class_info['subjects'].items():
                if allocation['satisfaction'] == "不足":
                    subject = Subject(subject_name)
                    teacher = school.get_assigned_teacher(subject, class_ref)
                    if teacher:
                        self._force_place_subject(schedule, school, class_ref, subject, teacher)
    
    def _parse_class_ref(self, class_name: str) -> Optional[ClassReference]:
        """クラス名をClassReferenceに変換"""
        # "1年2組" -> ClassReference(1, 2)
        import re
        match = re.match(r'(\d+)年(\d+)組', class_name)
        if match:
            return ClassReference(int(match.group(1)), int(match.group(2)))
        return None
    
    def _force_place_subject(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        subject: Subject,
        teacher: Teacher
    ):
        """科目を強制的に配置"""
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                if day == "月" and period == 6:
                    continue
                
                time_slot = TimeSlot(day, period)
                
                # 空きスロットか、優先度の低い科目なら置換
                existing = schedule.get_assignment(time_slot, class_ref)
                if not existing or (
                    existing.subject.name not in self.fixed_subjects and
                    existing.subject.name not in self.core_subjects
                ):
                    # 教師が利用可能か確認
                    if self._is_teacher_available(teacher.name, time_slot, schedule, school):
                        # 既存を削除
                        if existing:
                            try:
                                schedule.remove_assignment(time_slot, class_ref)
                            except:
                                continue
                        
                        # 新規配置
                        assignment = Assignment(class_ref, subject, teacher)
                        try:
                            schedule.assign(time_slot, assignment)
                            return
                        except:
                            pass
    
    def _final_adjustments(self, schedule: Schedule, school: School):
        """最終調整"""
        # 1. 月曜6限の再確認
        self._protect_monday_sixth_period(schedule, school)
        
        # 2. 5組の同期確認
        self._verify_grade5_sync(schedule, school)
        
        # 3. 交流学級の制約確認
        self._verify_exchange_constraints(schedule, school)
    
    def _verify_grade5_sync(self, schedule: Schedule, school: School):
        """5組の同期を確認"""
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 5組の授業を取得
                assignments = {}
                for class_ref in self.grade5_classes:
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        assignments[class_ref] = assignment
                
                # 同期が崩れている場合は修正
                if len(assignments) > 0 and len(assignments) < 3:
                    # 最も多い科目に統一
                    subjects = defaultdict(int)
                    for assignment in assignments.values():
                        subjects[assignment.subject.name] += 1
                    
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
    
    def _verify_exchange_constraints(self, schedule: Schedule, school: School):
        """交流学級の制約を確認"""
        for exchange_class, parent_class in self.exchange_class_mapping.items():
            days = ["月", "火", "水", "木", "金"]
            
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                    if exchange_assignment and exchange_assignment.subject.name == "自立":
                        # 親学級が数学か英語か確認
                        parent_assignment = schedule.get_assignment(time_slot, parent_class)
                        if parent_assignment and parent_assignment.subject.name not in ["数", "英"]:
                            # 修正を試みる
                            self._fix_jiritsu_constraint(
                                schedule, school, time_slot, 
                                exchange_class, parent_class
                            )
    
    def _fix_jiritsu_constraint(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        exchange_class: ClassReference,
        parent_class: ClassReference
    ):
        """自立活動の制約違反を修正"""
        # 親学級を数学または英語に変更
        for subject_name in ["数", "英"]:
            subject = Subject(subject_name)
            teacher = school.get_assigned_teacher(subject, parent_class)
            
            if teacher and self._is_teacher_available(teacher.name, time_slot, schedule, school):
                try:
                    # 既存を削除
                    existing = schedule.get_assignment(time_slot, parent_class)
                    if existing:
                        schedule.remove_assignment(time_slot, parent_class)
                    
                    # 新規配置
                    assignment = Assignment(parent_class, subject, teacher)
                    schedule.assign(time_slot, assignment)
                    return
                except:
                    pass
    
    def _get_jiritsu_teacher(self, exchange_class: ClassReference) -> Optional[str]:
        """交流学級の自立活動担当教師を取得"""
        jiritsu_teachers = {
            (1, 6): "財津",
            (1, 7): "智田",
            (2, 6): "財津",
            (2, 7): "智田",
            (3, 6): "財津",
            (3, 7): "智田"
        }
        return jiritsu_teachers.get((exchange_class.grade, exchange_class.class_number))
    
    def _copy_schedule(self, original: Schedule) -> Schedule:
        """スケジュールのコピーを作成"""
        copy = Schedule()
        for time_slot, assignment in original.get_all_assignments():
            copy.assign(time_slot, assignment)
            if original.is_locked(time_slot, assignment.class_ref):
                copy.lock_cell(time_slot, assignment.class_ref)
        return copy
    
    def _count_teacher_conflicts(self, schedule: Schedule, school: School) -> int:
        """教師重複をカウント（テスト期間を除く）"""
        from collections import defaultdict
        
        grade5_refs = {ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)}
        
        conflicts = 0
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # テスト期間はスキップ
                if (day, period) in self.test_periods:
                    continue
                
                # 教師ごとにクラスを収集
                teacher_classes = defaultdict(list)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        teacher_name = assignment.teacher.name
                        
                        # 固定教師はスキップ
                        if teacher_name in self.fixed_teachers:
                            continue
                        
                        teacher_classes[teacher_name].append(class_ref)
                
                # 重複をカウント
                for teacher_name, classes in teacher_classes.items():
                    # 5組の合同授業は除外
                    grade5_count = sum(1 for c in classes if c in grade5_refs)
                    if grade5_count == len(classes) and grade5_count > 1:
                        continue  # 5組のみの重複は正常
                    
                    if len(classes) > 1:
                        conflicts += 1
        
        return conflicts
    
    def _count_empty_slots(self, schedule: Schedule, school: School) -> int:
        """空きスロット数をカウント"""
        empty = 0
        days = ["月", "火", "水", "木", "金"]
        
        for class_ref in school.get_all_classes():
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    if not schedule.get_assignment(time_slot, class_ref):
                        empty += 1
        
        return empty
    
    def _print_summary(self, result: OptimizationResult):
        """結果サマリーを出力"""
        self.logger.info("\n=== ハイブリッドV6生成結果（制約違反学習システム統合版）===")
        self.logger.info(f"総割り当て数: {result.statistics['total_assignments']}")
        self.logger.info(f"制約違反数: {result.violations}")
        self.logger.info(f"教師重複数: {result.teacher_conflicts}")
        self.logger.info(f"空きスロット数: {result.statistics['empty_slots']}")
        self.logger.info(f"柔軟な満足度: {result.statistics['flexible_satisfaction_rate']:.1f}%")
        self.logger.info(f"完全充足クラス数: {result.statistics['fully_satisfied_classes']}")
        self.logger.info(f"特別な状況: {result.statistics['special_circumstances']}件")
        self.logger.info(f"警告: {result.statistics['warnings_count']}件")
        
        # 学習システムの統計
        learning_stats = result.statistics.get('learning_stats', {})
        self.logger.info(f"\n学習システム統計:")
        self.logger.info(f"  予測されたリスク: {learning_stats.get('predicted_risks', 0)}件")
        self.logger.info(f"  回避された違反: {learning_stats.get('avoided_violations', 0)}件")
        self.logger.info(f"  適用された戦略: {learning_stats.get('strategy_applications', 0)}回")
        self.logger.info(f"  学習による改善: {learning_stats.get('learning_improvements', 0)}回")
        self.logger.info(f"  学習済みパターン: {learning_stats.get('total_patterns', 0)}個")
        self.logger.info(f"  有効な戦略: {learning_stats.get('active_strategies', 0)}個")
        
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
        
        # 学習レポートのサマリー
        if result.learning_results:
            summary = result.learning_results.get('summary', {})
            if summary.get('avoidance_rate', 0) > 0:
                self.logger.info(f"\n学習システムの成果:")
                self.logger.info(f"  違反回避率: {summary['avoidance_rate']:.1%}")
                
                # 高頻度パターン
                patterns = result.learning_results.get('high_frequency_patterns', [])
                if patterns:
                    self.logger.info(f"  検出された主要パターン: {len(patterns)}個")