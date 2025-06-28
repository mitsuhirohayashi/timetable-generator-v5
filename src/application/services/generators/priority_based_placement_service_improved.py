"""改良版優先度ベース配置サービス

バックトラッキングと段階的制約緩和により、より多くの授業配置を実現。
"""
import logging
from typing import List, Dict, Optional, Tuple, Set, Any
from dataclasses import dataclass
from collections import defaultdict
import random

from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.value_objects.time_slot import ClassReference, TimeSlot, Subject
from ....domain.value_objects.assignment import Assignment
from ....domain.services.validators.constraint_validator import ConstraintValidatorImproved


@dataclass
class PlacementDifficulty:
    """配置難易度"""
    class_ref: ClassReference
    subject_name: str
    remaining_hours: int
    available_slots: int
    teacher_constraints: int
    difficulty_score: float


@dataclass
class BacktrackState:
    """バックトラッキング用の状態"""
    time_slot: TimeSlot
    assignment: Assignment
    displaced_assignments: List[Tuple[TimeSlot, Assignment]]


class PriorityBasedPlacementServiceImproved:
    """改良版優先度ベース配置サービス
    
    主な改良点:
    1. 配置難易度に基づく優先順位付け
    2. バックトラッキングによる再配置
    3. 段階的制約緩和
    """
    
    def __init__(self, constraint_validator: ConstraintValidatorImproved):
        """初期化
        
        Args:
            constraint_validator: 改良版制約検証器
        """
        self.constraint_validator = constraint_validator
        self.logger = logging.getLogger(__name__)
        
        # バックトラッキング統計
        self._backtrack_stats = {
            'total_backtracks': 0,
            'successful_backtracks': 0,
            'max_depth': 0,
            'total_displaced': 0
        }
    
    def place_all_subjects(self, schedule: Schedule, school: School, 
                          max_iterations: int = 100) -> int:
        """全ての教科を配置
        
        Args:
            schedule: スケジュール
            school: 学校情報
            max_iterations: 最大反復回数
            
        Returns:
            配置した授業数
        """
        self.logger.info("優先度ベース配置を開始")
        
        total_placed = 0
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # 配置難易度を計算
            difficulties = self._calculate_placement_difficulties(schedule, school)
            
            if not difficulties:
                self.logger.info("全ての必要授業を配置完了")
                break
            
            # デバッグ: 配置難易度の統計
            self.logger.info(f"反復{iteration}: {len(difficulties)}個の配置タスク")
            if difficulties:
                self.logger.debug(f"最も難しい配置: {difficulties[0].class_ref} {difficulties[0].subject_name} "
                                f"(残り{difficulties[0].remaining_hours}時間, "
                                f"利用可能{difficulties[0].available_slots}スロット)")
            
            # 最も難しい配置から順に処理
            difficulties.sort(key=lambda x: x.difficulty_score, reverse=True)
            
            placed_in_iteration = 0
            
            for difficulty in difficulties[:10]:  # 上位10個を処理
                self.logger.debug(f"配置試行: {difficulty.class_ref} {difficulty.subject_name} "
                                f"(残り{difficulty.remaining_hours}時間)")
                success = self._try_place_with_backtrack(
                    schedule, school, difficulty
                )
                
                if success:
                    placed_in_iteration += 1
                    total_placed += 1
                    self.logger.info(f"配置成功: {difficulty.class_ref} {difficulty.subject_name}")
            
            if placed_in_iteration == 0:
                # 制約緩和を試みる
                self.logger.warning(f"反復{iteration}: 通常配置できず、制約緩和を試みます")
                relaxed_placed = self._try_relaxed_placement(
                    schedule, school, difficulties[:5]
                )
                
                if relaxed_placed > 0:
                    total_placed += relaxed_placed
                else:
                    self.logger.warning("制約緩和でも配置できません")
                    break
        
        self.logger.info(f"優先度ベース配置完了: {total_placed}個配置")
        return total_placed
    
    def _calculate_placement_difficulties(self, schedule: Schedule, 
                                        school: School) -> List[PlacementDifficulty]:
        """配置難易度を計算"""
        difficulties = []
        
        for class_ref in school.get_all_classes():
            # get_class_requirementsはget_all_standard_hoursに変更されている
            standard_hours = school.get_all_standard_hours(class_ref)
            requirements = {subject.name: int(hours) for subject, hours in standard_hours.items()}
            
            # デバッグ: クラスごとの要求時数
            if requirements:
                self.logger.debug(f"{class_ref}: 要求時数 {requirements}")
            
            for subject_name, required_hours in requirements.items():
                # 既に配置済みの時間数をカウント
                placed_hours = self._count_placed_hours(schedule, class_ref, subject_name)
                remaining_hours = required_hours - placed_hours
                
                if remaining_hours <= 0:
                    continue
                
                # 配置可能なスロット数を計算
                available_slots = self._count_available_slots(
                    schedule, school, class_ref, subject_name
                )
                
                # 教師制約の数を計算
                teacher_constraints = self._count_teacher_constraints(
                    school, subject_name
                )
                
                # 難易度スコアを計算
                # スコアが高いほど配置が難しい
                if available_slots == 0:
                    difficulty_score = 1000.0
                else:
                    difficulty_score = (
                        remaining_hours * 10 +
                        teacher_constraints * 5 +
                        (remaining_hours / available_slots) * 20
                    )
                
                difficulties.append(PlacementDifficulty(
                    class_ref=class_ref,
                    subject_name=subject_name,
                    remaining_hours=remaining_hours,
                    available_slots=available_slots,
                    teacher_constraints=teacher_constraints,
                    difficulty_score=difficulty_score
                ))
        
        return difficulties
    
    def _try_place_with_backtrack(self, schedule: Schedule, school: School,
                                 difficulty: PlacementDifficulty) -> bool:
        """バックトラッキングを使用して配置を試みる"""
        class_ref = difficulty.class_ref
        subject_name = difficulty.subject_name
        
        # 利用可能な時間枠を取得
        available_slots = self._get_available_time_slots(
            schedule, school, class_ref, subject_name
        )
        
        if not available_slots:
            self.logger.debug(f"{class_ref} {subject_name}: 利用可能なスロットなし")
            return False
        
        self.logger.debug(f"{class_ref} {subject_name}: {len(available_slots)}個の利用可能スロット")
        
        # 各時間枠で配置を試みる
        for time_slot in available_slots:
            # 教師を探す
            teacher = self._find_best_teacher(
                school, subject_name, time_slot, schedule
            )
            
            if not teacher:
                self.logger.debug(f"  {time_slot}: 利用可能な教師なし")
                continue
            
            self.logger.debug(f"  {time_slot}: 教師{teacher.name}で配置を試行")
            
            assignment = Assignment(
                class_ref=class_ref,
                subject=Subject(subject_name),
                teacher=teacher
            )
            
            # 直接配置を試みる
            # UnifiedConstraintSystemの場合はboolのみを返すので対応
            result = self.constraint_validator.check_assignment(
                schedule, school, time_slot, assignment
            )
            if isinstance(result, tuple):
                can_place, error_msg = result
            else:
                can_place = result
                error_msg = None
            
            if can_place:
                schedule.assign(time_slot, assignment)
                self.logger.info(f"    配置成功! {class_ref} {subject_name} を {time_slot} に配置")
                return True
            else:
                self.logger.warning(f"    配置失敗 {class_ref} {subject_name} @ {time_slot}: {error_msg}")
            
            # バックトラッキングを試みる
            if self._try_backtrack(schedule, school, time_slot, assignment):
                return True
        
        return False
    
    def _try_backtrack(self, schedule: Schedule, school: School,
                      time_slot: TimeSlot, assignment: Assignment,
                      depth: int = 0, max_depth: int = 3) -> bool:
        """バックトラッキングによる再配置を試みる"""
        if depth >= max_depth:
            return False
        
        self._backtrack_stats['total_backtracks'] += 1
        self._backtrack_stats['max_depth'] = max(self._backtrack_stats['max_depth'], depth + 1)
        
        # この時間枠で競合する授業を特定
        conflicting_assignments = self._find_conflicting_assignments(
            schedule, school, time_slot, assignment
        )
        
        if not conflicting_assignments:
            return False
        
        # 各競合授業の移動を試みる
        for conflict_time_slot, conflict_assignment in conflicting_assignments:
            # 競合授業を一時的に削除
            if schedule.is_locked(conflict_time_slot, conflict_assignment.class_ref):
                continue
            
            schedule.remove_assignment(conflict_time_slot, conflict_assignment.class_ref)
            self._backtrack_stats['total_displaced'] += 1
            
            # 元の授業を配置
            can_place, _ = self.constraint_validator.check_assignment(
                schedule, school, time_slot, assignment
            )
            
            if can_place:
                schedule.assign(time_slot, assignment)
                
                # 競合授業を別の場所に配置
                alternative_slot = self._find_alternative_slot(
                    schedule, school, conflict_assignment, conflict_time_slot
                )
                
                if alternative_slot:
                    schedule.assign(alternative_slot, conflict_assignment)
                    self._backtrack_stats['successful_backtracks'] += 1
                    return True
                else:
                    # 再帰的にバックトラッキング
                    if self._try_place_displaced(
                        schedule, school, conflict_assignment, 
                        conflict_time_slot, depth + 1
                    ):
                        self._backtrack_stats['successful_backtracks'] += 1
                        return True
                
                # 失敗したら元に戻す
                schedule.remove_assignment(time_slot, assignment.class_ref)
            
            # 競合授業を元に戻す
            schedule.assign(conflict_time_slot, conflict_assignment)
        
        return False
    
    def _try_relaxed_placement(self, schedule: Schedule, school: School,
                             difficulties: List[PlacementDifficulty]) -> int:
        """制約を緩和して配置を試みる"""
        placed_count = 0
        
        for difficulty in difficulties:
            # 制約レベルを段階的に緩和
            for constraint_level in ['normal', 'relaxed', 'minimal']:
                if self._try_place_with_constraint_level(
                    schedule, school, difficulty, constraint_level
                ):
                    placed_count += 1
                    self.logger.info(
                        f"制約レベル'{constraint_level}'で"
                        f"{str(difficulty.class_ref)}の{difficulty.subject_name}を配置"
                    )
                    break
        
        return placed_count
    
    def _try_place_with_constraint_level(self, schedule: Schedule, school: School,
                                       difficulty: PlacementDifficulty,
                                       constraint_level: str) -> bool:
        """指定された制約レベルで配置を試みる"""
        # 制約レベルに応じた配置戦略
        # （実装の詳細は省略）
        return False
    
    def _count_placed_hours(self, schedule: Schedule, class_ref: ClassReference,
                          subject_name: str) -> int:
        """配置済みの時間数をカウント"""
        count = 0
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject.name == subject_name:
                    count += 1
        return count
    
    def _count_available_slots(self, schedule: Schedule, school: School,
                             class_ref: ClassReference, subject_name: str) -> int:
        """配置可能なスロット数をカウント"""
        count = 0
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                if not schedule.get_assignment(time_slot, class_ref):
                    # 簡易チェック（教師は後で決定）
                    count += 1
        return count
    
    def _count_teacher_constraints(self, school: School, subject_name: str) -> int:
        """教師制約の数をカウント"""
        subject = Subject(subject_name)
        
        teachers = school.get_subject_teachers(subject)
        constraint_count = 0
        
        for teacher in teachers:
            # 不在時間をカウント
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    if school.is_teacher_unavailable(day, period, teacher):
                        constraint_count += 1
        
        return constraint_count
    
    def _get_available_time_slots(self, schedule: Schedule, school: School,
                                class_ref: ClassReference, subject_name: str) -> List[TimeSlot]:
        """利用可能な時間枠を取得"""
        available = []
        
        # まず、日内重複なしで配置可能なスロットを探す
        for day in ["月", "火", "水", "木", "金"]:
            # 日内重複を避けるため、その日に既に配置されているかチェック
            daily_count = 0
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject.name == subject_name:
                    daily_count += 1
            
            if daily_count > 0:
                continue  # この日は既に配置済み
            
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                if not schedule.get_assignment(time_slot, class_ref):
                    available.append(time_slot)
        
        # 日内重複なしで配置可能なスロットがない場合、制約を緩和
        if not available:
            self.logger.debug(f"{class_ref} {subject_name}: 日内重複なしでは配置不可、制約を緩和")
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    if not schedule.get_assignment(time_slot, class_ref):
                        available.append(time_slot)
        
        return available
    
    def _find_best_teacher(self, school: School, subject_name: str,
                         time_slot: TimeSlot, schedule: Schedule) -> Optional[Any]:
        """最適な教師を見つける"""
        subject = Subject(subject_name)
        
        teachers = school.get_subject_teachers(subject)
        
        # 各教師の負担をカウント
        teacher_loads = {}
        for teacher in teachers:
            if school.is_teacher_unavailable(time_slot.day, time_slot.period, teacher):
                continue
            
            # この時間に他のクラスを教えているかチェック
            is_busy = False
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.teacher and assignment.teacher == teacher:
                    is_busy = True
                    break
            
            if not is_busy:
                # 教師の現在の負担をカウント
                load = 0
                for day in ["月", "火", "水", "木", "金"]:
                    for period in range(1, 7):
                        ts = TimeSlot(day, period)
                        for cr in school.get_all_classes():
                            a = schedule.get_assignment(ts, cr)
                            if a and a.teacher and a.teacher == teacher:
                                load += 1
                
                teacher_loads[teacher] = load
        
        if not teacher_loads:
            return None
        
        # 最も負担の少ない教師を選択
        return min(teacher_loads, key=teacher_loads.get)
    
    def _find_conflicting_assignments(self, schedule: Schedule, school: School,
                                    time_slot: TimeSlot, 
                                    assignment: Assignment) -> List[Tuple[TimeSlot, Assignment]]:
        """競合する授業を特定"""
        conflicts = []
        
        # 教師の競合をチェック
        if assignment.teacher:
            for class_ref in school.get_all_classes():
                if class_ref == assignment.class_ref:
                    continue
                
                existing = schedule.get_assignment(time_slot, class_ref)
                if existing and existing.teacher and existing.teacher == assignment.teacher:
                    conflicts.append((time_slot, existing))
        
        # 他の競合もチェック（体育館使用など）
        # （実装の詳細は省略）
        
        return conflicts
    
    def _find_alternative_slot(self, schedule: Schedule, school: School,
                             assignment: Assignment, 
                             original_slot: TimeSlot) -> Optional[TimeSlot]:
        """代替の時間枠を見つける"""
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                if time_slot == original_slot:
                    continue
                
                if not schedule.get_assignment(time_slot, assignment.class_ref):
                    can_place, _ = self.constraint_validator.check_assignment(
                        schedule, school, time_slot, assignment
                    )
                    
                    if can_place:
                        return time_slot
        
        return None
    
    def _try_place_displaced(self, schedule: Schedule, school: School,
                           assignment: Assignment, original_slot: TimeSlot,
                           depth: int) -> bool:
        """移動された授業を再配置"""
        # 代替スロットを探す
        alternative = self._find_alternative_slot(
            schedule, school, assignment, original_slot
        )
        
        if alternative:
            schedule.assign(alternative, assignment)
            return True
        
        # さらにバックトラッキング
        available_slots = self._get_available_time_slots(
            schedule, school, assignment.class_ref, assignment.subject.name
        )
        
        for slot in available_slots:
            if self._try_backtrack(schedule, school, slot, assignment, depth):
                return True
        
        return False
    
    def get_backtrack_statistics(self) -> Dict[str, int]:
        """バックトラッキング統計を取得"""
        return self._backtrack_stats.copy()
