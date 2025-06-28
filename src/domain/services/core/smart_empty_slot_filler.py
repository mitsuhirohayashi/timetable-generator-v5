"""リファクタリング版スマート空きコマ埋めサービス

ExchangeClassServiceとConstraintValidatorを使用して、
重複コードを排除し、責任を明確に分離したバージョン。
"""

import logging
import random
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict
from ....shared.mixins.logging_mixin import LoggingMixin

from ...entities.schedule import Schedule
from ...entities.school import School, Subject, Teacher
from ...value_objects.time_slot import ClassReference, TimeSlot
from ...value_objects.assignment import Assignment
from ..synchronizers.exchange_class_service import ExchangeClassService
from ..validators.unified_constraint_validator import UnifiedConstraintValidator
from ..validators.daily_duplicate_preventer import DailyDuplicatePreventer
# NOTE: These imports violate Clean Architecture - fill strategies are in application layer
from ...interfaces.fill_strategy import FillStrategy
from ....application.services.generators.fill_strategies import (
    StrictFillStrategy,
    BalancedFillStrategy,
    RelaxedFillStrategy,
    UltraRelaxedFillStrategy,
    ForcedFillStrategy,
    FlexibleFillingStrategy
)
from ...utils.schedule_utils import ScheduleUtils
from ..synchronizers.grade5_teacher_selector import Grade5TeacherSelector


