"""統一ハイブリッド生成戦略 V3

日内重複を防ぐため、全フェーズで共有される日内科目追跡システムを実装。
"""
import logging
from typing import Optional, Dict, List, Set, Tuple, TYPE_CHECKING
from collections import defaultdict
from dataclasses import dataclass
import random

from .base_generation_strategy import BaseGenerationStrategy

if TYPE_CHECKING:
    from ....domain.entities.schedule import Schedule
    from ....domain.entities.school import School
    from ....domain.value_objects.time_slot import TimeSlot, ClassReference
    from ....domain.value_objects.assignment import Assignment
    from ....domain.entities.teacher import Teacher


@dataclass
class TeacherScheduleSlot:
    """教師のスケジュールスロット"""
    is_available: bool = True
    assigned_class: Optional[str] = None
    subject: Optional[str] = None
    is_joint_class: bool = False  # 5組合同授業フラグ


class TeacherScheduleTracker:
    """教師スケジュール追跡システム（改良版）"""
    
    def __init__(self):
        # 教師名 -> 曜日 -> 時限 -> TeacherScheduleSlot
        self.schedules: Dict[str, Dict[str, Dict[int, TeacherScheduleSlot]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(TeacherScheduleSlot))
        )
        self.logger = logging.getLogger(__name__)
        
    def mark_unavailable(self, teacher: str, day: str, period: int, assigned_class: str, subject: str, is_joint: bool = False):
        """教師の時間を使用済みにマーク"""
        if not is_joint or not self.schedules[teacher][day][period].is_available:
            # 非合同授業または既に使用済みの場合
            self.schedules[teacher][day][period] = TeacherScheduleSlot(
                is_available=False,
                assigned_class=assigned_class,
                subject=subject,
                is_joint_class=is_joint
            )
        
    def is_available(self, teacher: str, day: str, period: int, is_joint: bool = False) -> bool:
        """教師が利用可能か確認"""
        slot = self.schedules[teacher][day][period]
        if slot.is_available:
            return True
        # 既に使用済みでも、両方が合同授業なら可
        if is_joint and slot.is_joint_class:
            return True
        return False
        
    def get_conflicts(self) -> List[Tuple[str, str, int, List[str]]]:
        """教師の重複を検出（合同授業と交流学級ペアを除外）"""
        conflicts = []
        
        # 交流学級と親学級のマッピング
        exchange_parent_map = {
            "1年6組": "1年1組", "1年7組": "1年2組",
            "2年6組": "2年3組", "2年7組": "2年2組",
            "3年6組": "3年3組", "3年7組": "3年2組"
        }
        
        # 各教師の各時間をチェック
        for teacher, days in self.schedules.items():
            for day, periods in days.items():
                for period, slot in periods.items():
                    if not slot.is_available and not slot.is_joint_class:
                        # この教師・時間の全ての割り当てを収集
                        assignments_at_time = []
                        
                        # 全ての時間割を再チェック
                        for t, d in self.schedules.items():
                            if t == teacher and day in d and period in d[day]:
                                s = d[day][period]
                                if not s.is_available and s.assigned_class:
                                    assignments_at_time.append(s.assigned_class)
                        
                        # 重複があれば記録（交流学級ペアを除外）
                        unique_assignments = list(set(assignments_at_time))
                        if len(unique_assignments) > 1:
                            # 交流学級ペアかチェック
                            if len(unique_assignments) == 2:
                                class1, class2 = unique_assignments[0], unique_assignments[1]
                                if ((class1 in exchange_parent_map and exchange_parent_map[class1] == class2) or
                                    (class2 in exchange_parent_map and exchange_parent_map[class2] == class1)):
                                    continue  # 交流学級ペアは除外
                            
                            conflicts.append((teacher, day, period, unique_assignments))
        
        return conflicts


