"""技術・家庭科（技家）の特別処理サービス

技家は技術科と家庭科の合併授業を表し、以下の特別な処理が必要：
1. 複数教師が同じ時間に複数クラスで教える場合の割り振り
2. 技術教師と家庭科教師の適切な配分
3. 物理的に不可能な配置の防止
"""
from typing import Dict, List, Optional, Tuple
from ....shared.mixins.logging_mixin import LoggingMixin
from ...entities.school import School
from ...entities.schedule import Schedule
from ...value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ...value_objects.assignment import Assignment


class TechHomeHandler(LoggingMixin):
    """技術・家庭科の特別処理を行うサービス"""
    
    def __init__(self):
        super().__init__()
        # 技家の教師タイプマッピング
        self.tech_teachers = []  # 技術科教師のリスト
        self.home_teachers = []  # 家庭科教師のリスト
        self.assignment_map: Dict[Tuple[TimeSlot, Teacher], List[ClassReference]] = {}
    
    def can_assign_techome(
        self, 
        schedule: Schedule, 
        school: School, 
        time_slot: TimeSlot, 
        class_ref: ClassReference,
        subject: Subject
    ) -> Optional[Teacher]:
        """技家を配置可能か判定し、可能な場合は適切な教師を返す
        
        Args:
            schedule: 現在のスケジュール
            school: 学校情報
            time_slot: 配置しようとする時間枠
            class_ref: 配置しようとするクラス
            subject: 教科（技家）
            
        Returns:
            配置可能な教師、不可能な場合はNone
        """
        if subject.name != "技家":
            return None
            
        # その時間に技家が配置されているクラスを収集
        techome_classes = []
        for cls in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, cls)
            if assignment and assignment.subject.name == "技家":
                techome_classes.append(cls)
        
        # まだ配置されていない場合は、技術または家庭科教師を割り当て
        if not techome_classes:
            # 技術科教師を優先的に割り当て
            tech_teacher = school.get_assigned_teacher(Subject("技"), class_ref)
            if tech_teacher and self._is_teacher_available(schedule, school, time_slot, tech_teacher):
                return tech_teacher
            
            # 家庭科教師を試す
            home_teacher = school.get_assigned_teacher(Subject("家"), class_ref)
            if home_teacher and self._is_teacher_available(schedule, school, time_slot, home_teacher):
                return home_teacher
            
            return None
        
        # 既に技家が配置されている場合
        # 同じ時間の技家授業数をカウント
        techome_count = len(techome_classes) + 1  # 今配置しようとしているクラスも含む
        
        # 技術・家庭科教師の配分を計算
        return self._allocate_teacher_for_techome(
            schedule, school, time_slot, class_ref, techome_count, techome_classes
        )
    
    def _allocate_teacher_for_techome(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        total_count: int,
        existing_classes: List[ClassReference]
    ) -> Optional[Teacher]:
        """技家の教師を適切に配分する
        
        同じ時間に複数クラスで技家がある場合、技術教師と家庭科教師を
        適切に配分する。例：5クラスなら技術3、家庭科2など。
        """
        # 既存の教師割り当てを確認
        tech_count = 0
        home_count = 0
        
        for cls in existing_classes:
            assignment = schedule.get_assignment(time_slot, cls)
            if assignment and assignment.teacher:
                # 教師名から技術/家庭科を判定（簡易版）
                if "技" in assignment.teacher.name or assignment.teacher == school.get_assigned_teacher(Subject("技"), cls):
                    tech_count += 1
                elif "家" in assignment.teacher.name or assignment.teacher == school.get_assigned_teacher(Subject("家"), cls):
                    home_count += 1
        
        # 配分を決定（技術教師を優先、半分以上を技術に）
        tech_target = (total_count + 1) // 2
        home_target = total_count - tech_target
        
        # 技術教師がまだ足りない場合
        if tech_count < tech_target:
            tech_teacher = school.get_assigned_teacher(Subject("技"), class_ref)
            if tech_teacher and self._is_teacher_available_for_techome(
                schedule, school, time_slot, tech_teacher, tech_count + 1
            ):
                return tech_teacher
        
        # 家庭科教師を割り当て
        if home_count < home_target:
            home_teacher = school.get_assigned_teacher(Subject("家"), class_ref)
            if home_teacher and self._is_teacher_available_for_techome(
                schedule, school, time_slot, home_teacher, home_count + 1
            ):
                return home_teacher
        
        # どちらも配置できない場合
        self.logger.warning(
            f"技家配置失敗: {time_slot} {class_ref} "
            f"(技術{tech_count}/{tech_target}, 家庭科{home_count}/{home_target})"
        )
        return None
    
    def _is_teacher_available(
        self, 
        schedule: Schedule, 
        school: School, 
        time_slot: TimeSlot, 
        teacher: Teacher
    ) -> bool:
        """教師が利用可能か判定（通常の授業用）"""
        # 既に他の授業を担当していないか
        for cls in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, cls)
            if assignment and assignment.teacher == teacher:
                return False
        
        # 教師の不在チェック
        if school.is_teacher_unavailable(time_slot.day, time_slot.period, teacher):
            return False
        
        return True
    
    def _is_teacher_available_for_techome(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        teacher: Teacher,
        max_classes: int
    ) -> bool:
        """技家授業での教師の利用可能性を判定
        
        技家の場合、1人の教師が複数クラスを巡回指導できるが、
        物理的な限界（最大3クラス程度）を考慮する。
        """
        # 既に担当しているクラス数を確認
        current_count = 0
        for cls in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, cls)
            if assignment and assignment.teacher == teacher:
                current_count += 1
        
        # 物理的な限界を超えていないか
        if current_count >= max_classes:
            return False
        
        # 教師の不在チェック
        if school.is_teacher_unavailable(time_slot.day, time_slot.period, teacher):
            return False
        
        return True
    
    def validate_techome_assignments(
        self, 
        schedule: Schedule, 
        school: School
    ) -> List[str]:
        """技家の配置を検証し、問題があれば報告する
        
        Returns:
            問題のリスト
        """
        issues = []
        
        # 各時間枠での技家配置を確認
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 技家を配置しているクラスと教師を収集
                techome_assignments = []
                teacher_counts = {}
                
                for cls in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, cls)
                    if assignment and assignment.subject.name == "技家":
                        techome_assignments.append((cls, assignment.teacher))
                        if assignment.teacher:
                            teacher_counts[assignment.teacher] = teacher_counts.get(assignment.teacher, 0) + 1
                
                # 教師の過負荷をチェック
                for teacher, count in teacher_counts.items():
                    if count > 3:  # 物理的に3クラス以上は困難
                        issues.append(
                            f"{day}{period}限: {teacher.name}先生が技家を{count}クラス担当 "
                            f"（物理的に困難）"
                        )
                
                # 5クラス以上の技家は要注意
                if len(techome_assignments) >= 5:
                    unique_teachers = len(set(t for _, t in techome_assignments if t))
                    if unique_teachers < 2:
                        issues.append(
                            f"{day}{period}限: 技家が{len(techome_assignments)}クラスあるが、"
                            f"教師が{unique_teachers}人のみ（最低2人必要）"
                        )
        
        return issues