class SmartEmptySlotFiller(LoggingMixin):
    """リファクタリング版スマート空きコマ埋めサービス
    
    主な改善点:
    1. 交流学級ロジックをExchangeClassServiceに委譲
    2. 制約チェックをConstraintValidatorに委譲
    3. 責任を空きスロットの発見と埋め込み戦略の適用に限定
    """
    
    def __init__(self, constraint_system, absence_loader=None, homeroom_teachers=None, 
                 sixth_period_rules=None, priority_subjects=None, teacher_ratios=None):
        """初期化
        
        Args:
            constraint_system: 統一制約システム
            absence_loader: 教師不在情報ローダー
            homeroom_teachers: 担任教師マッピング（QA.txtから読み込み）
            sixth_period_rules: 6限目のルール（QA.txtから読み込み）
            priority_subjects: 優先教科リスト（QA.txtから読み込み）
            teacher_ratios: 教師比率（QA.txtから読み込み）
        """
        super().__init__()
        self.constraint_system = constraint_system
        self.homeroom_teachers = homeroom_teachers or {}
        self.sixth_period_rules = sixth_period_rules or {}
        self.priority_subjects = priority_subjects or ["算", "国", "理", "社", "英", "数"]
        
        # 委譲するサービス
        self.exchange_service = ExchangeClassService()
        self.grade5_teacher_selector = Grade5TeacherSelector(teacher_ratios)
        self.constraint_validator = UnifiedConstraintValidator(
            unified_system=constraint_system,
            absence_loader=absence_loader
        )
        self.duplicate_preventer = DailyDuplicatePreventer()
        
        # 戦略マッピング
        self.strategies = {
            1: StrictFillStrategy(),
            2: BalancedFillStrategy(),
            3: RelaxedFillStrategy(),
            4: UltraRelaxedFillStrategy(),
            5: FlexibleFillingStrategy()  # 人間的な柔軟性を持つ最終戦略
        }
        self.forced_strategy = ForcedFillStrategy()
        
        # 5組クラスの設定
        self.grade5_classes = self.constraint_validator.grade5_classes
        
        # 統計情報
        self.stats = defaultdict(int)        
        # 未配置スロットの詳細記録
        self.unfilled_slots = {}
    
    def fill_empty_slots_smartly(self, schedule: Schedule, school: School, max_passes: int = 5) -> int:
        """戦略パターンを使用して空きスロットを段階的に埋める"""
        self.logger.info("リファクタリング版スマート空きコマ埋め開始")
        
        total_filled = 0
        
        for pass_num in range(1, max_passes + 1):
            strategy = self.strategies.get(pass_num, self.forced_strategy)
            check_level = self._get_check_level_for_strategy(strategy)
            
            self.logger.info(f"\n=== 第{pass_num}パス開始（{strategy.name}戦略、チェックレベル: {check_level}） ===")
            
            # 空きスロットを見つける
            empty_slots = self._find_empty_slots(schedule, school)
            if not empty_slots:
                self.logger.info("空きスロットがないため終了")
                break
            
            self.logger.info(f"空きスロット数: {len(empty_slots)}")
            
            filled = 0
            
            # クラスタイプ別に処理
            filled += self._fill_by_class_type(schedule, school, empty_slots, strategy, check_level)
            
            total_filled += filled
            self.logger.info(f"第{pass_num}パス完了: {filled}スロット埋め")
            
            # 進捗がない場合、次の戦略へ
            if filled == 0 and pass_num < max_passes:
                self.logger.info("進捗なし - 次の戦略へ移行")
        
        self._log_statistics()
        return total_filled
    
    def _get_check_level_for_strategy(self, strategy: FillStrategy) -> str:
        """戦略に応じたチェックレベルを取得"""
        if isinstance(strategy, StrictFillStrategy):
            return 'strict'
        elif isinstance(strategy, (BalancedFillStrategy, RelaxedFillStrategy)):
            return 'normal'
        else:
            return 'relaxed'
    
    def _fill_by_class_type(
        self, 
        schedule: Schedule, 
        school: School, 
        empty_slots: List[Tuple[TimeSlot, ClassReference]],
        strategy: FillStrategy,
        check_level: str
    ) -> int:
        """クラスタイプ別に空きスロットを埋める"""
        filled = 0
        
        # クラスをタイプ別に分類
        exchange_slots = []
        parent_slots = []
        grade5_slots = []
        regular_slots = []
        
        for time_slot, class_ref in empty_slots:
            if self.exchange_service.is_exchange_class(class_ref):
                exchange_slots.append((time_slot, class_ref))
            elif self.exchange_service.is_parent_class(class_ref):
                parent_slots.append((time_slot, class_ref))
            elif class_ref in self.grade5_classes:
                grade5_slots.append((time_slot, class_ref))
            else:
                regular_slots.append((time_slot, class_ref))
        
        # 処理順序: 親学級 → 交流学級 → 5組 → 通常クラス
        # （親学級を先に処理することで、交流学級の同期が容易になる）
        for slots, class_type in [
            (parent_slots, "親学級"),
            (exchange_slots, "交流学級"),
            (grade5_slots, "5組"),
            (regular_slots, "通常クラス")
        ]:
            if slots:
                self.logger.debug(f"{class_type}の空きスロット処理中: {len(slots)}個")
                if class_type == "5組":
                    filled += self._fill_grade5_slots(schedule, school, slots, strategy, check_level)
                else:
                    filled += self._fill_slots(schedule, school, slots, strategy, check_level)
        
        return filled
    
    def _fill_slots(
        self,
        schedule: Schedule,
        school: School,
        slots: List[Tuple[TimeSlot, ClassReference]],
        strategy: FillStrategy,
        check_level: str
    ) -> int:
        """通常のスロット埋め処理"""
        filled = 0
        
        for time_slot, class_ref in slots:
            if self._fill_single_slot(schedule, school, time_slot, class_ref, strategy, check_level):
                filled += 1
                
                # 親学級の場合、交流学級も同期
                if self.exchange_service.is_parent_class(class_ref):
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        self.exchange_service.sync_exchange_with_parent(
                            schedule, school, time_slot, class_ref, assignment
                        )
        
        return filled
    
    def _fill_grade5_slots(
        self,
        schedule: Schedule,
        school: School,
        slots: List[Tuple[TimeSlot, ClassReference]],
        strategy: FillStrategy,
        check_level: str
    ) -> int:
        """5組の空きスロットを同期的に埋める"""
        filled = 0
        
        # タイムスロットごとにグループ化
        slots_by_time = defaultdict(list)
        for time_slot, class_ref in slots:
            slots_by_time[time_slot].append(class_ref)
        
        # 水曜4限を最優先で処理
        wed4_slot = TimeSlot("水", 4)
        if wed4_slot in slots_by_time:
            self.logger.info("=== 5組の水曜4限を優先的に処理 ===")
            # ensure_grade5_syncを使って確実に同期
            from .grade5_synchronizer_refactored import RefactoredGrade5Synchronizer
            synchronizer = RefactoredGrade5Synchronizer(self.constraint_validator.unified_system)
            if synchronizer.ensure_grade5_sync(schedule, school, wed4_slot):
                # 成功した場合、該当スロットの数だけfilled増加
                filled += len([c for c in slots_by_time[wed4_slot] if c in self.grade5_classes])
                self.logger.info(f"水曜4限の5組同期完了: {filled}スロット埋め")
            
            # 処理済みのスロットを削除
            del slots_by_time[wed4_slot]
        
        # 各タイムスロットを処理（部分的な空きも含む）
        for time_slot, empty_classes in slots_by_time.items():
            # 既に配置されている5組の授業を確認
            existing_assignments = {}
            existing_subject = None
            existing_teacher = None
            
            for class_ref in self.grade5_classes:
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment:
                    existing_assignments[class_ref] = assignment
                    if not existing_subject:
                        existing_subject = assignment.subject
                        existing_teacher = assignment.teacher
            
            # 既に配置がある場合は、同じ科目・教師で空きを埋める
            if existing_subject and existing_teacher:
                for class_ref in empty_classes:
                    if class_ref in self.grade5_classes:
                        assignment = Assignment(class_ref, existing_subject, existing_teacher)
                        if schedule.assign(time_slot, assignment):
                            filled += 1
                            # キャッシュをクリア（5組割り当て後も必要）
                            self.constraint_validator.clear_cache()
                            self.logger.info(
                                f"{time_slot} 5組同期割り当て（既存に合わせる）: "
                                f"{class_ref} → {existing_subject.name}({existing_teacher.name})"
                            )
            
            # 全ての5組が空いている場合は、最適な科目を選択
            elif len(empty_classes) >= len([c for c in empty_classes if c in self.grade5_classes]):
                subject, teacher = self._find_best_subject_for_grade5(
                    schedule, school, time_slot, strategy, check_level
                )
                
                if subject and teacher:
                    # 空いている5組全てに同じ教科・教師を割り当て
                    for class_ref in empty_classes:
                        if class_ref in self.grade5_classes:
                            assignment = Assignment(class_ref, subject, teacher)
                            if schedule.assign(time_slot, assignment):
                                filled += 1
                                # キャッシュをクリア（5組割り当て後も必要）
                                self.constraint_validator.clear_cache()
                                self.logger.info(
                                    f"{time_slot} 5組同期割り当て（新規）: "
                                    f"{class_ref} → {subject.name}({teacher.name})"
                                )
        
        return filled
    
    def _fill_single_slot(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        strategy: FillStrategy,
        check_level: str
    ) -> bool:
        """単一の空きスロットを戦略に従って埋める"""
        # 不足科目を取得
        shortage_subjects = self._get_shortage_subjects_prioritized(schedule, school, class_ref)
        
        # 教師負担を計算
        teacher_loads = self._calculate_teacher_loads(schedule, school)
        
        # 戦略に従って候補リストを作成
        candidates = strategy.create_candidates(
            schedule, school, time_slot, class_ref, shortage_subjects, teacher_loads
        )
        
        # 各候補を試す
        for subject, teacher in candidates:
            # Daily duplicate pre-check
            can_place_no_dup, dup_reason = self.duplicate_preventer.can_place_subject(
                schedule, time_slot, class_ref, subject, check_level
            )
            
            if not can_place_no_dup:
                self.logger.debug(f"Daily duplicate prevented: {dup_reason}")
                self.stats['blocked_by_daily_duplicate_preventer'] += 1
                continue
            
            assignment = Assignment(class_ref, subject, teacher)
            
            # 統一制約チェック
            can_place, error_msg = self.constraint_validator.can_place_assignment(
                schedule, school, time_slot, assignment, check_level
            )
            
            if can_place:
                # 割り当て実行
                schedule.assign(time_slot, assignment)
                # キャッシュをクリア（重要：新しい割り当て後は必ずキャッシュをクリア）
                self.constraint_validator.clear_cache()
                self.duplicate_preventer.clear_cache()
                
                self.logger.debug(
                    f"{time_slot} {class_ref}: {subject.name}({teacher.name})を割り当て（{strategy.name}戦略）"
                )
                self.stats[f'{strategy.name}_filled'] += 1
                return True
            else:
                self.stats[f'blocked_by_{self._categorize_error(error_msg)}'] += 1
        
        return False
    
    def _categorize_error(self, error_msg: str) -> str:
        """エラーメッセージをカテゴリ分類"""
        if "不在" in error_msg:
            return "teacher_absence"
        elif "重複" in error_msg or "既に" in error_msg:
            return "daily_duplicate"
        elif "交流学級" in error_msg or "親学級" in error_msg:
            return "exchange_constraint"
        elif "体育館" in error_msg:
            return "gym_constraint"
        elif "5組同期" in error_msg:
            return "grade5_sync"
        else:
            return "other"
    
    def _find_best_subject_for_grade5(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        strategy: FillStrategy,
        check_level: str
    ) -> Tuple[Optional[Subject], Optional[Teacher]]:
        """5組に最適な教科と教師を見つける（標準時数を超えても配置可能）"""
        # First, get safe subjects that won't cause daily duplicates
        safe_subjects_for_grade5 = []
        
        # Check each Grade 5 class to ensure the subject won't cause duplicates
        for class_name in self.grade5_classes:
            class_ref = ClassReference.from_string(class_name)
            safe_subjects = self.duplicate_preventer.find_safe_subjects_for_slot(
                schedule, school, time_slot, class_ref, check_level
            )
            safe_subjects_for_grade5.append(set(s.name for s in safe_subjects))
        
        # Get intersection - subjects safe for ALL Grade 5 classes
        if safe_subjects_for_grade5:
            common_safe_subjects = set.intersection(*safe_subjects_for_grade5)
        else:
            common_safe_subjects = set()
        
        self.logger.debug(f"Safe subjects for Grade 5 at {time_slot}: {common_safe_subjects}")
        # 各クラスの標準時数を取得
        base_hours_by_class = {}
        for class_ref in self.grade5_classes:
            base_hours_by_class[class_ref] = school.get_all_standard_hours(class_ref)
        
        # 全科目の標準時数を集計（固定科目を除く）
        combined_base_hours = defaultdict(int)
        for class_ref in self.grade5_classes:
            for subject, hours in base_hours_by_class[class_ref].items():
                if not ScheduleUtils.is_fixed_subject(subject.name):
                    combined_base_hours[subject] += hours
        
        # 現在の配置数を集計
        current_hours = defaultdict(int)
        days = ["月", "火", "水", "木", "金"]
        for class_ref in self.grade5_classes:
            for day in days:
                for period in range(1, 7):
                    ts = TimeSlot(day, period)
                    assignment = schedule.get_assignment(ts, class_ref)
                    if assignment and assignment.subject:
                        current_hours[assignment.subject] += 1
        
        # 標準時数の多い順でソート（主要教科を優先）
        sorted_subjects = []
        
        # まず主要教科
        priority_subjects = getattr(self, 'priority_subjects', ["算", "国", "理", "社", "英", "数"])
        for subject, base_hours in sorted(combined_base_hours.items(), key=lambda x: x[1], reverse=True):
            if subject.name in priority_subjects:
                sorted_subjects.append(subject)
        
        # 次にその他の教科
        for subject, base_hours in sorted(combined_base_hours.items(), key=lambda x: x[1], reverse=True):
            if subject not in sorted_subjects:
                sorted_subjects.append(subject)
        
        # 各教科について教師を探す
        for subject in sorted_subjects:
            # Skip if this subject would cause daily duplicates
            if subject.name not in common_safe_subjects:
                self.logger.debug(f"Skipping {subject.name} - would cause daily duplicates")
                continue
            
            # 5組担当可能な教師を取得
            teacher = self._get_grade5_teacher(school, subject)
            
            if teacher:
                # 全クラスで配置可能かチェック
                all_valid = True
                for class_ref in self.grade5_classes:
                    assignment = Assignment(class_ref, subject, teacher)
                    can_place, _ = self.constraint_validator.can_place_assignment(
                        schedule, school, time_slot, assignment, check_level
                    )
                    if not can_place:
                        all_valid = False
                        break
                
                if all_valid:
                    return subject, teacher
        
        return None, None
    
    def _find_empty_slots(self, schedule: Schedule, school: School) -> List[Tuple[TimeSlot, ClassReference]]:
        """空きスロットを見つける"""
        empty_slots = []
        priority_slots = []  # 優先度の高いスロット（3年生の6限）
        grade5_wed4_slots = []  # 5組の水曜4限（最優先）
        
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # テストピリオドはスキップ
                if self.constraint_validator.is_test_period(time_slot):
                    continue
                
                for class_ref in school.get_all_classes():
                    # 特別な空きコマはスキップ
                    if self._should_skip_slot(time_slot, class_ref):
                        continue
                    
                    # 既に割り当てがある場合はスキップ
                    if schedule.get_assignment(time_slot, class_ref):
                        continue
                    
                    # ロックされている場合はスキップ
                    if schedule.is_locked(time_slot, class_ref):
                        continue
                    
                    # 5組の水曜4限は最優先
                    if class_ref in self.grade5_classes and day == "水" and period == 4:
                        grade5_wed4_slots.append((time_slot, class_ref))
                    # 3年生の6限は優先度を高くする
                    elif class_ref.grade == 3 and period == 6 and day in ["月", "火", "水"]:
                        priority_slots.append((time_slot, class_ref))
                    else:
                        empty_slots.append((time_slot, class_ref))
        
        # 各グループをシャッフル
        random.shuffle(grade5_wed4_slots)
        random.shuffle(priority_slots)
        random.shuffle(empty_slots)
        
        # 優先順位: 5組水曜4限 > 3年生6限 > その他
        return grade5_wed4_slots + priority_slots + empty_slots
    
    def _should_skip_slot(self, time_slot: TimeSlot, class_ref: ClassReference) -> bool:
        """このスロットをスキップすべきかチェック
        
        QA.txtから読み込んだ6限目ルールに基づいて判定します。
        """
        # 6限目ルールが設定されている場合
        if hasattr(self, 'sixth_period_rules') and self.sixth_period_rules:
            grade_rules = self.sixth_period_rules.get(class_ref.grade, {})
            if time_slot.period == 6 and time_slot.day in grade_rules:
                rule = grade_rules[time_slot.day]
                # 'normal'（通常授業）以外はスキップ
                return rule != 'normal'
        
        # デフォルトルール（フォールバック）
        # 3年生の特別ルール：月曜・火曜・水曜の6限は授業可能
        if class_ref.grade == 3:
            # 金曜6限のYTのみスキップ
            if time_slot.day == "金" and time_slot.period == 6:
                return True
            # 月曜・火曜・水曜の6限は授業可能なのでスキップしない
            return False
        
        # 1・2年生のルール
        # 月曜6限（欠）- 全学年共通だが3年生は例外
        if time_slot.day == "月" and time_slot.period == 6:
            return True
        
        # 1・2年生は火曜・水曜・金曜の6限をスキップ（YT）
        if ((time_slot.day == "火" and time_slot.period == 6) or
            (time_slot.day == "水" and time_slot.period == 6) or
            (time_slot.day == "金" and time_slot.period == 6)):
            return True
        
        return False
    
    def _get_shortage_subjects_prioritized(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference
    ) -> Dict[Subject, int]:
        """優先度を考慮した科目を取得（標準時数を超えても配置可能）"""
        base_hours = school.get_all_standard_hours(class_ref)
        
        # 現在の割り当て数をカウント
        current_hours = defaultdict(int)
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject:
                    current_hours[assignment.subject] += 1
        
        # 全ての教科を標準時数順（多い順）でソート
        all_subjects = {}
        for subject, required in sorted(base_hours.items(), key=lambda x: x[1], reverse=True):
            # 固定科目はスキップ
            if ScheduleUtils.is_fixed_subject(subject.name):
                continue
            
            # 標準時数を基準に優先度を設定（不足していなくても含める）
            current = current_hours.get(subject, 0)
            # 優先度スコア = 標準時数 - 現在の配置数（負の値でも含める）
            priority_score = required - current
            all_subjects[subject] = priority_score
        
        # 主要教科を最優先、その後は標準時数順
        prioritized = {}
        
        # まず主要教科（標準時数順）
        priority_subjects = getattr(self, 'priority_subjects', ["算", "国", "理", "社", "英", "数"])
        for subject, score in sorted(all_subjects.items(), key=lambda x: base_hours.get(x[0], 0), reverse=True):
            if subject.name in priority_subjects:
                prioritized[subject] = score
        
        # 次にその他の教科（標準時数順）
        for subject, score in sorted(all_subjects.items(), key=lambda x: base_hours.get(x[0], 0), reverse=True):
            if subject not in prioritized:
                prioritized[subject] = score
        
        return prioritized
    
    def _get_shortage_subjects(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference
    ) -> Dict[Subject, int]:
        """不足している科目とその時数を取得"""
        base_hours = school.get_all_standard_hours(class_ref)
        
        # 現在の割り当て数をカウント
        current_hours = defaultdict(int)
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject:
                    current_hours[assignment.subject] += 1
        
        shortage = {}
        for subject, required in base_hours.items():
            # 固定科目はスキップ
            if ScheduleUtils.is_fixed_subject(subject.name):
                continue
                
            current = current_hours.get(subject, 0)
            if current < required:
                shortage[subject] = required - current
        
        return shortage
    
    def _calculate_teacher_loads(self, schedule: Schedule, school: School) -> Dict[str, int]:
        """各教師の現在の負担を計算"""
        loads = defaultdict(int)
        
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        loads[assignment.teacher.name] += 1
        
        return dict(loads)
    
    def _get_grade5_teacher(self, school: School, subject: Subject) -> Optional[Teacher]:
        """5組の教科を担当できる教師を取得"""
        # 5組の代表クラスとして1年5組を使用
        from ...utils import parse_class_reference
        class_ref = parse_class_reference("1年5組")
        
        # Grade5TeacherSelectorに委譲
        return self.grade5_teacher_selector.select_teacher(school, subject, class_ref)
    
    def _get_homeroom_teacher(self, class_ref: ClassReference) -> Optional[str]:
        """担任教師の名前を取得
        
        QA.txtから読み込んだルールを使用するため、
        初期化時に担任教師マッピングを注入する必要があります。
        """
        # 初期化時に設定されたマッピングから取得
        if hasattr(self, 'homeroom_teachers'):
            return self.homeroom_teachers.get(class_ref.full_name)
        
        # マッピングが設定されていない場合はNone
        return None
    
    def _log_statistics(self) -> None:
        """統計情報をログ出力"""
        self.logger.info("\n=== 空きコマ埋め統計 ===")
        for key, value in sorted(self.stats.items()):
            self.logger.info(f"{key}: {value}")
    
    def _record_unfilled_slot(self, slot_id: str, reasons: List[str]):
        """未配置スロットとその理由を記録"""
        self.unfilled_slots[slot_id] = reasons
    
    def get_unfilled_slots_report(self) -> str:
        """未配置スロットの詳細レポートを生成"""
        if not self.unfilled_slots:
            return "全ての空きスロットが埋まりました。"
        
        report = ["\n=== 未配置スロットの詳細 ===\n"]
        
        # 理由別に集計
        reason_counts = defaultdict(int)
        teacher_absence_slots = []
        
        for slot_id, reasons in sorted(self.unfilled_slots.items()):
            report.append(f"\n{slot_id}:")
            for reason in reasons:
                report.append(f"  - {reason}")
                
                # 教師不在を特別に記録
                if "不在" in reason or "研修" in reason or "年休" in reason:
                    teacher_absence_slots.append((slot_id, reason))
                    reason_counts["教師不在"] += 1
                elif "日内重複" in reason:
                    reason_counts["日内重複制約"] += 1
                elif "標準時数" in reason:
                    reason_counts["標準時数達成"] += 1
                elif "担当教師未設定" in reason:
                    reason_counts["教師未割当"] += 1
                else:
                    reason_counts["その他の制約"] += 1
        
        # サマリー
        report.append("\n\n=== サマリー ===")
        report.append(f"未配置スロット総数: {len(self.unfilled_slots)}")
        report.append("\n理由別内訳:")
        for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
            report.append(f"  {reason}: {count}件")
        
        # 教師不在による未配置を強調
        if teacher_absence_slots:
            report.append("\n\n=== 教師不在による未配置（物理的制約） ===")
            for slot_id, reason in teacher_absence_slots:
                report.append(f"  {slot_id}: {reason}")
        
        return "\n".join(report)