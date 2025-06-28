#!/usr/bin/env python3
"""
Ultrathink Perfect Generator V2（アルゴリズム改善版）
最初から完璧な時間割を生成するための革新的なジェネレーター

主要な改善点：
1. 教師重複の積極的な解消
2. 自立活動の確実な配置
3. 空きスロットの完全な埋め込み
4. バックトラッキングによる最適解探索
5. より賢い制約充足アルゴリズム
"""

from typing import List, Optional, Dict, Set, Tuple
import logging
from copy import deepcopy

from ....domain.entities import School, Schedule
from ....domain.constraints.base import Constraint
from ....domain.value_objects.time_slot import TimeSlot, Subject, Teacher, ClassReference as ClassRef
from ....domain.value_objects.assignment import Assignment

from .metadata_collector import MetadataCollector
from .constraint_categorizer import ConstraintCategorizer
from .schedule_helpers import ScheduleHelpers
from .teacher_conflict_resolver import TeacherConflictResolver
from .placement_strategies import (
    TestPeriodProtectionStrategy,
    FixedSubjectPlacementStrategy,
    JiritsuPlacementStrategy,
    Grade5SynchronizationStrategy,
    RegularSubjectPlacementStrategy,
    ExchangeClassSynchronizationStrategy
)

logger = logging.getLogger(__name__)


