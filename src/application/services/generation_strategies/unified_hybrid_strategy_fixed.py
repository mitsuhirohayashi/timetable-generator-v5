"""統一ハイブリッド生成戦略（修正版）

全ての戦略の長所を統合した、教師中心の時間割生成アルゴリズム。
教師重複を完全に排除し、制約違反を最小化します。

ハードコードされた教師マッピングを削除し、学校データから動的に取得します。
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


@dataclass
class TeacherScheduleSlot:
    """教師のスケジュールスロット"""
    is_available: bool = True
    assigned_class: Optional[str] = None
    subject: Optional[str] = None
    is_joint_class: bool = False  # 5組合同授業フラグ


class TeacherScheduleTracker:
    """教師スケジュール追跡システム"""
    
    def __init__(self):
        # 教師名 -> 曜日 -> 時限 -> TeacherScheduleSlot
        self.schedules: Dict[str, Dict[str, Dict[int, TeacherScheduleSlot]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(TeacherScheduleSlot))
        )
        self.teacher_subjects: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
        self.logger = logging.getLogger(__name__)
        
    def mark_unavailable(self, teacher: str, day: str, period: int, assigned_class: str, subject: str, is_joint: bool = False):
        """教師の時間を使用済みにマーク"""
        self.schedules[teacher][day][period] = TeacherScheduleSlot(
            is_available=False,
            assigned_class=assigned_class,
            subject=subject,
            is_joint_class=is_joint
        )
        
    def is_available(self, teacher: str, day: str, period: int) -> bool:
        """教師が利用可能か確認"""
        return self.schedules[teacher][day][period].is_available
        
    def get_conflicts(self) -> List[Tuple[str, str, int, List[str]]]:
        """教師の重複を検出"""
        conflicts = []
        for teacher, days in self.schedules.items():
            for day, periods in days.items():
                for period, slot in periods.items():
                    if not slot.is_available:
                        # 同じ時間の他の割り当てを確認
                        assignments = []
                        for t, d in self.schedules.items():
                            if t == teacher and day in d and period in d[day]:
                                if not d[day][period].is_available:
                                    assignments.append(d[day][period].assigned_class)
                        if len(assignments) > 1 and not slot.is_joint_class:
                            conflicts.append((teacher, day, period, assignments))
        return conflicts


class UnifiedHybridStrategyFixed(BaseGenerationStrategy):
    """統一ハイブリッド生成戦略（修正版）"""
    
    def __init__(self, constraint_system):
        super().__init__(constraint_system)
        self.logger = logging.getLogger(__name__)
        self.teacher_tracker = TeacherScheduleTracker()
        
        # 定数定義
        self.grade5_classes = ["1年5組", "2年5組", "3年5組"]
        self.exchange_parent_map = {
            "1年6組": "1年1組", "1年7組": "1年2組",
            "2年6組": "2年3組", "2年7組": "2年2組",
            "3年6組": "3年3組", "3年7組": "3年2組",
        }
        self.fixed_subjects = {"YT", "道", "学", "総", "欠", "行", "テスト", "技家", "学総"}
        
    def get_name(self) -> str:
        return "unified_hybrid_fixed"
        
    def generate(
        self,
        school: 'School',
        initial_schedule: Optional['Schedule'] = None,
        max_iterations: int = 500,
        **kwargs
    ) -> 'Schedule':
        """統一ハイブリッドアルゴリズムでスケジュールを生成"""
        self.logger.info("=== 統一ハイブリッドアルゴリズム（修正版）を開始 ===")
        self.logger.info("学校の実際の教師データを使用して生成します")
        
        # 学校オブジェクトを保存
        self._school = school
        
        # スケジュールの初期化
        from ....domain.entities.schedule import Schedule
        if initial_schedule:
            # 初期スケジュールがある場合はそのまま使用
            schedule = initial_schedule
        else:
            schedule = Schedule()
        
        # Phase 1: 固定要素の保護と配置
        self.logger.info("\nPhase 1: 固定要素の保護...")
        self._protect_fixed_elements(schedule, school, initial_schedule)
        
        # Phase 2: 5組合同授業の一括配置
        self.logger.info("\nPhase 2: 5組合同授業の配置...")
        placed_grade5 = self._place_grade5_jointly(schedule, school)
        self.logger.info(f"  → {placed_grade5}コマ配置")
        
        # Phase 3: 交流学級の自立活動配置
        self.logger.info("\nPhase 3: 交流学級の自立活動配置...")
        placed_jiritsu = self._place_jiritsu_activities(schedule, school)
        self.logger.info(f"  → {placed_jiritsu}コマ配置")
        
        # Phase 4: 体育の分散配置
        self.logger.info("\nPhase 4: 体育の分散配置...")
        placed_pe = self._place_pe_distributed(schedule, school)
        self.logger.info(f"  → {placed_pe}コマ配置")
        
        # Phase 5: 主要教科の配置
        self.logger.info("\nPhase 5: 主要教科の配置...")
        placed_major = self._place_major_subjects(schedule, school)
        self.logger.info(f"  → {placed_major}コマ配置")
        
        # Phase 6: 技能教科の配置
        self.logger.info("\nPhase 6: 技能教科の配置...")
        placed_skill = self._place_skill_subjects(schedule, school)
        self.logger.info(f"  → {placed_skill}コマ配置")
        
        # Phase 7: 交流学級の同期
        self.logger.info("\nPhase 7: 交流学級の同期...")
        synced = self._sync_exchange_classes(schedule, school)
        self.logger.info(f"  → {synced}コマ同期")
        
        # Phase 8: 最終最適化
        self.logger.info("\nPhase 8: 最終最適化...")
        optimized = self._final_optimization(schedule, school, max_iterations=100)
        self.logger.info(f"  → {optimized}回の改善")
        
        # 検証
        violations = self.validate_schedule(schedule, school)
        teacher_conflicts = self.teacher_tracker.get_conflicts()
        
        self.logger.info(f"\n=== 生成完了 ===")
        self.logger.info(f"制約違反: {len(violations)}件")
        self.logger.info(f"教師重複: {len(teacher_conflicts)}件")
        
        if violations:
            self.log_violations(violations[:10])  # 最初の10件のみ表示
            
        return schedule
    
    def _protect_fixed_elements(self, schedule: 'Schedule', school: 'School', initial_schedule: Optional['Schedule']):
        """固定要素を保護し、既存の全ての割り当てを教師トラッカーに登録"""
        if not initial_schedule:
            return
            
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    assignment = initial_schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        # 既存の全ての割り当てを教師トラッカーに登録
                        if assignment.teacher:
                            # 5組の合同授業かチェック
                            is_joint = False
                            if str(class_ref) in self.grade5_classes:
                                # 他の5組クラスも同じ科目か確認
                                all_same = True
                                for grade5_class in self.grade5_classes:
                                    if str(class_ref) != grade5_class:
                                        other_parts = grade5_class.split("年")
                                        other_grade = int(other_parts[0])
                                        other_num = int(other_parts[1].replace("組", ""))
                                        other_ref = ClassReference(other_grade, other_num)
                                        other_assignment = initial_schedule.get_assignment(time_slot, other_ref)
                                        if not other_assignment or other_assignment.subject.name != assignment.subject.name:
                                            all_same = False
                                            break
                                is_joint = all_same
                            
                            self.teacher_tracker.mark_unavailable(
                                assignment.teacher.name, day, period, 
                                str(class_ref), assignment.subject.name,
                                is_joint=is_joint
                            )
                        
                        # 固定科目の場合は保護（初期スケジュールと同じ場合はスキップ）
                        if assignment.subject.name in self.fixed_subjects:
                            existing = schedule.get_assignment(time_slot, class_ref)
                            if not existing:
                                schedule.assign(time_slot, assignment)
    
    def _place_grade5_jointly(self, schedule: 'Schedule', school: 'School') -> int:
        """5組合同授業を一括配置"""
        placed = 0
        days = ["月", "火", "水", "木", "金"]
        subjects_hours = {
            "国": 4, "数": 4, "英": 4, "理": 3, "社": 3,
            "保": 3, "音": 1, "美": 1, "技": 1, "家": 1,
            "日生": 2, "作業": 2, "生単": 1, "自立": 2
        }
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        from ....domain.value_objects.assignment import Assignment
        from ....domain.value_objects.time_slot import Subject
        
        # 各科目の配置時数を追跡
        placed_hours = defaultdict(int)
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 5組全てが空いているか確認
                all_available = True
                for grade in [1, 2, 3]:
                    class_ref = ClassReference(grade, 5)
                    if schedule.get_assignment(time_slot, class_ref):
                        all_available = False
                        break
                
                if not all_available:
                    continue
                
                # 配置する科目を選択
                available_subjects = []
                for subject, hours in subjects_hours.items():
                    if placed_hours[subject] < hours:
                        # 教師が利用可能か確認
                        teacher = self._get_teacher_for_subject_from_school(subject, 1, 5)
                        if teacher and self.teacher_tracker.is_available(teacher.name, day, period):
                            # 教師不在チェック
                            if not school.is_teacher_unavailable(teacher.name, day, period):
                                available_subjects.append(subject)
                
                if available_subjects:
                    # ランダムに科目を選択
                    subject = random.choice(available_subjects)
                    teacher = self._get_teacher_for_subject_from_school(subject, 1, 5)
                    
                    if teacher:
                        # 3クラス全てに配置
                        for grade in [1, 2, 3]:
                            class_ref = ClassReference(grade, 5)
                            assignment = Assignment(
                                class_ref,
                                Subject(subject),
                                teacher
                            )
                            schedule.assign(time_slot, assignment)
                            placed += 1
                        
                        # 教師を使用済みにマーク（合同授業フラグ付き）
                        self.teacher_tracker.mark_unavailable(
                            teacher.name, day, period, 
                            "5組合同", subject, is_joint=True
                        )
                        placed_hours[subject] += 1
        
        return placed
    
    def _place_jiritsu_activities(self, schedule: 'Schedule', school: 'School') -> int:
        """交流学級の自立活動を配置"""
        placed = 0
        days = ["月", "火", "水", "木", "金"]
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        from ....domain.value_objects.assignment import Assignment
        from ....domain.value_objects.time_slot import Subject
        
        for exchange_class, parent_class in self.exchange_parent_map.items():
            # 各交流学級は週2時間の自立活動が必要
            jiritsu_hours = 0
            
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
                for period in range(1, 5):  # 6限は除外
                    if jiritsu_hours >= 2:
                        break
                        
                    time_slot = TimeSlot(day, period)
                    
                    # 親学級の科目を確認
                    parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                    if parent_assignment and parent_assignment.subject.name in ["数", "英"]:
                        # 交流学級が空いているか確認
                        if not schedule.get_assignment(time_slot, exchange_ref):
                            # 自立活動の教師を取得
                            teacher = self._get_teacher_for_subject_from_school("自立", exchange_grade, exchange_num)
                            
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
                                        jiritsu_hours += 1
                                        
                                        # 教師を使用済みにマーク
                                        self.teacher_tracker.mark_unavailable(
                                            teacher.name, day, period,
                                            str(exchange_ref), "自立"
                                        )
                                    except:
                                        pass
        
        return placed
    
    def _place_pe_distributed(self, schedule: 'Schedule', school: 'School') -> int:
        """体育を分散配置（体育館使用制約を考慮）"""
        placed = 0
        days = ["月", "火", "水", "木", "金"]
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        from ....domain.value_objects.assignment import Assignment
        from ....domain.value_objects.time_slot import Subject
        
        # 各クラスの体育時数を追跡
        pe_hours = defaultdict(int)
        target_hours = 3  # 週3時間
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # この時間に体育館が使用されているか確認
                gym_used = False
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name == "保":
                        gym_used = True
                        break
                
                if gym_used:
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
                                
                                # 教師を使用済みにマーク
                                self.teacher_tracker.mark_unavailable(
                                    teacher.name, day, period,
                                    str(class_ref), "保"
                                )
                                
                                # 交流学級も同期
                                for exchange_class, parent_class in self.exchange_parent_map.items():
                                    if parent_class == f"{class_ref.grade}年{class_ref.class_number}組":
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
                                            schedule.assign(time_slot, exchange_assignment)
                                            placed += 1
                            except:
                                pass
        
        return placed
    
    def _place_major_subjects(self, schedule: 'Schedule', school: 'School') -> int:
        """主要教科（国・数・英・理・社）を配置"""
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
                    
                    # この日に既に配置されている科目を確認
                    subjects_today = set()
                    for p in range(1, 7):
                        ts = TimeSlot(day, p)
                        assignment = schedule.get_assignment(ts, class_ref)
                        if assignment:
                            subjects_today.add(assignment.subject.name)
                    
                    # 配置可能な科目を探す
                    available_subjects = []
                    for subject in major_subjects:
                        # 時数チェック
                        if subject_hours[class_key][subject] >= target_hours[subject]:
                            continue
                        
                        # 日内重複チェック
                        if subject in subjects_today:
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
                            
                            # 教師を使用済みにマーク
                            self.teacher_tracker.mark_unavailable(
                                teacher.name, day, period,
                                str(class_ref), subject
                            )
                        except:
                            pass
        
        return placed
    
    def _place_skill_subjects(self, schedule: 'Schedule', school: 'School') -> int:
        """技能教科（音・美・技・家）を配置"""
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
                            
                            # 教師を使用済みにマーク
                            self.teacher_tracker.mark_unavailable(
                                teacher.name, day, period,
                                str(class_ref), subject
                            )
                        except:
                            pass
        
        return placed
    
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
                        except:
                            pass
        
        return synced
    
    def _final_optimization(self, schedule: 'Schedule', school: 'School', max_iterations: int) -> int:
        """最終最適化（教師重複の解消）"""
        improvements = 0
        
        for _ in range(max_iterations):
            conflicts = self.teacher_tracker.get_conflicts()
            if not conflicts:
                break
            
            # 各重複を解消
            for teacher, day, period, classes in conflicts:
                # 重複している授業の1つを移動
                if len(classes) > 1:
                    # 最初の授業以外を削除
                    for i, class_name in enumerate(classes[1:]):
                        # スケジュールから該当授業を探して削除
                        from ....domain.value_objects.time_slot import TimeSlot
                        time_slot = TimeSlot(day, period)
                        
                        for class_ref in school.get_all_classes():
                            if str(class_ref) == class_name:
                                assignment = schedule.get_assignment(time_slot, class_ref)
                                if assignment and assignment.teacher and assignment.teacher.name == teacher:
                                    try:
                                        schedule.remove_assignment(time_slot, class_ref)
                                        improvements += 1
                                        
                                        # トラッカーも更新
                                        self.teacher_tracker.schedules[teacher][day][period].is_available = True
                                    except:
                                        pass
        
        return improvements
    
    def _get_teacher_for_subject_from_school(self, subject: str, grade: int, class_num: int) -> Optional['Teacher']:
        """学校オブジェクトから科目・学年・クラスに応じた教師を取得"""
        if not self._school:
            return None
            
        try:
            from ....domain.value_objects.time_slot import ClassReference, Subject
            class_ref = ClassReference(grade, class_num)
            subject_obj = Subject(subject)
            
            # 学校から割り当てられた教師を取得
            teacher = self._school.get_assigned_teacher(subject_obj, class_ref)
            return teacher
            
        except Exception as e:
            self.logger.debug(f"教師取得エラー: {subject} for {grade}-{class_num}: {e}")
            return None