class DailySubjectTracker:
    """日内科目追跡システム（全フェーズで共有）"""
    
    def __init__(self):
        # (class_key, day) -> set of subjects
        self.daily_subjects: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
        
    def add_subject(self, class_key: str, day: str, subject: str):
        """科目を追加"""
        self.daily_subjects[(class_key, day)].add(subject)
        
    def has_subject(self, class_key: str, day: str, subject: str) -> bool:
        """その日に既に科目があるかチェック"""
        return subject in self.daily_subjects[(class_key, day)]
        
    def get_subjects(self, class_key: str, day: str) -> Set[str]:
        """その日の科目を取得"""
        return self.daily_subjects[(class_key, day)]
        
    def init_from_schedule(self, schedule: 'Schedule', school: 'School'):
        """既存のスケジュールから初期化"""
        days = ["月", "火", "水", "木", "金"]
        from ....domain.value_objects.time_slot import TimeSlot
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        class_key = f"{class_ref.grade}年{class_ref.class_number}組"
                        self.add_subject(class_key, day, assignment.subject.name)


class UnifiedHybridStrategyV3(BaseGenerationStrategy):
    """統一ハイブリッド生成戦略 V3 - 日内重複防止強化版"""
    
    def __init__(self, constraint_system: 'UnifiedConstraintSystem'):
        super().__init__(constraint_system)
        self.logger = logging.getLogger(__name__)
        self.teacher_tracker = TeacherScheduleTracker()
        self.daily_tracker = DailySubjectTracker()  # 全フェーズで共有
        
        # 交流学級と親学級のマッピング
        self.exchange_parent_map = {
            "1年6組": "1年1組",
            "1年7組": "1年2組",
            "2年6組": "2年3組",
            "2年7組": "2年2組",
            "3年6組": "3年3組",
            "3年7組": "3年2組"
        }
    
    def get_name(self) -> str:
        """戦略名を返す"""
        return "Unified Hybrid Strategy V3"
    
    def generate(
        self,
        school: 'School',
        initial_schedule: Optional['Schedule'] = None,
        max_iterations: int = 100,
        **kwargs
    ) -> 'Schedule':
        """時間割を生成"""
        self.logger.info("統一ハイブリッド戦略 V3 による時間割生成を開始")
        
        # scheduleを作成または使用
        schedule = initial_schedule if initial_schedule else school.create_empty_schedule()
        
        # schoolを保存（_get_teacher_for_subject_from_schoolで使用）
        self._school = school
        
        # 既存のスケジュールから初期化
        self._initialize_from_existing(schedule, school)
        
        # フェーズ1: 自立活動の配置
        jiritsu_placed = self._place_jiritsu_improved(schedule, school)
        self.logger.info(f"フェーズ1: {jiritsu_placed}個の自立活動を配置")
        
        # フェーズ2: 5組の同期処理
        grade5_synced = self._sync_grade5_classes(schedule, school)
        self.logger.info(f"フェーズ2: {grade5_synced}個の5組授業を同期")
        
        # フェーズ3: 体育の配置
        pe_placed = self._place_pe_carefully(schedule, school)
        self.logger.info(f"フェーズ3: {pe_placed}個の体育を配置")
        
        # フェーズ4: 主要教科の配置
        major_placed = self._place_major_subjects_improved(schedule, school)
        self.logger.info(f"フェーズ4: {major_placed}個の主要教科を配置")
        
        # フェーズ5: 技能教科の配置
        skill_placed = self._place_skill_subjects_improved(schedule, school)
        self.logger.info(f"フェーズ5: {skill_placed}個の技能教科を配置")
        
        # フェーズ6: 空きスロットの充填
        filled = self._fill_empty_slots(schedule, school)
        self.logger.info(f"フェーズ6: {filled}個の空きスロットを充填")
        
        # フェーズ7: 交流学級の同期
        exchange_synced = self._sync_exchange_classes(schedule, school)
        self.logger.info(f"フェーズ7: {exchange_synced}個の交流学級を同期")
        
        # フェーズ8: 最終最適化
        optimized = self._final_optimization_improved(schedule, school, 10)
        self.logger.info(f"フェーズ8: {optimized}回の最適化を実行")
        
        # 制約違反をチェック
        conflicts = self.teacher_tracker.get_conflicts()
        if conflicts:
            self.logger.warning(f"生成完了後も{len(conflicts)}個の教師重複が残存")
        
        return schedule
    
    def _initialize_from_existing(self, schedule: 'Schedule', school: 'School'):
        """既存のスケジュールから初期化"""
        days = ["月", "火", "水", "木", "金"]
        from ....domain.value_objects.time_slot import TimeSlot
        
        # 日内科目トラッカーを初期化
        self.daily_tracker.init_from_schedule(schedule, school)
        
        # 教師スケジュールトラッカーを初期化
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        # 5組合同授業かチェック
                        is_joint = class_ref.class_number == 5
                        
                        self.teacher_tracker.mark_unavailable(
                            assignment.teacher.name,
                            day,
                            period,
                            str(class_ref),
                            assignment.subject.name,
                            is_joint
                        )
    
    def _place_jiritsu_improved(self, schedule: 'Schedule', school: 'School') -> int:
        """自立活動を配置（改良版）"""
        placed = 0
        days = ["月", "火", "水", "木", "金"]
        periods = [1, 2, 3, 4, 5]  # 6限は除外
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        from ....domain.value_objects.assignment import Assignment
        from ....domain.value_objects.time_slot import Subject
        
        # 各交流学級の自立活動時数を追跡
        jiritsu_hours = defaultdict(int)
        target_hours = 2  # 週2時間
        
        for exchange_class, parent_class in self.exchange_parent_map.items():
            # 既に十分な自立活動があるかチェック
            if jiritsu_hours[exchange_class] >= target_hours:
                continue
            
            # クラス参照を作成
            exchange_parts = exchange_class.split("年")
            exchange_grade = int(exchange_parts[0])
            exchange_num = int(exchange_parts[1].replace("組", ""))
            exchange_ref = ClassReference(exchange_grade, exchange_num)
            
            parent_parts = parent_class.split("年")
            parent_grade = int(parent_parts[0])
            parent_num = int(parent_parts[1].replace("組", ""))
            parent_ref = ClassReference(parent_grade, parent_num)
            
            # 配置可能な時間を探す
            for day in days:
                for period in periods:
                    if jiritsu_hours[exchange_class] >= target_hours:
                        break
                    
                    time_slot = TimeSlot(day, period)
                    
                    # 交流学級が空いているかチェック
                    if schedule.get_assignment(time_slot, exchange_ref):
                        continue
                    
                    # 親学級の授業をチェック
                    parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                    if parent_assignment and parent_assignment.subject.name in ["数", "英"]:
                        # 交流学級の教師を取得
                        if exchange_num == 6:
                            teacher_name = "財津"
                        else:  # 7組
                            teacher_name = "智田"
                        
                        # 全教師から名前で検索
                        teacher = None
                        for t in school.get_all_teachers():
                            if t.name == teacher_name:
                                teacher = t
                                break
                        
                        if teacher and self.teacher_tracker.is_available(teacher.name, day, period):
                            # 教師不在チェック
                            if not school.is_teacher_unavailable(teacher.name, day, period):
                                assignment = Assignment(
                                    exchange_ref,
                                    Subject("自立"),
                                    teacher
                                )
                                
                                try:
                                    schedule.assign(time_slot, assignment)
                                    placed += 1
                                    jiritsu_hours[exchange_class] += 1
                                    
                                    # 教師を使用済みにマーク
                                    self.teacher_tracker.mark_unavailable(
                                        teacher.name, day, period,
                                        str(exchange_ref), "自立"
                                    )
                                    
                                    # 日内科目トラッカーに追加
                                    self.daily_tracker.add_subject(exchange_class, day, "自立")
                                    
                                except:
                                    pass
        
        return placed
    
    def _sync_grade5_classes(self, schedule: 'Schedule', school: 'School') -> int:
        """5組のクラスを同期"""
        synced = 0
        days = ["月", "火", "水", "木", "金"]
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        from ....domain.value_objects.assignment import Assignment
        
        # 5組の3クラス
        grade5_refs = [
            ClassReference(1, 5),
            ClassReference(2, 5),
            ClassReference(3, 5)
        ]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 既存の配置を確認
                assignments = []
                for ref in grade5_refs:
                    assignment = schedule.get_assignment(time_slot, ref)
                    if assignment:
                        assignments.append((ref, assignment))
                
                # 1つでも配置があれば、他も同期
                if assignments:
                    # 最初の配置を基準にする
                    base_ref, base_assignment = assignments[0]
                    
                    for ref in grade5_refs:
                        if ref != base_ref and not schedule.get_assignment(time_slot, ref):
                            # 同じ科目・教師で配置
                            new_assignment = Assignment(
                                ref,
                                base_assignment.subject,
                                base_assignment.teacher
                            )
                            
                            try:
                                schedule.assign(time_slot, new_assignment)
                                synced += 1
                                
                                # 日内科目トラッカーに追加
                                class_key = f"{ref.grade}年{ref.class_number}組"
                                self.daily_tracker.add_subject(class_key, day, base_assignment.subject.name)
                                
                            except:
                                pass
        
        return synced
    
    def _place_pe_carefully(self, schedule: 'Schedule', school: 'School') -> int:
        """体育を慎重に配置"""
        placed = 0
        days = ["月", "火", "水", "木", "金"]
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        from ....domain.value_objects.assignment import Assignment
        from ....domain.value_objects.time_slot import Subject
        
        # 各クラスの体育時数を追跡
        pe_hours = defaultdict(int)
        target_hours = 3  # 週3時間
        
        # 体育館使用状況を追跡
        gym_usage = defaultdict(list)  # (day, period) -> [class_refs]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # この時間に体育館を使用しているクラスを確認
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name == "保":
                        gym_usage[(day, period)].append(class_ref)
                
                # 体育館が空いているか、交流学級ペアのみが使用中か確認
                current_usage = gym_usage[(day, period)]
                can_add_pe = len(current_usage) == 0 or self._can_add_pe_class(current_usage)
                
                if not can_add_pe:
                    continue
                
                # 体育が必要なクラスをリストアップ
                classes_needing_pe = []
                for class_ref in school.get_all_classes():
                    # 5組は別処理なのでスキップ
                    if class_ref.class_number == 5:
                        continue
                    
                    class_key = f"{class_ref.grade}年{class_ref.class_number}組"
                    if pe_hours[class_key] < target_hours:
                        if not schedule.get_assignment(time_slot, class_ref):
                            # この日に既に体育があるかチェック
                            if not self.daily_tracker.has_subject(class_key, day, "保"):
                                classes_needing_pe.append(class_ref)
                
                if classes_needing_pe:
                    # ランダムに1クラスを選択
                    class_ref = random.choice(classes_needing_pe)
                    teacher = self._get_teacher_for_subject_from_school("保", class_ref.grade, class_ref.class_number)
                    
                    if teacher and self.teacher_tracker.is_available(teacher.name, day, period):
                        # 教師不在チェック
                        if not school.is_teacher_unavailable(teacher.name, day, period):
                            assignment = Assignment(
                                class_ref,
                                Subject("保"),
                                teacher
                            )
                            
                            try:
                                schedule.assign(time_slot, assignment)
                                placed += 1
                                pe_hours[f"{class_ref.grade}年{class_ref.class_number}組"] += 1
                                gym_usage[(day, period)].append(class_ref)
                                
                                # 教師を使用済みにマーク
                                self.teacher_tracker.mark_unavailable(
                                    teacher.name, day, period,
                                    str(class_ref), "保"
                                )
                                
                                # 日内科目トラッカーに追加
                                class_key = f"{class_ref.grade}年{class_ref.class_number}組"
                                self.daily_tracker.add_subject(class_key, day, "保")
                                
                                # 交流学級も同期
                                self._sync_exchange_pe(schedule, school, class_ref, time_slot, teacher)
                                
                            except:
                                pass
        
        return placed
    
    def _can_add_pe_class(self, current_usage: List) -> bool:
        """体育館に追加でクラスを入れられるかチェック"""
        # 交流学級ペアのみが使用中なら追加不可
        if len(current_usage) == 2:
            class1 = str(current_usage[0])
            class2 = str(current_usage[1])
            
            # 交流学級ペアかチェック
            for exchange, parent in self.exchange_parent_map.items():
                if (class1 == exchange and class2 == parent) or (class1 == parent and class2 == exchange):
                    return False
        
        # 5組合同なら追加不可
        grade5_count = sum(1 for c in current_usage if c.class_number == 5)
        if grade5_count >= 3:
            return False
            
        # 1クラスのみなら追加可能
        return len(current_usage) < 2
    
    def _sync_exchange_pe(self, schedule: 'Schedule', school: 'School', parent_ref, time_slot, teacher):
        """交流学級の体育を同期"""
        parent_class = f"{parent_ref.grade}年{parent_ref.class_number}組"
        
        for exchange_class, parent_class_name in self.exchange_parent_map.items():
            if parent_class_name == parent_class:
                from ....domain.value_objects.time_slot import ClassReference
                from ....domain.value_objects.assignment import Assignment
                from ....domain.value_objects.time_slot import Subject
                
                exchange_parts = exchange_class.split("年")
                exchange_grade = int(exchange_parts[0])
                exchange_num = int(exchange_parts[1].replace("組", ""))
                exchange_ref = ClassReference(exchange_grade, exchange_num)
                
                if not schedule.get_assignment(time_slot, exchange_ref):
                    exchange_assignment = Assignment(
                        exchange_ref,
                        Subject("保"),
                        teacher
                    )
                    try:
                        schedule.assign(time_slot, exchange_assignment)
                        
                        # 日内科目トラッカーに追加
                        self.daily_tracker.add_subject(exchange_class, time_slot.day, "保")
                        
                    except:
                        pass
    
    def _place_major_subjects_improved(self, schedule: 'Schedule', school: 'School') -> int:
        """主要教科を配置（改良版）"""
        placed = 0
        major_subjects = ["国", "数", "英", "理", "社"]
        days = ["月", "火", "水", "木", "金"]
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        from ....domain.value_objects.assignment import Assignment
        from ....domain.value_objects.time_slot import Subject
        
        # 各クラス・科目の配置時数を追跡
        subject_hours = defaultdict(lambda: defaultdict(int))
        target_hours = {"国": 4, "数": 4, "英": 4, "理": 3, "社": 3}
        
        # 全ての空きスロットに対して配置を試みる
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    # 5組は別処理なのでスキップ
                    if class_ref.class_number == 5:
                        continue
                    
                    # 既に授業が入っているかチェック
                    if schedule.get_assignment(time_slot, class_ref):
                        continue
                    
                    class_key = f"{class_ref.grade}年{class_ref.class_number}組"
                    
                    # 配置可能な科目を探す
                    available_subjects = []
                    for subject in major_subjects:
                        # 時数チェック
                        if subject_hours[class_key][subject] >= target_hours[subject]:
                            continue
                        
                        # 日内重複チェック（共有トラッカーを使用）
                        if self.daily_tracker.has_subject(class_key, day, subject):
                            continue
                        
                        # 教師取得と利用可能性チェック
                        teacher = self._get_teacher_for_subject_from_school(subject, class_ref.grade, class_ref.class_number)
                        if teacher and self.teacher_tracker.is_available(teacher.name, day, period):
                            # 教師不在チェック
                            if not school.is_teacher_unavailable(teacher.name, day, period):
                                available_subjects.append((subject, teacher))
                    
                    if available_subjects:
                        # 時数の少ない科目を優先
                        subject, teacher = min(available_subjects, key=lambda x: subject_hours[class_key][x[0]])
                        
                        assignment = Assignment(
                            class_ref,
                            Subject(subject),
                            teacher
                        )
                        
                        try:
                            schedule.assign(time_slot, assignment)
                            placed += 1
                            subject_hours[class_key][subject] += 1
                            
                            # 日内科目トラッカーに追加（共有）
                            self.daily_tracker.add_subject(class_key, day, subject)
                            
                            # 教師を使用済みにマーク
                            self.teacher_tracker.mark_unavailable(
                                teacher.name, day, period,
                                str(class_ref), subject
                            )
                        except:
                            pass
        
        return placed
    
    def _place_skill_subjects_improved(self, schedule: 'Schedule', school: 'School') -> int:
        """技能教科を配置（改良版）"""
        placed = 0
        skill_subjects = ["音", "美", "技", "家"]
        days = ["月", "火", "水", "木", "金"]
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        from ....domain.value_objects.assignment import Assignment
        from ....domain.value_objects.time_slot import Subject
        
        # 各クラス・科目の配置時数を追跡
        subject_hours = defaultdict(lambda: defaultdict(int))
        target_hours = {"音": 1, "美": 1, "技": 1, "家": 1}
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    # 5組は別処理なのでスキップ
                    if class_ref.class_number == 5:
                        continue
                    
                    # 既に授業が入っているかチェック
                    if schedule.get_assignment(time_slot, class_ref):
                        continue
                    
                    class_key = f"{class_ref.grade}年{class_ref.class_number}組"
                    
                    # 配置可能な科目を探す
                    available_subjects = []
                    for subject in skill_subjects:
                        # 時数チェック
                        if subject_hours[class_key][subject] >= target_hours[subject]:
                            continue
                        
                        # 日内重複チェック（共有トラッカーを使用）
                        if self.daily_tracker.has_subject(class_key, day, subject):
                            continue
                        
                        # 教師取得と利用可能性チェック
                        teacher = self._get_teacher_for_subject_from_school(subject, class_ref.grade, class_ref.class_number)
                        if teacher and self.teacher_tracker.is_available(teacher.name, day, period):
                            # 教師不在チェック
                            if not school.is_teacher_unavailable(teacher.name, day, period):
                                available_subjects.append((subject, teacher))
                    
                    if available_subjects:
                        # ランダムに科目を選択
                        subject, teacher = random.choice(available_subjects)
                        
                        assignment = Assignment(
                            class_ref,
                            Subject(subject),
                            teacher
                        )
                        
                        try:
                            schedule.assign(time_slot, assignment)
                            placed += 1
                            subject_hours[class_key][subject] += 1
                            
                            # 日内科目トラッカーに追加（共有）
                            self.daily_tracker.add_subject(class_key, day, subject)
                            
                            # 教師を使用済みにマーク
                            self.teacher_tracker.mark_unavailable(
                                teacher.name, day, period,
                                str(class_ref), subject
                            )
                        except:
                            pass
        
        return placed
    
    def _fill_empty_slots(self, schedule: 'Schedule', school: 'School') -> int:
        """空きスロットを埋める"""
        filled = 0
        days = ["月", "火", "水", "木", "金"]
        all_subjects = ["国", "数", "英", "理", "社", "音", "美", "技", "家", "保"]
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        from ....domain.value_objects.assignment import Assignment
        from ....domain.value_objects.time_slot import Subject
        
        # 空きスロットを埋める
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    # 既に授業が入っているかチェック
                    if schedule.get_assignment(time_slot, class_ref):
                        continue
                    
                    class_key = f"{class_ref.grade}年{class_ref.class_number}組"
                    
                    # 配置可能な科目を探す
                    available_subjects = []
                    for subject in all_subjects:
                        # 日内重複チェック（共有トラッカーを使用）
                        if self.daily_tracker.has_subject(class_key, day, subject):
                            continue
                        
                        # 教師取得と利用可能性チェック
                        teacher = self._get_teacher_for_subject_from_school(subject, class_ref.grade, class_ref.class_number)
                        if teacher and self.teacher_tracker.is_available(teacher.name, day, period):
                            # 教師不在チェック
                            if not school.is_teacher_unavailable(teacher.name, day, period):
                                available_subjects.append((subject, teacher))
                    
                    if available_subjects:
                        # ランダムに科目を選択
                        subject, teacher = random.choice(available_subjects)
                        
                        assignment = Assignment(
                            class_ref,
                            Subject(subject),
                            teacher
                        )
                        
                        try:
                            schedule.assign(time_slot, assignment)
                            filled += 1
                            
                            # 日内科目トラッカーに追加（共有）
                            self.daily_tracker.add_subject(class_key, day, subject)
                            
                            # 教師を使用済みにマーク
                            self.teacher_tracker.mark_unavailable(
                                teacher.name, day, period,
                                str(class_ref), subject
                            )
                        except:
                            pass
        
        return filled
    
    def _sync_exchange_classes(self, schedule: 'Schedule', school: 'School') -> int:
        """交流学級を親学級と同期"""
        synced = 0
        days = ["月", "火", "水", "木", "金"]
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        
        for exchange_class, parent_class in self.exchange_parent_map.items():
            # クラス参照を作成
            exchange_parts = exchange_class.split("年")
            exchange_grade = int(exchange_parts[0])
            exchange_num = int(exchange_parts[1].replace("組", ""))
            exchange_ref = ClassReference(exchange_grade, exchange_num)
            
            parent_parts = parent_class.split("年")
            parent_grade = int(parent_parts[0])
            parent_num = int(parent_parts[1].replace("組", ""))
            parent_ref = ClassReference(parent_grade, parent_num)
            
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_ref)
                    parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                    
                    # 交流学級が自立活動の場合はスキップ
                    if exchange_assignment and exchange_assignment.subject.name in ["自立", "日生", "作業"]:
                        continue
                    
                    # 親学級に授業があり、交流学級が空いている場合
                    if parent_assignment and not exchange_assignment:
                        try:
                            schedule.assign(time_slot, parent_assignment)
                            synced += 1
                            
                            # 日内科目トラッカーに追加
                            self.daily_tracker.add_subject(exchange_class, day, parent_assignment.subject.name)
                            
                        except:
                            pass
        
        return synced
    
    def _final_optimization_improved(self, schedule: 'Schedule', school: 'School', max_iterations: int) -> int:
        """最終最適化（改良版）"""
        improvements = 0
        
        for iteration in range(max_iterations):
            # 日内重複の検出と修正
            daily_dup_fixed = self._fix_daily_duplicates(schedule, school)
            if daily_dup_fixed > 0:
                improvements += daily_dup_fixed
                self.logger.info(f"Iteration {iteration + 1}: {daily_dup_fixed}個の日内重複を修正")
            
            # 教師重複の検出（通常は発生しないはず）
            conflicts = self.teacher_tracker.get_conflicts()
            if len(conflicts) == 0 and daily_dup_fixed == 0:
                break
        
        return improvements
    
    def _fix_daily_duplicates(self, schedule: 'Schedule', school: 'School') -> int:
        """日内重複を修正"""
        fixed = 0
        days = ["月", "火", "水", "木", "金"]
        
        from ....domain.value_objects.time_slot import TimeSlot
        
        # 各クラス・日の科目を再確認
        for day in days:
            for class_ref in school.get_all_classes():
                class_key = f"{class_ref.grade}年{class_ref.class_number}組"
                subjects_in_day = []
                
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        subjects_in_day.append((period, assignment))
                
                # 重複を探す
                subject_counts = defaultdict(list)
                for period, assignment in subjects_in_day:
                    subject_counts[assignment.subject.name].append((period, assignment))
                
                for subject, occurrences in subject_counts.items():
                    if len(occurrences) > 1:
                        # 重複がある - 最初の1つを残して他を削除
                        for i in range(1, len(occurrences)):
                            period, assignment = occurrences[i]
                            time_slot = TimeSlot(day, period)
                            
                            # スロットをクリア
                            schedule.clear_slot(time_slot, class_ref)
                            fixed += 1
                            
                            # 日内科目トラッカーも更新
                            # (実際はaddしかないので、再初期化が必要かも)
        
        return fixed
    
    def _get_teacher_for_subject_from_school(self, subject: str, grade: int, class_num: int) -> Optional['Teacher']:
        """学校データから科目の教師を取得"""
        from ....domain.value_objects.time_slot import ClassReference
        
        # 教師キャッシュを作成（初回のみ）
        if not hasattr(self, '_teacher_cache'):
            self._teacher_cache = {}
            
        # キャッシュキー
        cache_key = f"{subject}_{grade}_{class_num}"
        
        # キャッシュにあれば返す
        if cache_key in self._teacher_cache:
            return self._teacher_cache[cache_key]
        
        # 学校から教師を取得（school属性経由）
        if hasattr(self, '_school'):
            school = self._school
        else:
            # generateメソッドから呼ばれるはずなので、schoolを保存
            return None
        
        class_ref = ClassReference(grade, class_num)
        teacher = school.get_assigned_teacher(subject, class_ref)
        
        # キャッシュに保存
        self._teacher_cache[cache_key] = teacher
        
        return teacher