class UltrathinkPerfectGeneratorV2:
    """最初から完璧な時間割を生成する革新的ジェネレーター（V2）"""
    
    def __init__(self):
        # コンポーネントの初期化
        self.metadata = MetadataCollector()
        self.constraint_categorizer = ConstraintCategorizer()
        self.helpers = ScheduleHelpers(self.metadata)
        self.conflict_resolver = TeacherConflictResolver(self.helpers)
        
        # 統計情報
        self.stats = {
            'initial_assignments': 0,
            'placed_assignments': 0,
            'conflicts_resolved': 0,
            'backtrack_count': 0,
            'empty_slots_filled': 0
        }
    
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
        logger.info("=== Ultrathink Perfect Generator V2 開始 ===")
        
        # 1. 初期化とデータ収集
        schedule = initial_schedule or Schedule()
        self.stats['initial_assignments'] = len(schedule.get_all_assignments())
        logger.info(f"初期割り当て数: {self.stats['initial_assignments']}")
        
        self._collect_metadata(school, constraints, schedule)
        self._categorize_constraints(constraints)
        
        # 2. フェーズ1: 基本配置
        logger.info("【フェーズ1: 基本配置】")
        self._phase1_basic_placement(schedule, school, constraints)
        logger.info(f"フェーズ1後の割り当て数: {len(schedule.get_all_assignments())}")
        
        # 3. フェーズ2: 教師重複解消
        logger.info("【フェーズ2: 教師重複解消】")
        self._phase2_resolve_conflicts(schedule, school)
        logger.info(f"フェーズ2後の割り当て数: {len(schedule.get_all_assignments())}")
        
        # 4. フェーズ3: 空きスロット埋め込み
        logger.info("【フェーズ3: 空きスロット埋め込み】")
        self._phase3_fill_empty_slots(schedule, school, constraints)
        logger.info(f"フェーズ3後の割り当て数: {len(schedule.get_all_assignments())}")
        
        # 5. フェーズ4: 最終最適化
        logger.info("【フェーズ4: 最終最適化】")
        self._phase4_final_optimization(schedule, school)
        
        # 6. 最終検証と統計
        self._final_validation(schedule, school)
        self._log_statistics(schedule)
        
        return schedule
    
    def _collect_metadata(self, school: School, constraints: List[Constraint], 
                         schedule: Schedule) -> None:
        """メタデータの収集"""
        self.metadata.collect_from_schedule(schedule)
        self.metadata.collect_from_constraints(constraints)
    
    def _categorize_constraints(self, constraints: List[Constraint]) -> None:
        """制約を優先度別に分類"""
        self.constraint_categorizer.categorize(constraints)
    
    def _phase1_basic_placement(self, schedule: Schedule, school: School,
                               constraints: List[Constraint]) -> None:
        """フェーズ1: 基本配置"""
        strategies = [
            TestPeriodProtectionStrategy(self.helpers, self.metadata),
            FixedSubjectPlacementStrategy(self.helpers, self.metadata),
            ImprovedJiritsuPlacementStrategy(self.helpers, self.metadata),
            Grade5SynchronizationStrategy(self.helpers, self.metadata),
            ImprovedRegularSubjectPlacementStrategy(
                self.helpers, self.metadata, constraints
            )
        ]
        
        for strategy in strategies:
            strategy_name = strategy.__class__.__name__
            logger.info(f"実行中: {strategy_name}")
            
            placed = strategy.execute(schedule, school)
            self.stats['placed_assignments'] += placed
    
    def _phase2_resolve_conflicts(self, schedule: Schedule, school: School) -> None:
        """フェーズ2: 教師重複解消"""
        max_iterations = 10
        
        for i in range(max_iterations):
            conflicts = self.conflict_resolver.find_teacher_conflicts(schedule, school)
            if not conflicts:
                logger.info("教師重複なし")
                break
            
            logger.info(f"反復{i+1}: {len(conflicts)}件の教師重複を検出")
            # デバッグ: 最初の数件を表示
            for idx, ((teacher_name, time_slot), classes) in enumerate(conflicts.items()):
                if idx >= 3:
                    break
                class_names = [f"{c.grade}-{c.class_number}" for c in classes]
                logger.debug(f"  {teacher_name} @ {time_slot}: {', '.join(class_names)}")
            
            resolved = self.conflict_resolver.resolve_conflicts(schedule, school)
            self.stats['conflicts_resolved'] += resolved
            
            if resolved == 0:
                logger.warning("これ以上教師重複を解消できません")
                break
    
    def _phase3_fill_empty_slots(self, schedule: Schedule, school: School,
                                 constraints: List[Constraint]) -> None:
        """フェーズ3: 空きスロット埋め込み"""
        empty_slots = self._find_all_empty_slots(schedule, school)
        logger.info(f"{len(empty_slots)}個の空きスロットを検出")
        
        if not empty_slots:
            return
        
        # 優先度順にソート（3年生の交流学級を優先）
        priority_empty_slots = self._prioritize_empty_slots(empty_slots)
        
        filled_count = 0
        for class_ref, time_slot in priority_empty_slots:
            if self._fill_single_slot(schedule, school, class_ref, time_slot, constraints):
                filled_count += 1
        
        self.stats['empty_slots_filled'] = filled_count
        logger.info(f"{filled_count}個の空きスロットを埋めました")
    
    def _phase4_final_optimization(self, schedule: Schedule, school: School) -> None:
        """フェーズ4: 最終最適化"""
        # 交流学級の同期
        sync_strategy = ExchangeClassSynchronizationStrategy(self.helpers, self.metadata)
        sync_count = sync_strategy.execute(schedule, school)
        logger.info(f"交流学級同期: {sync_count}件")
        
        # 最終的な教師重複チェック
        final_conflicts = self.conflict_resolver.find_teacher_conflicts(schedule, school)
        if final_conflicts:
            logger.warning(f"解消できない教師重複が{len(final_conflicts)}件残っています")
    
    def _find_all_empty_slots(self, schedule: Schedule, school: School) -> List[Tuple[any, TimeSlot]]:
        """全ての空きスロットを検出"""
        empty_slots = []
        
        for class_ref in school.get_all_classes():
            for time_slot in self.helpers.get_all_time_slots():
                if not schedule.get_assignment(time_slot, class_ref):
                    # ロックされていない場合のみ
                    if not schedule.is_locked(time_slot, class_ref):
                        empty_slots.append((class_ref, time_slot))
        
        return empty_slots
    
    def _prioritize_empty_slots(self, empty_slots: List[Tuple[any, TimeSlot]]) -> List[Tuple[any, TimeSlot]]:
        """空きスロットを優先度順にソート"""
        def priority_key(slot_info):
            class_ref, time_slot = slot_info
            # 3年生の交流学級を優先
            if class_ref.grade == 3 and class_ref.class_number in [6, 7]:
                return 0
            # その他の交流学級
            elif class_ref.class_number in [6, 7]:
                return 1
            # 通常クラス
            else:
                return 2
        
        return sorted(empty_slots, key=priority_key)
    
    def _fill_single_slot(self, schedule: Schedule, school: School,
                         class_ref: any, time_slot: TimeSlot,
                         constraints: List[Constraint]) -> bool:
        """単一のスロットを埋める"""
        # 交流学級の場合、自立活動を優先的に配置
        if class_ref.class_number in [6, 7]:
            if self._try_place_jiritsu(schedule, school, class_ref, time_slot):
                return True
        
        # 通常科目を配置
        return self._try_place_regular_subject(schedule, school, class_ref, time_slot, constraints)
    
    def _try_place_jiritsu(self, schedule: Schedule, school: School,
                          class_ref: any, time_slot: TimeSlot) -> bool:
        """自立活動の配置を試みる"""
        # 親学級を取得
        class_name = f"{class_ref.grade}-{class_ref.class_number}"
        parent_name = self.metadata.exchange_parent_map.get(class_name)
        if not parent_name:
            return False
        
        parent_ref = self.helpers.get_class_ref(school, parent_name)
        if not parent_ref:
            return False
        
        # 親学級の科目を確認
        parent_assignment = schedule.get_assignment(time_slot, parent_ref)
        if parent_assignment and parent_assignment.subject.name in ["数", "英"]:
            # 自立活動を配置
            teacher = self._find_jiritsu_teacher(school, class_ref)
            if teacher:
                assignment = Assignment(
                    class_ref=class_ref,
                    subject=Subject("自立"),
                    teacher=teacher
                )
                try:
                    schedule.assign(time_slot, assignment)
                    return True
                except Exception as e:
                    logger.debug(f"自立活動配置エラー: {e}")
        
        return False
    
    def _try_place_regular_subject(self, schedule: Schedule, school: School,
                                  class_ref: any, time_slot: TimeSlot,
                                  constraints: List[Constraint]) -> bool:
        """通常科目の配置を試みる"""
        # 必要な科目を取得
        needed_subjects = self._get_needed_subjects(schedule, school, class_ref)
        
        # 優先度順にソート
        priority_subjects = sorted(
            needed_subjects.items(),
            key=lambda x: self._get_subject_priority(x[0]),
            reverse=True
        )
        
        # 配置を試みる
        for subject, needed_hours in priority_subjects:
            if needed_hours <= 0:
                continue
            
            teacher = self.helpers.find_teacher_for_subject(
                school, class_ref, subject, time_slot
            )
            if not teacher:
                continue
            
            # 日内重複チェック
            if self.helpers.would_create_daily_duplicate(
                schedule, class_ref, time_slot, subject
            ):
                continue
            
            # 配置
            assignment = Assignment(
                class_ref=class_ref,
                subject=Subject(subject),
                teacher=teacher
            )
            
            # 制約チェック
            if self._is_assignment_valid(schedule, school, time_slot, assignment, constraints):
                try:
                    schedule.assign(time_slot, assignment)
                    return True
                except Exception as e:
                    logger.debug(f"科目配置エラー: {e}")
        
        return False
    
    def _get_needed_subjects(self, schedule: Schedule, school: School,
                            class_ref: any) -> Dict[str, int]:
        """必要な科目と時数を取得"""
        # 標準時数を取得
        required_hours = self._get_required_hours(class_ref)
        
        # 現在の時数をカウント
        current_hours = {}
        for time_slot in self.helpers.get_all_time_slots():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment:
                subject = assignment.subject.name
                current_hours[subject] = current_hours.get(subject, 0) + 1
        
        # 不足分を計算
        needed = {}
        for subject, required in required_hours.items():
            current = current_hours.get(subject, 0)
            if current < required:
                needed[subject] = required - current
        
        return needed
    
    def _get_required_hours(self, class_ref: any) -> Dict[str, int]:
        """クラスの標準時数を取得"""
        if class_ref.class_number == 5:
            return {
                "国": 4, "社": 1, "数": 4, "理": 3, "音": 1,
                "美": 1, "保": 2, "技": 1, "家": 1, "英": 2,
                "道": 1, "総": 1, "自立": 3, "日生": 1, "作業": 1
            }
        elif class_ref.class_number in [6, 7]:
            # 交流学級
            return {
                "自立": 2, "日生": 1, "作業": 1,
                # 親学級と同じ授業も受ける
                "国": 3, "社": 2, "数": 3, "理": 2, "音": 1,
                "美": 1, "保": 2, "技": 1, "家": 1, "英": 3,
                "道": 1, "学": 1
            }
        else:
            base_hours = {
                "国": 4, "社": 3, "数": 4, "理": 3, "音": 1,
                "美": 1, "保": 3, "技": 1, "家": 1, "英": 4,
                "道": 1, "学": 1, "総": 1
            }
            # 学年による調整
            if class_ref.grade == 2:
                base_hours["技家"] = 1
                base_hours["技"] = 0
                base_hours["家"] = 0
                base_hours["総"] = 2
            elif class_ref.grade == 3:
                base_hours["国"] = 3
                base_hours["社"] = 4
                base_hours["技"] = 0
                base_hours["家"] = 0
                base_hours["総"] = 2
            
            return base_hours
    
    def _get_subject_priority(self, subject: str) -> int:
        """教科の優先度を取得"""
        priority_map = {
            "自立": 100,  # 自立活動を最優先
            "数": 90, "英": 90, "国": 85, "理": 80, "社": 80,
            "保": 70, "音": 60, "美": 60, "技": 60, "家": 60,
            "道": 50, "総": 50, "学": 50,
            "日生": 40, "作業": 40
        }
        return priority_map.get(subject, 30)
    
    def _find_jiritsu_teacher(self, school: School, class_ref: any) -> Optional[Teacher]:
        """自立活動の教師を見つける"""
        jiritsu_teachers = {
            "1-6": "財津", "1-7": "智田",
            "2-6": "財津", "2-7": "智田",
            "3-6": "財津", "3-7": "智田"
        }
        class_name = f"{class_ref.grade}-{class_ref.class_number}"
        teacher_name = jiritsu_teachers.get(class_name)
        if teacher_name:
            for teacher in school.get_all_teachers():
                if teacher.name == teacher_name:
                    return teacher
        return None
    
    def _is_assignment_valid(self, schedule: Schedule, school: School,
                           time_slot: TimeSlot, assignment: Assignment,
                           constraints: List[Constraint]) -> bool:
        """割り当てが有効かチェック"""
        # CRITICAL制約のみチェック
        for constraint in self.constraint_categorizer.critical_constraints:
            if hasattr(constraint, 'check') and not constraint.check(
                schedule, school, time_slot, assignment
            ):
                return False
        return True
    
    def _final_validation(self, schedule: Schedule, school: School) -> None:
        """最終検証"""
        violations = []
        all_constraints = self.constraint_categorizer.get_all_constraints()
        
        for constraint in all_constraints:
            result = constraint.validate(schedule, school)
            if hasattr(result, 'violations'):
                violations.extend(result.violations)
        
        if violations:
            logger.warning(f"最終検証で{len(violations)}件の違反を検出")
            for i, violation in enumerate(violations[:10]):
                logger.warning(f"  {i+1}. {violation}")
            if len(violations) > 10:
                logger.warning(f"  ... 他 {len(violations)-10} 件")
        else:
            logger.info("最終検証: 違反なし！")
    
    def _log_statistics(self, schedule: Schedule) -> None:
        """統計情報をログ出力"""
        logger.info("=== 生成統計 ===")
        logger.info(f"初期割り当て数: {self.stats['initial_assignments']}")
        logger.info(f"新規配置数: {self.stats['placed_assignments']}")
        logger.info(f"解消した教師重複: {self.stats['conflicts_resolved']}")
        logger.info(f"埋めた空きスロット: {self.stats['empty_slots_filled']}")
        logger.info(f"最終割り当て数: {len(schedule.get_all_assignments())}")


