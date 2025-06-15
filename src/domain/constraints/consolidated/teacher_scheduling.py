"""教師スケジューリング制約 - 教師の重複、不在、勤務時間などの統合管理"""
from typing import Dict, Set, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path
import csv

from .base import (
    ConfigurableConstraint, ConstraintConfig, ConstraintType,
    ConstraintPriority, ValidationContext, ConstraintResult, ConstraintViolation
)
from ...value_objects.time_slot import TimeSlot, ClassReference, Teacher
from ...services.team_teaching_service import get_team_teaching_service
from ....infrastructure.config.path_config import path_config


@dataclass
class TeacherAvailability:
    """教師の利用可能性情報"""
    teacher_name: str
    available_slots: Set[Tuple[str, int]]  # (day, period)のセット
    absence_slots: Set[Tuple[str, int]]   # 不在時間
    meeting_slots: Set[Tuple[str, int]]   # 会議時間
    max_daily_hours: int = 6              # 1日の最大授業時数
    max_weekly_hours: int = 25            # 週の最大授業時数


@dataclass 
class TeamTeachingInfo:
    """チームティーチング情報"""
    classes: Set[ClassReference]
    teachers: Set[str]
    subject: str
    allow_simultaneous: bool = True


class TeacherSchedulingConstraint(ConfigurableConstraint):
    """教師スケジューリング統合制約
    
    以下の制約を統合:
    - TeacherConflictConstraint: 教師の重複防止
    - TeacherAvailabilityConstraint: 教師の利用可能性
    - TeacherAbsenceConstraint: 教師の不在
    - PartTimeTeacherConstraint: 非常勤講師の時間制限
    - MeetingLockConstraint（教師側）: 会議による制限
    """
    
    def __init__(self):
        config = ConstraintConfig(
            name="教師スケジューリング制約",
            description="教師の重複防止、勤務時間、不在情報などの統合管理",
            type=ConstraintType.HARD,
            priority=ConstraintPriority.CRITICAL
        )
        super().__init__(config)
        
        # 教師の利用可能性情報
        self.teacher_availability: Dict[str, TeacherAvailability] = {}
        
        # チームティーチング情報
        self.team_teaching_info: List[TeamTeachingInfo] = []
        
        # 特殊な教師（複数クラス同時担当可能）
        self.special_teachers = {"欠課", "YT担当", "道担当"}
        
        # チームティーチングサービス
        self.tt_service = get_team_teaching_service()
        
    def _load_configuration(self):
        """設定を読み込む"""
        self._load_teacher_basic_info()
        self._load_part_time_teachers()
        self._load_teacher_absences()
        self._load_meeting_participants()
        self._load_team_teaching_config()
        
    def _load_teacher_basic_info(self):
        """教師の基本情報を読み込む"""
        # デフォルトで全教師は全時間利用可能
        all_slots = set()
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                all_slots.add((day, period))
        
        # teacher_subject_mapping.csvから教師リストを取得
        teacher_mapping_path = path_config.config_dir / "teacher_subject_mapping.csv"
        if teacher_mapping_path.exists():
            try:
                with open(teacher_mapping_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        teacher_name = row.get('教師名', '')
                        if teacher_name and teacher_name not in self.teacher_availability:
                            self.teacher_availability[teacher_name] = TeacherAvailability(
                                teacher_name=teacher_name,
                                available_slots=all_slots.copy(),
                                absence_slots=set(),
                                meeting_slots=set()
                            )
            except Exception as e:
                self.logger.error(f"教師情報の読み込みエラー: {e}")
    
    def _load_part_time_teachers(self):
        """非常勤講師の情報を読み込む"""
        part_time_path = path_config.config_dir / "part_time_teachers.csv"
        if part_time_path.exists():
            try:
                with open(part_time_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        teacher_name = row.get('教師名', '')
                        available_days = row.get('勤務曜日', '').split('、')
                        available_periods = row.get('勤務時限', '').split('、')
                        
                        if teacher_name:
                            # 利用可能な時間を設定
                            available_slots = set()
                            for day in available_days:
                                for period_str in available_periods:
                                    try:
                                        if '-' in period_str:
                                            start, end = map(int, period_str.split('-'))
                                            for p in range(start, end + 1):
                                                available_slots.add((day, p))
                                        else:
                                            period = int(period_str)
                                            available_slots.add((day, period))
                                    except:
                                        pass
                            
                            if teacher_name not in self.teacher_availability:
                                self.teacher_availability[teacher_name] = TeacherAvailability(
                                    teacher_name=teacher_name,
                                    available_slots=available_slots,
                                    absence_slots=set(),
                                    meeting_slots=set()
                                )
                            else:
                                self.teacher_availability[teacher_name].available_slots = available_slots
            except Exception as e:
                self.logger.warning(f"非常勤講師情報の読み込みエラー: {e}")
        
        # ハードコードされた青井先生の情報（フォールバック）
        if "青井" not in self.teacher_availability:
            aoi_slots = set()
            for day, periods in [("月", [1,2,3]), ("水", [1,2,3]), ("金", [1,2,3])]:
                for period in periods:
                    aoi_slots.add((day, period))
            
            self.teacher_availability["青井"] = TeacherAvailability(
                teacher_name="青井",
                available_slots=aoi_slots,
                absence_slots=set(),
                meeting_slots=set()
            )
    
    def _load_teacher_absences(self):
        """教師の不在情報を読み込む"""
        # Follow-up.csvから読み込む処理
        followup_path = path_config.input_dir / "Follow-up.csv"
        if followup_path.exists():
            try:
                from ....infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
                loader = TeacherAbsenceLoader()
                absences = loader.load_teacher_absences()
                
                for absence in absences:
                    teacher_name = absence['teacher']
                    day = absence['day']
                    period = absence['period']
                    
                    if teacher_name in self.teacher_availability:
                        self.teacher_availability[teacher_name].absence_slots.add((day, period))
            except Exception as e:
                self.logger.warning(f"教師不在情報の読み込みエラー: {e}")
    
    def _load_meeting_participants(self):
        """会議参加者情報を読み込む"""
        meeting_members_path = path_config.config_dir / "meeting_members.csv"
        if meeting_members_path.exists():
            try:
                with open(meeting_members_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        day = row.get('曜日', '')
                        period_str = row.get('時限', '')
                        members = row.get('参加者', '').split('、')
                        
                        if day and period_str:
                            try:
                                period = int(period_str)
                                for member in members:
                                    member = member.strip()
                                    if member in self.teacher_availability:
                                        self.teacher_availability[member].meeting_slots.add((day, period))
                            except:
                                pass
            except Exception as e:
                self.logger.warning(f"会議参加者情報の読み込みエラー: {e}")
    
    def _load_team_teaching_config(self):
        """チームティーチング設定を読み込む"""
        # Grade 5のチームティーチング
        grade5_teachers = set()
        grade5_tt_path = path_config.config_dir / "grade5_team_teaching.csv"
        if grade5_tt_path.exists():
            try:
                with open(grade5_tt_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        teacher = row.get('教師名', '')
                        if teacher:
                            grade5_teachers.add(teacher)
            except:
                pass
        
        if grade5_teachers:
            self.team_teaching_info.append(TeamTeachingInfo(
                classes={ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)},
                teachers=grade5_teachers,
                subject="*",  # 全教科
                allow_simultaneous=True
            ))
        
        # その他のチームティーチング設定をteam_teaching_config.jsonから読み込む
        tt_config_path = path_config.config_dir / "team_teaching_config.json"
        if tt_config_path.exists():
            try:
                import json
                with open(tt_config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 設定を解析してTeamTeachingInfoに変換
                    # （実装は設定ファイルの形式に依存）
            except:
                pass
    
    def validate(self, context: ValidationContext) -> ConstraintResult:
        """制約を検証する"""
        result = ConstraintResult(constraint_name=self.name)
        
        # 教師の重複をチェック
        self._validate_teacher_conflicts(context, result)
        
        # 教師の利用可能性をチェック
        self._validate_teacher_availability(context, result)
        
        # 教師の負荷をチェック（ソフト制約）
        self._validate_teacher_workload(context, result)
        
        return result
    
    def _validate_teacher_conflicts(self, context: ValidationContext, result: ConstraintResult):
        """教師の重複をチェック"""
        # 時間ごとの教師割り当てを収集
        time_teacher_assignments = defaultdict(lambda: defaultdict(list))
        
        for time_slot in context.schedule.all_time_slots:
            assignments = context.get_assignments_by_time(time_slot)
            
            for assignment in assignments:
                if assignment.teacher:
                    teacher_name = assignment.teacher.name
                    
                    # 特殊な教師はスキップ
                    if teacher_name in self.special_teachers:
                        continue
                    
                    # チームティーチングの場合は特別処理
                    if self._is_team_teaching_assignment(assignment, time_slot):
                        continue
                    
                    time_teacher_assignments[time_slot][teacher_name].append(assignment)
        
        # 重複をチェック
        for time_slot, teacher_assignments in time_teacher_assignments.items():
            for teacher_name, assignments in teacher_assignments.items():
                if len(assignments) > 1:
                    # 重複が発生
                    classes = [a.class_ref for a in assignments]
                    violation = ConstraintViolation(
                        constraint_name=self.name,
                        severity="ERROR",
                        message=f"{teacher_name}が{time_slot}に複数クラス{classes}を担当しています",
                        time_slot=time_slot,
                        teacher=teacher_name
                    )
                    result.add_violation(violation)
    
    def _validate_teacher_availability(self, context: ValidationContext, result: ConstraintResult):
        """教師の利用可能性をチェック"""
        for time_slot in context.schedule.all_time_slots:
            assignments = context.get_assignments_by_time(time_slot)
            slot_key = (time_slot.day, time_slot.period)
            
            for assignment in assignments:
                if assignment.teacher:
                    teacher_name = assignment.teacher.name
                    
                    if teacher_name in self.teacher_availability:
                        availability = self.teacher_availability[teacher_name]
                        
                        # 利用可能時間外
                        if slot_key not in availability.available_slots:
                            violation = ConstraintViolation(
                                constraint_name=self.name,
                                severity="ERROR",
                                message=f"{teacher_name}は{time_slot}に勤務時間外です",
                                time_slot=time_slot,
                                class_ref=assignment.class_ref,
                                teacher=teacher_name
                            )
                            result.add_violation(violation)
                        
                        # 不在時間
                        elif slot_key in availability.absence_slots:
                            violation = ConstraintViolation(
                                constraint_name=self.name,
                                severity="ERROR",
                                message=f"{teacher_name}は{time_slot}に不在です",
                                time_slot=time_slot,
                                class_ref=assignment.class_ref,
                                teacher=teacher_name
                            )
                            result.add_violation(violation)
                        
                        # 会議時間
                        elif slot_key in availability.meeting_slots:
                            violation = ConstraintViolation(
                                constraint_name=self.name,
                                severity="ERROR",
                                message=f"{teacher_name}は{time_slot}に会議があります",
                                time_slot=time_slot,
                                class_ref=assignment.class_ref,
                                teacher=teacher_name
                            )
                            result.add_violation(violation)
    
    def _validate_teacher_workload(self, context: ValidationContext, result: ConstraintResult):
        """教師の負荷をチェック（ソフト制約）"""
        # 教師ごとの授業時数を集計
        teacher_daily_hours = defaultdict(lambda: defaultdict(int))
        teacher_weekly_hours = defaultdict(int)
        
        for time_slot in context.schedule.all_time_slots:
            assignments = context.get_assignments_by_time(time_slot)
            
            for assignment in assignments:
                if assignment.teacher:
                    teacher_name = assignment.teacher.name
                    teacher_daily_hours[teacher_name][time_slot.day] += 1
                    teacher_weekly_hours[teacher_name] += 1
        
        # 負荷をチェック
        for teacher_name in teacher_daily_hours:
            if teacher_name in self.teacher_availability:
                availability = self.teacher_availability[teacher_name]
                
                # 日ごとの最大時数チェック
                for day, hours in teacher_daily_hours[teacher_name].items():
                    if hours > availability.max_daily_hours:
                        violation = ConstraintViolation(
                            constraint_name=self.name,
                            severity="WARNING",
                            message=f"{teacher_name}の{day}曜日の授業時数が{hours}時間で上限を超えています",
                            teacher=teacher_name
                        )
                        result.add_violation(violation)
                
                # 週の最大時数チェック
                weekly_hours = teacher_weekly_hours[teacher_name]
                if weekly_hours > availability.max_weekly_hours:
                    violation = ConstraintViolation(
                        constraint_name=self.name,
                        severity="WARNING",
                        message=f"{teacher_name}の週授業時数が{weekly_hours}時間で上限を超えています",
                        teacher=teacher_name
                    )
                    result.add_violation(violation)
    
    def _is_team_teaching_assignment(self, assignment, time_slot: TimeSlot) -> bool:
        """チームティーチングの割り当てかチェック"""
        # TeamTeachingServiceを使用
        if self.tt_service.is_team_teaching_class(assignment.class_ref):
            # 同じ時間の他の5組クラスも同じ教師か確認
            other_assignments = []
            for other_class in self.tt_service.get_team_teaching_group(assignment.class_ref):
                if other_class != assignment.class_ref:
                    other_assignment = assignment.schedule.get_assignment(time_slot, other_class)
                    if other_assignment:
                        other_assignments.append(other_assignment)
            
            # 全て同じ教師なら正当なチームティーチング
            if all(a.teacher and a.teacher.name == assignment.teacher.name for a in other_assignments):
                return True
        
        return False
    
    def check_assignment(self, context: ValidationContext) -> bool:
        """配置前チェック"""
        if not context.teacher or not context.time_slot:
            return True
        
        teacher_name = context.teacher
        time_slot = context.time_slot
        slot_key = (time_slot.day, time_slot.period)
        
        # 特殊な教師は常に配置可能
        if teacher_name in self.special_teachers:
            return True
        
        # 教師の利用可能性チェック
        if teacher_name in self.teacher_availability:
            availability = self.teacher_availability[teacher_name]
            
            # 利用可能時間外
            if slot_key not in availability.available_slots:
                self.logger.debug(f"{teacher_name}は{time_slot}に勤務時間外")
                return False
            
            # 不在時間
            if slot_key in availability.absence_slots:
                self.logger.debug(f"{teacher_name}は{time_slot}に不在")
                return False
            
            # 会議時間
            if slot_key in availability.meeting_slots:
                self.logger.debug(f"{teacher_name}は{time_slot}に会議")
                return False
        
        # 既存の割り当てとの重複チェック
        if context.schedule:
            assignments = context.get_assignments_by_time(time_slot)
            for assignment in assignments:
                if (assignment.teacher and 
                    assignment.teacher.name == teacher_name and
                    assignment.class_ref != context.class_ref):
                    
                    # チームティーチングの場合は許可
                    if (context.class_ref and 
                        self.tt_service.is_valid_team_teaching(
                            teacher_name, 
                            [assignment.class_ref, context.class_ref],
                            context.subject or ""
                        )):
                        return True
                    
                    self.logger.debug(f"{teacher_name}は{time_slot}に既に{assignment.class_ref}を担当")
                    return False
        
        return True
    
    def is_teacher_available(self, teacher_name: str, time_slot: TimeSlot) -> bool:
        """教師が指定時間に利用可能かチェック"""
        slot_key = (time_slot.day, time_slot.period)
        
        if teacher_name in self.special_teachers:
            return True
        
        if teacher_name in self.teacher_availability:
            availability = self.teacher_availability[teacher_name]
            return (slot_key in availability.available_slots and
                    slot_key not in availability.absence_slots and
                    slot_key not in availability.meeting_slots)
        
        return True  # 情報がない場合は利用可能とする
    
    def get_available_teachers(self, time_slot: TimeSlot) -> Set[str]:
        """指定時間に利用可能な教師のリストを取得"""
        available = set()
        slot_key = (time_slot.day, time_slot.period)
        
        for teacher_name, availability in self.teacher_availability.items():
            if (slot_key in availability.available_slots and
                slot_key not in availability.absence_slots and
                slot_key not in availability.meeting_slots):
                available.add(teacher_name)
        
        # 特殊な教師も追加
        available.update(self.special_teachers)
        
        return available