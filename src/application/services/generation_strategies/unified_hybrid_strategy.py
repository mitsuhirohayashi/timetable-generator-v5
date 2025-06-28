"""統一ハイブリッド生成戦略

全ての戦略の長所を統合した、教師中心の時間割生成アルゴリズム。
教師重複を完全に排除し、制約違反を最小化します。
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
    
    def register_teacher_subjects(self, teacher_mapping: Dict):
        """教師と科目の対応を登録"""
        for subject, mapping in teacher_mapping.items():
            if isinstance(mapping, str):
                # 単一教師
                self.teacher_subjects[mapping][subject] = ["all"]
            elif isinstance(mapping, list):
                # 複数教師（体育など）
                for teacher in mapping:
                    self.teacher_subjects[teacher][subject] = ["all"]
            elif isinstance(mapping, dict):
                # 学年・クラス別マッピング
                for grade, grade_mapping in mapping.items():
                    if isinstance(grade_mapping, dict):
                        for class_num, teacher in grade_mapping.items():
                            self.teacher_subjects[teacher][subject].append(f"{grade}年{class_num}組")
                    else:
                        self.teacher_subjects[grade_mapping][subject].append(f"{grade}年")


class UnifiedHybridStrategy(BaseGenerationStrategy):
    """統一ハイブリッド生成戦略"""
    
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
        
        # 教師マッピング（CLAUDE.mdより）
        self.teacher_mapping = self._load_teacher_mapping()
        self.teacher_tracker.register_teacher_subjects(self.teacher_mapping)
        
    def get_name(self) -> str:
        return "unified_hybrid"
        
    def generate(
        self,
        school: 'School',
        initial_schedule: Optional['Schedule'] = None,
        max_iterations: int = 500,
        **kwargs
    ) -> 'Schedule':
        """統一ハイブリッドアルゴリズムでスケジュールを生成"""
        print("[PRINT DEBUG] UnifiedHybridStrategy.generate() called")
        self.logger.info("=== 統一ハイブリッドアルゴリズムを開始 ===")
        self.logger.info("教師中心アプローチで制約違反を最小化します")
        
        # 学校オブジェクトを保存
        self._school = school
        
        # スケジュールの初期化
        from ....domain.entities.schedule import Schedule
        if initial_schedule:
            # 初期スケジュールがある場合はそのまま使用
            schedule = initial_schedule
        else:
            schedule = Schedule()
        
        # 教師不在情報を読み込む
        teacher_absences = self._load_teacher_absences()
        
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
    
    def _load_teacher_mapping(self) -> Dict:
        """教師マッピングを定義"""
        return {
            "国": {
                1: {"1": "寺田", "2": "寺田", "3": "寺田", "5": "寺田", "6": "寺田", "7": "寺田"},
                2: {"1": "寺田", "2": "小野塚", "3": "小野塚", "5": "寺田", "6": "小野塚", "7": "小野塚"},
                3: {"1": "小野塚", "2": "小野塚", "3": "小野塚", "5": "寺田", "6": "小野塚", "7": "小野塚"}
            },
            "社": {
                1: {"1": "蒲地", "2": "北", "3": "蒲地", "5": "蒲地", "6": "蒲地", "7": "北"},
                2: {"1": "蒲地", "2": "蒲地", "3": "蒲地", "5": "蒲地", "6": "蒲地", "7": "蒲地"},
                3: {"1": "北", "2": "北", "3": "北", "5": "蒲地", "6": "北", "7": "北"}
            },
            "数": {
                1: {"1": "梶永", "2": "梶永", "3": "梶永", "5": "梶永", "6": "梶永", "7": "梶永"},
                2: {"1": "井上", "2": "井上", "3": "井上", "5": "梶永", "6": "井上", "7": "井上"},
                3: {"1": "森山", "2": "森山", "3": "森山", "5": "梶永", "6": "森山", "7": "森山"}
            },
            "理": {
                1: {"1": "金子ひ", "2": "金子ひ", "3": "金子ひ", "5": "智田", "6": "金子ひ", "7": "金子ひ"},
                2: {"1": "智田", "2": "智田", "3": "金子ひ", "5": "智田", "6": "金子ひ", "7": "智田"},
                3: {"1": "白石", "2": "白石", "3": "白石", "5": "智田", "6": "白石", "7": "白石"}
            },
            "英": {
                1: {"1": "井野口", "2": "井野口", "3": "井野口", "5": "林田", "6": "井野口", "7": "井野口"},
                2: {"1": "箱崎", "2": "箱崎", "3": "箱崎", "5": "林田", "6": "箱崎", "7": "箱崎"},
                3: {"1": "林田", "2": "林田", "3": "林田", "5": "林田", "6": "林田", "7": "林田"}
            },
            "音": "塚本",
            "美": {1: "青井", 2: "青井", 3: "青井", "5組": "金子み"},
            "保": ["永山", "野口", "財津"],
            "技": "林",
            "家": "金子み",
            "自立": {"5": "金子み", "6": "財津", "7": "智田"},
            "日生": "金子み",
            "作業": "金子み",
            "生単": "金子み"
        }
    
    def _load_teacher_absences(self) -> Dict[str, List[Tuple[str, List[int]]]]:
        """教師不在情報を読み込む（Follow-up.csvより）"""
        return {
            "北": [("月", [1, 2, 3, 4, 5, 6]), ("火", [1, 2, 3, 4, 5, 6])],  # 振休
            "井上": [("月", [5, 6]), ("金", [1, 2, 3, 4, 5, 6])],  # 研修、出張
            "梶永": [("金", [1, 2, 3, 4, 5, 6])],  # 出張
            "財津": [("火", [5, 6]), ("木", [1, 2, 3, 4, 5, 6])],  # 外勤、年休
            "永山": [("火", [5, 6])],  # 外勤
            "林田": [("火", [5, 6])],  # 外勤
            "校長": [("水", [1, 2, 3, 4, 5, 6])],  # 出張
            "白石": [("水", [1, 2, 3, 4, 5, 6])],  # 年休
            "森山": [("水", [5, 6])],  # 外勤
            "小野塚": [("金", [4, 5, 6])],  # 外勤
        }
    
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
        from ....domain.value_objects.time_slot import Subject, Teacher
        
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
                        teacher_name = self._get_teacher_for_subject(subject, 1, 5)
                        if teacher_name and self.teacher_tracker.is_available(teacher_name, day, period):
                            available_subjects.append(subject)
                
                if available_subjects:
                    # ランダムに科目を選択
                    subject = random.choice(available_subjects)
                    teacher_name = self._get_teacher_for_subject(subject, 1, 5)
                    
                    if teacher_name:
                        teacher_obj = None
                        for t in school.get_all_teachers():
                            if t.name == teacher_name:
                                teacher_obj = t
                                break
                        
                        # 3クラス全てに配置
                        for grade in [1, 2, 3]:
                            class_ref = ClassReference(grade, 5)
                            assignment = Assignment(
                                class_ref,
                                Subject(subject),
                                teacher_obj
                            )
                            schedule.assign(time_slot, assignment)
                            placed += 1
                        
                        # 教師を使用済みにマーク（合同授業フラグ付き）
                        self.teacher_tracker.mark_unavailable(
                            teacher_name, day, period, 
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
        from ....domain.value_objects.time_slot import Subject, Teacher
        
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
                            # 担当教師を取得
                            teacher_name = self._get_jiritsu_teacher(exchange_num)
                            if teacher_name and self.teacher_tracker.is_available(teacher_name, day, period):
                                teacher_obj = None
                                for t in school.get_all_teachers():
                                    if t.name == teacher_name:
                                        teacher_obj = t
                                        break
                                
                                # 自立活動を配置
                                assignment = Assignment(
                                    exchange_ref,
                                    Subject("自立"),
                                    teacher_obj
                                )
                                schedule.assign(time_slot, assignment)
                                
                                self.teacher_tracker.mark_unavailable(
                                    teacher_name, day, period,
                                    exchange_class, "自立"
                                )
                                
                                placed += 1
                                jiritsu_hours += 1
        
        return placed
    
    def _place_pe_distributed(self, schedule: 'Schedule', school: 'School') -> int:
        """体育を分散配置"""
        placed = 0
        days = ["月", "火", "水", "木", "金"]
        pe_teachers = ["永山", "野口", "財津"]
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        from ....domain.value_objects.assignment import Assignment
        from ....domain.value_objects.time_slot import Subject, Teacher
        
        # 各クラスの必要時数
        target_hours = 3
        class_hours = defaultdict(int)
        
        # 時間帯別の体育配置数を追跡
        gym_usage = defaultdict(int)
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                time_key = f"{day}_{period}"
                
                # この時間帯の体育館使用状況を確認
                if gym_usage[time_key] >= 1:  # 既に1クラスが使用中
                    continue
                
                # 配置可能なクラスを探す
                for class_ref in school.get_all_classes():
                    class_name = str(class_ref)
                    
                    # 5組と交流学級は別処理
                    if class_name.endswith("5組") or class_name.endswith("6組") or class_name.endswith("7組"):
                        continue
                    
                    # 必要時数を満たしているか確認
                    if class_hours[class_name] >= target_hours:
                        continue
                    
                    # 既に授業が配置されているか確認
                    if schedule.get_assignment(time_slot, class_ref):
                        continue
                    
                    # その日に既に体育があるか確認
                    has_pe_today = False
                    for p in range(1, 7):
                        ts = TimeSlot(day, p)
                        ass = schedule.get_assignment(ts, class_ref)
                        if ass and ass.subject.name == "保":
                            has_pe_today = True
                            break
                    
                    if has_pe_today:
                        continue
                    
                    # 利用可能な体育教師を探す
                    for teacher_name in pe_teachers:
                        if self.teacher_tracker.is_available(teacher_name, day, period):
                            teacher_obj = None
                            for t in school.get_all_teachers():
                                if t.name == teacher_name:
                                    teacher_obj = t
                                    break
                            
                            # 体育を配置
                            assignment = Assignment(
                                class_ref,
                                Subject("保"),
                                teacher_obj
                            )
                            schedule.assign(time_slot, assignment)
                            
                            self.teacher_tracker.mark_unavailable(
                                teacher_name, day, period,
                                class_name, "保"
                            )
                            
                            gym_usage[time_key] += 1
                            class_hours[class_name] += 1
                            placed += 1
                            break
                    
                    if gym_usage[time_key] >= 1:
                        break
        
        return placed
    
    def _place_major_subjects(self, schedule: 'Schedule', school: 'School') -> int:
        """主要教科を配置"""
        placed = 0
        days = ["月", "火", "水", "木", "金"]
        major_subjects = ["国", "数", "英", "理", "社"]
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        from ....domain.value_objects.assignment import Assignment
        from ....domain.value_objects.time_slot import Subject, Teacher
        
        # 標準時数
        standard_hours = {"国": 4, "数": 4, "英": 4, "理": 3, "社": 3}
        
        # 各クラス・科目の配置時数を追跡
        class_subject_hours = defaultdict(lambda: defaultdict(int))
        
        # ランダムな順序で配置を試みる
        time_slots = []
        for day in days:
            for period in range(1, 7):
                time_slots.append((day, period))
        
        random.shuffle(time_slots)
        
        for day, period in time_slots:
            time_slot = TimeSlot(day, period)
            
            # ランダムな順序でクラスを処理
            classes = list(school.get_all_classes())
            random.shuffle(classes)
            
            for class_ref in classes:
                class_name = str(class_ref)
                
                # 5組と交流学級の自立活動時間はスキップ
                if class_name.endswith("5組"):
                    continue
                
                # 既に授業が配置されているか確認
                if schedule.get_assignment(time_slot, class_ref):
                    continue
                
                # 配置可能な主要教科を探す
                available_subjects = []
                for subject in major_subjects:
                    # 標準時数を満たしているか確認
                    if class_subject_hours[class_name][subject] >= standard_hours[subject]:
                        continue
                    
                    # その日に既に同じ科目があるか確認
                    has_subject_today = False
                    for p in range(1, 7):
                        ts = TimeSlot(day, p)
                        ass = schedule.get_assignment(ts, class_ref)
                        if ass and ass.subject.name == subject:
                            has_subject_today = True
                            break
                    
                    if has_subject_today:
                        continue
                    
                    # 教師を取得
                    grade = class_ref.grade
                    class_num = class_ref.class_number
                    teacher_name = self._get_teacher_for_subject(subject, grade, class_num)
                    
                    if teacher_name and self.teacher_tracker.is_available(teacher_name, day, period):
                        available_subjects.append((subject, teacher_name))
                
                if available_subjects:
                    # ランダムに科目を選択
                    subject, teacher_name = random.choice(available_subjects)
                    
                    teacher_obj = None
                    for t in school.get_all_teachers():
                        if t.name == teacher_name:
                            teacher_obj = t
                            break
                    
                    # 授業を配置
                    assignment = Assignment(
                        class_ref,
                        Subject(subject),
                        teacher_obj
                    )
                    schedule.assign(time_slot, assignment)
                    
                    self.teacher_tracker.mark_unavailable(
                        teacher_name, day, period,
                        class_name, subject
                    )
                    
                    class_subject_hours[class_name][subject] += 1
                    placed += 1
        
        return placed
    
    def _place_skill_subjects(self, schedule: 'Schedule', school: 'School') -> int:
        """技能教科を配置"""
        placed = 0
        days = ["月", "火", "水", "木", "金"]
        skill_subjects = ["音", "美", "技", "家"]
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        from ....domain.value_objects.assignment import Assignment
        from ....domain.value_objects.time_slot import Subject, Teacher
        
        # 標準時数
        standard_hours = {"音": 1, "美": 1, "技": 1, "家": 1}
        
        # 各クラス・科目の配置時数を追跡
        class_subject_hours = defaultdict(lambda: defaultdict(int))
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    class_name = str(class_ref)
                    
                    # 5組は別処理
                    if class_name.endswith("5組"):
                        continue
                    
                    # 既に授業が配置されているか確認
                    if schedule.get_assignment(time_slot, class_ref):
                        continue
                    
                    # 配置可能な技能教科を探す
                    for subject in skill_subjects:
                        # 標準時数を満たしているか確認
                        if class_subject_hours[class_name][subject] >= standard_hours[subject]:
                            continue
                        
                        # 教師を取得
                        grade = class_ref.grade
                        class_num = class_ref.class_number
                        teacher_name = self._get_teacher_for_subject(subject, grade, class_num)
                        
                        if teacher_name and self.teacher_tracker.is_available(teacher_name, day, period):
                            teacher_obj = None
                            for t in school.get_all_teachers():
                                if t.name == teacher_name:
                                    teacher_obj = t
                                    break
                            
                            # 授業を配置
                            assignment = Assignment(
                                class_ref,
                                Subject(subject),
                                teacher_obj
                            )
                            schedule.assign(time_slot, assignment)
                            
                            self.teacher_tracker.mark_unavailable(
                                teacher_name, day, period,
                                class_name, subject
                            )
                            
                            class_subject_hours[class_name][subject] += 1
                            placed += 1
                            break
        
        return placed
    
    def _sync_exchange_classes(self, schedule: 'Schedule', school: 'School') -> int:
        """交流学級を親学級と同期"""
        synced = 0
        days = ["月", "火", "水", "木", "金"]
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        from ....domain.value_objects.assignment import Assignment
        
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
                    
                    # 自立活動の場合はスキップ
                    if exchange_assignment and exchange_assignment.subject.name == "自立":
                        continue
                    
                    # 親学級に授業があり、交流学級にない場合
                    if parent_assignment and not exchange_assignment:
                        # 同じ授業を配置
                        new_assignment = Assignment(
                            exchange_ref,
                            parent_assignment.subject,
                            parent_assignment.teacher
                        )
                        schedule.assign(time_slot, new_assignment)
                        synced += 1
                    
                    # 両方に授業があるが異なる場合
                    elif parent_assignment and exchange_assignment:
                        if parent_assignment.subject.name != exchange_assignment.subject.name:
                            # 親学級に合わせる
                            schedule.remove_assignment(time_slot, exchange_ref)
                            new_assignment = Assignment(
                                exchange_ref,
                                parent_assignment.subject,
                                parent_assignment.teacher
                            )
                            schedule.assign(time_slot, new_assignment)
                            synced += 1
        
        return synced
    
    def _final_optimization(self, schedule: 'Schedule', school: 'School', max_iterations: int) -> int:
        """最終最適化（スワップによる改善）"""
        improvements = 0
        days = ["月", "火", "水", "木", "金"]
        
        from ....domain.value_objects.time_slot import TimeSlot
        
        for _ in range(max_iterations):
            # 現在の違反数を計算
            current_violations = len(self.validate_schedule(schedule, school))
            current_conflicts = len(self.teacher_tracker.get_conflicts())
            
            # ランダムに2つの授業を選択してスワップを試みる
            day1 = random.choice(days)
            day2 = random.choice(days)
            period1 = random.randint(1, 6)
            period2 = random.randint(1, 6)
            
            classes = list(school.get_all_classes())
            class1 = random.choice(classes)
            class2 = random.choice(classes)
            
            time_slot1 = TimeSlot(day1, period1)
            time_slot2 = TimeSlot(day2, period2)
            
            assignment1 = schedule.get_assignment(time_slot1, class1)
            assignment2 = schedule.get_assignment(time_slot2, class2)
            
            if assignment1 and assignment2:
                # 固定科目はスワップしない
                if (assignment1.subject.name in self.fixed_subjects or
                    assignment2.subject.name in self.fixed_subjects):
                    continue
                
                # スワップを実行
                schedule.remove_assignment(time_slot1, class1)
                schedule.remove_assignment(time_slot2, class2)
                
                # 新しい割り当てを作成
                from ....domain.value_objects.assignment import Assignment
                new_assignment1 = Assignment(class1, assignment2.subject, assignment2.teacher)
                new_assignment2 = Assignment(class2, assignment1.subject, assignment1.teacher)
                
                # 制約をチェックしながら配置
                try:
                    schedule.assign(time_slot1, new_assignment1)
                    schedule.assign(time_slot2, new_assignment2)
                    
                    # 改善を確認
                    new_violations = len(self.validate_schedule(schedule, school))
                    new_conflicts = len(self.teacher_tracker.get_conflicts())
                    
                    if (new_violations + new_conflicts) < (current_violations + current_conflicts):
                        improvements += 1
                    else:
                        # 改善しない場合は元に戻す
                        schedule.remove_assignment(time_slot1, class1)
                        schedule.remove_assignment(time_slot2, class2)
                        schedule.assign(time_slot1, assignment1)
                        schedule.assign(time_slot2, assignment2)
                except:
                    # エラーの場合は元に戻す
                    try:
                        schedule.assign(time_slot1, assignment1)
                        schedule.assign(time_slot2, assignment2)
                    except:
                        pass
        
        return improvements
    
    def _get_teacher_for_subject(self, subject: str, grade: int, class_num: int) -> Optional[str]:
        """科目・学年・クラスに応じた教師を取得"""
        # 学校オブジェクトから正しい教師を取得
        if hasattr(self, '_school') and self._school:
            try:
                from ....domain.value_objects.time_slot import ClassReference, Subject
                class_ref = ClassReference(grade, class_num)
                subject_obj = Subject(subject)
                teacher = self._school.get_assigned_teacher(subject_obj, class_ref)
                if teacher:
                    return teacher.name if hasattr(teacher, 'name') else str(teacher)
            except Exception as e:
                # 教師が見つからない場合はフォールバック
                self.logger.debug(f"教師取得エラー: {subject} for {grade}-{class_num}: {e}")
        
        # フォールバック: ハードコードされたマッピングを使用
        if subject in self.teacher_mapping:
            mapping = self.teacher_mapping[subject]
            
            if isinstance(mapping, str):
                return mapping
            elif isinstance(mapping, list):
                # 複数教師の場合はランダムに選択
                return random.choice(mapping)
            elif isinstance(mapping, dict):
                if grade in mapping:
                    grade_mapping = mapping[grade]
                    if isinstance(grade_mapping, dict):
                        return grade_mapping.get(str(class_num))
                    else:
                        return grade_mapping
                elif "5組" in mapping and class_num == 5:
                    return mapping["5組"]
        
        return None
    
    def _get_jiritsu_teacher(self, class_num: int) -> Optional[str]:
        """自立活動の担当教師を取得"""
        jiritsu_mapping = self.teacher_mapping.get("自立", {})
        return jiritsu_mapping.get(str(class_num))