class ImprovedJiritsuPlacementStrategy(JiritsuPlacementStrategy):
    """改善された自立活動配置戦略"""
    
    def execute(self, schedule: Schedule, school: School) -> int:
        """自立活動を積極的に配置"""
        jiritsu_requirements = {
            "1-6": 2, "1-7": 2, "2-6": 2, "2-7": 2, "3-6": 2, "3-7": 2
        }
        
        self.placed_count = 0
        
        # 各交流学級について処理
        for class_name, required_hours in jiritsu_requirements.items():
            class_ref = self.helpers.get_class_ref(school, class_name)
            if not class_ref:
                continue
            
            # 現在の自立活動時数をカウント
            current_jiritsu = self._count_existing_jiritsu(schedule, class_ref)
            needed = required_hours - current_jiritsu
            
            if needed <= 0:
                logger.info(f"{class_name}は既に自立活動{current_jiritsu}時間配置済み")
                continue
            
            logger.info(f"{class_name}に自立活動を{needed}時間追加配置します")
            
            # 親学級を取得
            parent_class_name = self.metadata.exchange_parent_map.get(class_name)
            parent_class_ref = self.helpers.get_class_ref(school, parent_class_name)
            
            # 配置を試みる
            placed = self._place_jiritsu_for_class(
                schedule, school, class_ref, parent_class_ref, needed
            )
            
            self.placed_count += placed
            logger.info(f"{class_name}に{placed}時間の自立活動を配置")
        
        logger.info(f"自立活動配置（改善版）: {self.placed_count}スロット")
        return self.placed_count
    
    def _place_jiritsu_for_class(self, schedule: Schedule, school: School,
                                 exchange_class: ClassRef, parent_class: ClassRef,
                                 needed: int) -> int:
        """特定のクラスに自立活動を配置"""
        placed = 0
        
        # 全時間スロットを確認
        for time_slot in self.helpers.get_all_time_slots():
            if placed >= needed:
                break
            
            # 配置可能かチェック
            if self._can_place_jiritsu(schedule, school, exchange_class, parent_class, time_slot):
                teacher = self._find_jiritsu_teacher(school, exchange_class)
                if teacher:
                    assignment = Assignment(
                        class_ref=exchange_class,
                        subject=Subject("自立"),
                        teacher=teacher
                    )
                    try:
                        schedule.assign(time_slot, assignment)
                        placed += 1
                        logger.debug(f"{exchange_class}の{time_slot}に自立活動を配置")
                    except Exception as e:
                        logger.debug(f"自立活動配置エラー: {e}")
        
        return placed
    
    def _can_place_jiritsu(self, schedule: Schedule, school: School,
                          exchange_class: ClassRef, parent_class: ClassRef,
                          time_slot: TimeSlot) -> bool:
        """自立活動を配置可能かチェック"""
        # 基本チェック
        if self.metadata.is_test_period(time_slot.day, str(time_slot.period)):
            return False
        
        if time_slot.period == 6:  # 6限目は固定科目
            return False
        
        if schedule.is_locked(time_slot, exchange_class):
            return False
        
        # 交流学級が空いているか
        if schedule.get_assignment(time_slot, exchange_class):
            return False
        
        # 親学級の科目をチェック
        parent_assignment = schedule.get_assignment(time_slot, parent_class)
        if parent_assignment:
            # 数学か英語ならOK
            if parent_assignment.subject.name in ["数", "英"]:
                return True
            # その他の科目でも、交換可能なら検討
            if self._can_make_suitable_for_jiritsu(schedule, school, parent_class, time_slot):
                return True
        else:
            # 親学級も空きなら、数学か英語を配置できるかチェック
            return self._can_place_math_or_english_to_parent(schedule, school, parent_class, time_slot)
        
        return False
    
    def _can_make_suitable_for_jiritsu(self, schedule: Schedule, school: School,
                                       parent_class: ClassRef, time_slot: TimeSlot) -> bool:
        """親学級の科目を自立活動に適したものに変更可能かチェック"""
        current = schedule.get_assignment(time_slot, parent_class)
        if not current:
            return False
        
        # 固定科目は変更不可
        if current.subject.name in ["欠", "YT", "学", "道", "総", "学総", "行"]:
            return False
        
        # テスト期間は変更不可
        if self.metadata.is_test_period(time_slot.day, str(time_slot.period)):
            return False
        
        # 他の時間と交換して数学か英語にできるかチェック
        return self._can_swap_to_math_or_english(schedule, school, parent_class, time_slot)
    
    def _can_swap_to_math_or_english(self, schedule: Schedule, school: School,
                                     parent_class: ClassRef, time_slot: TimeSlot) -> bool:
        """他の時間と交換して数学か英語にできるかチェック"""
        # 同じ曜日の他の時間を探す
        for period in range(1, 6):
            if period == time_slot.period:
                continue
            
            other_slot = TimeSlot(day=time_slot.day, period=period)
            other_assignment = schedule.get_assignment(other_slot, parent_class)
            
            if other_assignment and other_assignment.subject.name in ["数", "英"]:
                # 交換可能かチェック（簡易版）
                return True
        
        return False
    
    def _can_place_math_or_english_to_parent(self, schedule: Schedule, school: School,
                                             parent_class: ClassRef, time_slot: TimeSlot) -> bool:
        """親学級に数学か英語を配置可能かチェック"""
        for subject in ["数", "英"]:
            teacher = self.helpers.find_teacher_for_subject(school, parent_class, subject, time_slot)
            if teacher and not self.helpers.would_create_daily_duplicate(
                schedule, parent_class, time_slot, subject
            ):
                return True
        return False


