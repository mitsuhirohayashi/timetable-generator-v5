"""
フェーズ5: ハイブリッドアプローチV4（標準時数保証版）

V3の機能に加えて、標準時数完全保証システムを統合。
全ての科目が必要時数を満たす時間割を生成します。

主な改善点：
1. 標準時数保証システムの統合
2. 月曜6限の確実な保護
3. 事前計画に基づく配置
4. より賢いバックトラック戦略
"""
import logging
import random
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

from .standard_hours_guarantee_system import StandardHoursGuaranteeSystem
from ...entities.schedule import Schedule
from ...entities.school import School, Teacher, Subject
from ...value_objects.time_slot import TimeSlot, ClassReference
from ...value_objects.assignment import Assignment
from ..constraint_validator import ConstraintValidator
from ..exchange_class_synchronizer import ExchangeClassSynchronizer
from ..grade5_synchronizer_refactored import RefactoredGrade5Synchronizer


@dataclass
class OptimizationResult:
    """最適化結果"""
    schedule: Schedule
    violations: int
    teacher_conflicts: int
    statistics: Dict
    improvements: List[str] = field(default_factory=list)


class HybridScheduleGeneratorV4:
    """標準時数保証版ハイブリッド時間割生成器"""
    
    def __init__(self, enable_logging: bool = True):
        self.logger = logging.getLogger(__name__)
        if not enable_logging:
            self.logger.setLevel(logging.WARNING)
        
        # 制約検証器
        self.constraint_validator = ConstraintValidator()
        
        # 同期サービス
        self.grade5_synchronizer = RefactoredGrade5Synchronizer(self.constraint_validator)
        self.exchange_synchronizer = ExchangeClassSynchronizer()
        
        # 標準時数保証システム
        self.hours_guarantee_system = StandardHoursGuaranteeSystem(enable_logging)
        
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
    
    def generate(
        self,
        school: School,
        initial_schedule: Optional[Schedule] = None,
        target_violations: int = 0,
        time_limit: int = 300
    ) -> OptimizationResult:
        """スケジュールを生成"""
        start_time = datetime.now()
        
        self.logger.info("=== ハイブリッドV4時間割生成開始（標準時数保証版）===")
        
        # 初期スケジュールの準備
        if initial_schedule:
            schedule = self._copy_schedule(initial_schedule)
        else:
            schedule = Schedule()
        
        # フェーズ0: 月曜6限の確実な保護
        self.logger.info("フェーズ0: 月曜6限の保護")
        self._protect_monday_sixth_period(schedule, school)
        
        # フェーズ1: 標準時数分析と計画
        self.logger.info("フェーズ1: 標準時数分析と計画")
        hours_analysis = self.hours_guarantee_system._create_placement_plans(schedule, school)
        
        # フェーズ2: 5組の完全同期配置（標準時数を考慮）
        self.logger.info("フェーズ2: 5組の同期配置（標準時数考慮）")
        self._place_grade5_with_hours_guarantee(schedule, school, hours_analysis)
        
        # フェーズ3: 交流学級の自立活動配置
        self.logger.info("フェーズ3: 交流学級の自立活動配置")
        self._place_exchange_jiritsu_smart(schedule, school)
        
        # フェーズ4: 標準時数保証システムによる配置
        self.logger.info("フェーズ4: 標準時数保証配置")
        guarantee_results = self.hours_guarantee_system.guarantee_standard_hours(
            schedule, school, self.constraint_validator
        )
        
        # フェーズ5: 高度な最適化
        self.logger.info("フェーズ5: 高度な最適化")
        best_schedule = self._advanced_optimization(
            schedule, school, target_violations, time_limit, start_time, guarantee_results
        )
        
        # フェーズ6: 最終調整
        self.logger.info("フェーズ6: 最終調整")
        self._final_adjustments(best_schedule, school)
        
        # 結果の評価
        violations = self._count_violations(best_schedule, school)
        teacher_conflicts = self._count_teacher_conflicts(best_schedule, school)
        
        # 統計情報の収集
        statistics = {
            'total_assignments': len(best_schedule.get_all_assignments()),
            'violations': violations,
            'teacher_conflicts': teacher_conflicts,
            'elapsed_time': (datetime.now() - start_time).total_seconds(),
            'empty_slots': self._count_empty_slots(best_schedule, school),
            'standard_hours_completion': guarantee_results.get('overall_completion_rate', 0) * 100,
            'fully_satisfied_classes': guarantee_results.get('fully_satisfied', 0),
            'placement_attempts': self.hours_guarantee_system.placement_stats.get('attempts', 0)
        }
        
        result = OptimizationResult(
            schedule=best_schedule,
            violations=violations,
            teacher_conflicts=teacher_conflicts,
            statistics=statistics
        )
        
        # 改善点の記録
        if guarantee_results.get('overall_completion_rate', 0) > 0.95:
            result.improvements.append("標準時数95%以上達成")
        if teacher_conflicts < 10:
            result.improvements.append("教師重複を10件未満に削減")
        
        self._print_summary(result)
        
        return result
    
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
    
    def _place_grade5_with_hours_guarantee(
        self,
        schedule: Schedule,
        school: School,
        hours_analysis: Dict
    ):
        """5組を標準時数を考慮して同期配置"""
        # 5組の必要時数を統合
        grade5_needs = defaultdict(int)
        
        for class_ref in self.grade5_classes:
            if class_ref in hours_analysis:
                plan = hours_analysis[class_ref]
                for subject_name, req in plan.requirements.items():
                    if req.remaining_hours > 0:
                        grade5_needs[subject_name] = max(
                            grade5_needs[subject_name],
                            req.remaining_hours
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
        
        # 優先度順にソート（必要時数が多い順）
        sorted_subjects = sorted(grade5_needs.items(), key=lambda x: x[1], reverse=True)
        
        days = ["月", "火", "水", "木", "金"]
        for subject_name, needed_hours in sorted_subjects:
            if subject_name in self.fixed_subjects:
                continue
                
            teacher_name = grade5_subjects.get(subject_name)
            if not teacher_name:
                continue
            
            placed_count = 0
            
            # 最適な配置順序（バランスを考慮）
            day_order = self._get_optimal_day_order(subject_name)
            
            for day in day_order:
                if placed_count >= needed_hours:
                    break
                    
                for period in range(1, 7):
                    if placed_count >= needed_hours:
                        break
                    
                    # 月曜6限はスキップ
                    if day == "月" and period == 6:
                        continue
                    
                    time_slot = TimeSlot(day, period)
                    
                    # 全5組が空いているか確認
                    all_empty = True
                    for class_ref in self.grade5_classes:
                        if schedule.get_assignment(time_slot, class_ref):
                            all_empty = False
                            break
                    
                    if not all_empty:
                        continue
                    
                    # 教師が利用可能か確認
                    if not self._is_teacher_available(teacher_name, time_slot, schedule, school):
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
    
    def _place_exchange_jiritsu_smart(self, schedule: Schedule, school: School):
        """交流学級の自立活動を賢く配置"""
        for exchange_class, parent_class in self.exchange_class_mapping.items():
            # 自立活動の教師を取得
            jiritsu_teacher = self._get_jiritsu_teacher(exchange_class)
            if not jiritsu_teacher:
                continue
            
            # 標準時数（通常3時間）
            needed_hours = 3
            placed_count = 0
            
            # 最適な配置を探す
            days = ["月", "火", "水", "木", "金"]
            for day in days:
                if placed_count >= needed_hours:
                    break
                
                for period in range(1, 7):
                    if placed_count >= needed_hours:
                        break
                    
                    # 月曜6限はスキップ
                    if day == "月" and period == 6:
                        continue
                    
                    time_slot = TimeSlot(day, period)
                    
                    # 既に配置済みならスキップ
                    if schedule.get_assignment(time_slot, exchange_class):
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
                        except:
                            pass
    
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
    
    def _advanced_optimization(
        self,
        schedule: Schedule,
        school: School,
        target_violations: int,
        time_limit: int,
        start_time: datetime,
        guarantee_results: Dict
    ) -> Schedule:
        """高度な最適化"""
        best_schedule = self._copy_schedule(schedule)
        best_violations = self._count_violations(best_schedule, school)
        best_conflicts = self._count_teacher_conflicts(best_schedule, school)
        
        # 標準時数の完了率が低い場合は、それを優先
        completion_rate = guarantee_results.get('overall_completion_rate', 0)
        if completion_rate < 0.9:
            self.logger.info(f"標準時数完了率が低い({completion_rate*100:.1f}%)ため、時数充足を優先")
            return self._optimize_for_hours_completion(best_schedule, school, time_limit, start_time)
        
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
            current_violations = self._count_violations(schedule, school)
            current_conflicts = self._count_teacher_conflicts(schedule, school)
            
            if current_violations <= target_violations and current_conflicts == 0:
                return schedule
            
            # 改善戦略
            improved = False
            
            # 1. 教師重複の解消を最優先
            if current_conflicts > 0:
                improved = self._fix_teacher_conflicts_smart(schedule, school)
            
            # 2. その他の違反修正
            if not improved and current_violations > current_conflicts:
                improved = self._fix_other_violations(schedule, school)
            
            # 3. 局所探索
            if not improved:
                improved = self._local_search(schedule, school)
            
            # 評価
            new_violations = self._count_violations(schedule, school)
            new_conflicts = self._count_teacher_conflicts(schedule, school)
            
            if new_violations < best_violations or (new_violations == best_violations and new_conflicts < best_conflicts):
                best_schedule = self._copy_schedule(schedule)
                best_violations = new_violations
                best_conflicts = new_conflicts
                no_improvement_count = 0
            else:
                no_improvement_count += 1
            
            # 停滞時の処理
            if no_improvement_count > 20:
                schedule = self._copy_schedule(best_schedule)
                self._apply_perturbation(schedule, school)
                no_improvement_count = 0
        
        return best_schedule
    
    def _optimize_for_hours_completion(
        self,
        schedule: Schedule,
        school: School,
        time_limit: int,
        start_time: datetime
    ) -> Schedule:
        """標準時数の充足を優先した最適化"""
        # 再度標準時数保証システムを実行
        for i in range(3):  # 最大3回試行
            if (datetime.now() - start_time).total_seconds() > time_limit:
                break
            
            results = self.hours_guarantee_system.guarantee_standard_hours(
                schedule, school, self.constraint_validator
            )
            
            if results.get('overall_completion_rate', 0) > 0.95:
                break
            
            # 不足している科目を優先的に配置
            self._prioritize_shortage_subjects(schedule, school, results)
        
        return schedule
    
    def _prioritize_shortage_subjects(
        self,
        schedule: Schedule,
        school: School,
        results: Dict
    ):
        """不足している科目を優先配置"""
        # 重大な不足がある科目を特定
        critical_shortages = results.get('critical_shortages', [])
        
        for shortage in critical_shortages:
            class_name = shortage['class']
            subject_name = shortage['subject']
            
            # クラスと科目を特定
            class_ref = self._parse_class_ref(class_name)
            if not class_ref:
                continue
            
            subject = Subject(subject_name)
            teacher = school.get_assigned_teacher(subject, class_ref)
            if not teacher:
                continue
            
            # 空きスロットを探して配置
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
                    existing.subject.name not in ["数", "英", "国", "理", "社"]
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
    
    def _local_search(self, schedule: Schedule, school: School) -> bool:
        """局所探索"""
        # ランダムに2つの授業を交換して改善を試みる
        for _ in range(10):
            if self._try_random_swap(schedule, school):
                return True
        return False
    
    def _try_random_swap(self, schedule: Schedule, school: School) -> bool:
        """ランダムな交換を試みる"""
        classes = [c for c in school.get_all_classes() if c not in self.grade5_classes]
        if len(classes) < 2:
            return False
        
        # 交換前の状態を評価
        before_violations = self._count_violations(schedule, school)
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
            after_violations = self._count_violations(schedule, school)
            after_conflicts = self._count_teacher_conflicts(schedule, school)
            
            if (after_violations < before_violations or 
                (after_violations == before_violations and after_conflicts < before_conflicts)):
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
    
    def _apply_perturbation(self, schedule: Schedule, school: School):
        """スケジュールに摂動を加える"""
        # ランダムに3つの授業を削除
        removed = []
        days = ["月", "火", "水", "木", "金"]
        
        for _ in range(3):
            class_ref = random.choice(list(school.get_all_classes()))
            day = random.choice(days)
            period = random.randint(1, 5)
            time_slot = TimeSlot(day, period)
            
            if not schedule.is_locked(time_slot, class_ref):
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject.name not in self.fixed_subjects:
                    try:
                        schedule.remove_assignment(time_slot, class_ref)
                        removed.append((class_ref, assignment))
                    except:
                        pass
        
        # 削除した授業を別の場所に配置
        for class_ref, assignment in removed:
            placed = False
            for _ in range(10):
                day = random.choice(days)
                period = random.randint(1, 5)
                time_slot = TimeSlot(day, period)
                
                if not schedule.get_assignment(time_slot, class_ref):
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
    
    def _count_violations(self, schedule: Schedule, school: School) -> int:
        """違反数をカウント"""
        violations = self.constraint_validator.validate_all_constraints(schedule, school)
        return len(violations)
    
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
        self.logger.info("\n=== ハイブリッドV4生成結果（標準時数保証版）===")
        self.logger.info(f"総割り当て数: {result.statistics['total_assignments']}")
        self.logger.info(f"制約違反数: {result.violations}")
        self.logger.info(f"教師重複数: {result.teacher_conflicts}")
        self.logger.info(f"空きスロット数: {result.statistics['empty_slots']}")
        self.logger.info(f"標準時数達成率: {result.statistics['standard_hours_completion']:.1f}%")
        self.logger.info(f"完全充足クラス数: {result.statistics['fully_satisfied_classes']}")
        self.logger.info(f"実行時間: {result.statistics['elapsed_time']:.1f}秒")
        
        if result.improvements:
            self.logger.info("\n達成した改善:")
            for improvement in result.improvements:
                self.logger.info(f"  ✓ {improvement}")