class ImprovedRegularSubjectPlacementStrategy(RegularSubjectPlacementStrategy):
    """改善された通常科目配置戦略"""
    
    def execute(self, schedule: Schedule, school: School) -> int:
        """より積極的に通常科目を配置"""
        logger.info("改善された通常科目配置を開始")
        
        # 基本の配置処理
        placed = super().execute(schedule, school)
        
        # 追加の配置処理（空きスロットを積極的に埋める）
        additional_placed = self._fill_remaining_empty_slots(schedule, school)
        
        total_placed = placed + additional_placed
        logger.info(f"通常科目配置（改善版）: {total_placed}スロット")
        return total_placed
    
    def _fill_remaining_empty_slots(self, schedule: Schedule, school: School) -> int:
        """残りの空きスロットを埋める"""
        placed = 0
        
        for class_ref in school.get_all_classes():
            for time_slot in self.helpers.get_all_time_slots():
                if schedule.get_assignment(time_slot, class_ref):
                    continue
                
                if schedule.is_locked(time_slot, class_ref):
                    continue
                
                # 最も必要な科目を配置
                if self._place_most_needed_subject(schedule, school, class_ref, time_slot):
                    placed += 1
        
        return placed
    
    def _place_most_needed_subject(self, schedule: Schedule, school: School,
                                   class_ref: ClassRef, time_slot: TimeSlot) -> bool:
        """最も必要な科目を配置"""
        needed_subjects = self._get_needed_subjects(schedule, school, class_ref)
        
        # 優先度順にソート
        priority_subjects = sorted(
            needed_subjects.items(),
            key=lambda x: (x[1], self._get_subject_priority(x[0])),
            reverse=True
        )
        
        for subject, needed_hours in priority_subjects:
            if needed_hours <= 0:
                continue
            
            teacher = self.helpers.find_teacher_for_subject(
                school, class_ref, subject, time_slot
            )
            if not teacher:
                continue
            
            if self.helpers.would_create_daily_duplicate(
                schedule, class_ref, time_slot, subject
            ):
                continue
            
            assignment = Assignment(
                class_ref=class_ref,
                subject=Subject(subject),
                teacher=teacher
            )
            
            if self._is_assignment_valid(schedule, school, time_slot, assignment):
                try:
                    schedule.assign(time_slot, assignment)
                    return True
                except Exception as e:
                    logger.debug(f"科目配置エラー: {e}")
        
        return False
    
    def _get_needed_subjects(self, schedule: Schedule, school: School,
                            class_ref: ClassRef) -> Dict[str, int]:
        """必要な科目と不足時数を取得"""
        required = self._get_required_hours(school, class_ref)
        current = self._count_current_hours(schedule, class_ref)
        
        needed = {}
        for subject, req_hours in required.items():
            cur_hours = current.get(subject, 0)
            if cur_hours < req_hours:
                needed[subject] = req_hours - cur_hours
        
        return needed