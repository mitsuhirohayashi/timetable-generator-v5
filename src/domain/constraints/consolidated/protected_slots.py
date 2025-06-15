"""保護スロット制約 - 固定教科、会議時間、テスト期間などの保護"""
from typing import Dict, Set, List, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
import csv
import json

from .base import (
    ConfigurableConstraint, ConstraintConfig, ConstraintType, 
    ConstraintPriority, ProtectionLevel, ValidationContext, 
    ConstraintResult, ConstraintViolation
)
from ...value_objects.time_slot import TimeSlot, ClassReference
from ...value_objects.subject_validator import SubjectValidator
from ....infrastructure.config.path_config import path_config


@dataclass
class ProtectedSlot:
    """保護されたスロット"""
    time_slot: TimeSlot
    class_ref: ClassReference
    subject: str
    protection_level: ProtectionLevel
    reason: str


@dataclass
class ForbiddenSubject:
    """特定セルで禁止される教科"""
    time_slot: TimeSlot
    class_ref: ClassReference
    forbidden_subjects: Set[str]
    reason: str


class ProtectedSlotConstraint(ConfigurableConstraint):
    """保護スロット統合制約
    
    以下の制約を統合:
    - FixedSubjectConstraint: 固定教科の保護
    - FixedSubjectLockConstraint: input.csvの位置保持
    - MondaySixthPeriodConstraint: 月曜6限の欠課
    - PlacementForbiddenConstraint: 配置禁止
    - CellForbiddenSubjectConstraint: セル別禁止教科
    - MeetingLockConstraint: 会議時間の保護
    - TestPeriodExclusionConstraint: テスト期間
    """
    
    def __init__(self, initial_schedule=None):
        config = ConstraintConfig(
            name="保護スロット制約",
            description="固定教科、会議時間、特殊ルールなど、変更不可または制限のあるスロットの保護",
            type=ConstraintType.HARD,
            priority=ConstraintPriority.CRITICAL
        )
        super().__init__(config)
        
        self.initial_schedule = initial_schedule
        self.subject_validator = SubjectValidator()
        
        # 保護スロットと禁止教科の辞書
        self.protected_slots: Dict[Tuple[TimeSlot, ClassReference], ProtectedSlot] = {}
        self.forbidden_subjects: Dict[Tuple[TimeSlot, ClassReference], ForbiddenSubject] = {}
        
        # 固定教科のセット
        self.fixed_subjects = set()
        
        # 会議情報
        self.meeting_slots: Dict[str, Tuple[TimeSlot, Set[str]]] = {}  # 会議名 -> (時間, 参加者)
        
    def _load_configuration(self):
        """設定を読み込む"""
        self._load_fixed_subjects()
        self._load_system_rules()
        self._load_meeting_info()
        self._load_forbidden_cells()
        self._load_initial_schedule_locks()
        
    def _load_fixed_subjects(self):
        """固定教科を読み込む"""
        # システム定義の固定教科
        self.fixed_subjects = {
            '欠', '欠課', 'YT', '学', '学活', '総', '総合', 
            '道', '道徳', '学総', '行', '行事'
        }
        
        # valid_subjects.csvから追加の固定教科を読み込む
        valid_subjects_path = path_config.config_dir / "valid_subjects.csv"
        if valid_subjects_path.exists():
            try:
                with open(valid_subjects_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get('固定', '').lower() in ['true', '1', 'yes', '○']:
                            self.fixed_subjects.add(row['教科名'])
                            if '略称' in row and row['略称']:
                                self.fixed_subjects.add(row['略称'])
            except Exception as e:
                self.logger.error(f"固定教科の読み込みエラー: {e}")
    
    def _load_system_rules(self):
        """システムルールを読み込む"""
        # 月曜6限は全クラス欠課
        for grade in range(1, 4):  # 1-3年
            for class_num in range(1, 8):  # 1-7組
                time_slot = TimeSlot(day="月", period=6)
                class_ref = ClassReference(grade=grade, class_number=class_num)
                key = (time_slot, class_ref)
                
                self.protected_slots[key] = ProtectedSlot(
                    time_slot=time_slot,
                    class_ref=class_ref,
                    subject="欠",
                    protection_level=ProtectionLevel.ABSOLUTE,
                    reason="月曜6限は全クラス欠課"
                )
        
        # 火水金6限のYT
        yt_days = ["火", "水", "金"]
        for day in yt_days:
            for grade in range(1, 4):
                for class_num in range(1, 8):
                    time_slot = TimeSlot(day=day, period=6)
                    class_ref = ClassReference(grade=grade, class_number=class_num)
                    key = (time_slot, class_ref)
                    
                    # 5組以外はYT
                    if class_num != 5:
                        self.protected_slots[key] = ProtectedSlot(
                            time_slot=time_slot,
                            class_ref=class_ref,
                            subject="YT",
                            protection_level=ProtectionLevel.STRONG,
                            reason=f"{day}曜6限はYT"
                        )
    
    def _load_meeting_info(self):
        """会議情報を読み込む"""
        # デフォルトの会議時間
        default_meetings = {
            "HF": (TimeSlot(day="火", period=4), {"校長", "副校長", "教頭", "主幹"}),
            "企画": (TimeSlot(day="火", period=3), {"校長", "副校長", "主幹", "各主任"}),
            "特会": (TimeSlot(day="水", period=2), {"特別支援担当"}),
            "生指": (TimeSlot(day="木", period=3), {"生活指導担当"})
        }
        
        # meeting_members.csvから読み込み
        meeting_members_path = path_config.config_dir / "meeting_members.csv"
        if meeting_members_path.exists():
            try:
                with open(meeting_members_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        meeting_name = row.get('会議名', '')
                        day = row.get('曜日', '')
                        period = int(row.get('時限', 0))
                        members = set(row.get('参加者', '').split('、'))
                        
                        if meeting_name and day and period:
                            time_slot = TimeSlot(day=day, period=period)
                            self.meeting_slots[meeting_name] = (time_slot, members)
            except Exception as e:
                self.logger.warning(f"会議情報の読み込みエラー: {e}")
                # デフォルトを使用
                self.meeting_slots = default_meetings
        else:
            self.meeting_slots = default_meetings
    
    def _load_forbidden_cells(self):
        """セル別禁止教科を読み込む"""
        # input.csvから「非○○」の記載を読み込む
        if self.initial_schedule:
            for time_slot in self.initial_schedule.all_time_slots:
                for class_ref in self.initial_schedule.all_classes:
                    assignment = self.initial_schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject and assignment.subject.name.startswith('非'):
                        # 「非英」なら英語を禁止
                        forbidden_subject = assignment.subject.name[1:]
                        key = (time_slot, class_ref)
                        
                        if key not in self.forbidden_subjects:
                            self.forbidden_subjects[key] = ForbiddenSubject(
                                time_slot=time_slot,
                                class_ref=class_ref,
                                forbidden_subjects=set(),
                                reason="input.csvで指定"
                            )
                        
                        self.forbidden_subjects[key].forbidden_subjects.add(forbidden_subject)
    
    def _load_initial_schedule_locks(self):
        """初期スケジュールの固定教科をロック"""
        if not self.initial_schedule:
            return
            
        for time_slot in self.initial_schedule.all_time_slots:
            for class_ref in self.initial_schedule.all_classes:
                assignment = self.initial_schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject:
                    subject_name = assignment.subject.name
                    
                    # 固定教科の場合はロック
                    if subject_name in self.fixed_subjects:
                        key = (time_slot, class_ref)
                        if key not in self.protected_slots:
                            self.protected_slots[key] = ProtectedSlot(
                                time_slot=time_slot,
                                class_ref=class_ref,
                                subject=subject_name,
                                protection_level=ProtectionLevel.ABSOLUTE,
                                reason=f"固定教科（{subject_name}）"
                            )
    
    def validate(self, context: ValidationContext) -> ConstraintResult:
        """制約を検証する"""
        result = ConstraintResult(constraint_name=self.name)
        
        # 保護スロットの検証
        self._validate_protected_slots(context, result)
        
        # 禁止教科の検証
        self._validate_forbidden_subjects(context, result)
        
        # 会議時間の検証
        self._validate_meeting_times(context, result)
        
        # 固定教科の移動検証
        self._validate_fixed_subject_movements(context, result)
        
        return result
    
    def _validate_protected_slots(self, context: ValidationContext, result: ConstraintResult):
        """保護スロットの検証"""
        for (time_slot, class_ref), protected in self.protected_slots.items():
            assignment = context.get_assignment_at(time_slot, class_ref)
            
            if assignment and assignment.subject:
                current_subject = assignment.subject.name
                
                # 保護された教科と異なる場合
                if current_subject != protected.subject:
                    severity = "ERROR" if protected.protection_level == ProtectionLevel.ABSOLUTE else "WARNING"
                    
                    violation = ConstraintViolation(
                        constraint_name=self.name,
                        severity=severity,
                        message=f"{class_ref} {time_slot}: {protected.subject}であるべきところ{current_subject}が配置されています（{protected.reason}）",
                        time_slot=time_slot,
                        class_ref=class_ref,
                        subject=current_subject
                    )
                    result.add_violation(violation)
    
    def _validate_forbidden_subjects(self, context: ValidationContext, result: ConstraintResult):
        """禁止教科の検証"""
        for (time_slot, class_ref), forbidden in self.forbidden_subjects.items():
            assignment = context.get_assignment_at(time_slot, class_ref)
            
            if assignment and assignment.subject:
                current_subject = assignment.subject.name
                
                # 禁止教科が配置されている場合
                if current_subject in forbidden.forbidden_subjects:
                    violation = ConstraintViolation(
                        constraint_name=self.name,
                        severity="ERROR",
                        message=f"{class_ref} {time_slot}: {current_subject}は配置禁止です（{forbidden.reason}）",
                        time_slot=time_slot,
                        class_ref=class_ref,
                        subject=current_subject
                    )
                    result.add_violation(violation)
    
    def _validate_meeting_times(self, context: ValidationContext, result: ConstraintResult):
        """会議時間の検証"""
        for meeting_name, (time_slot, members) in self.meeting_slots.items():
            assignments = context.get_assignments_by_time(time_slot)
            
            for assignment in assignments:
                if assignment.teacher and assignment.teacher.name in members:
                    violation = ConstraintViolation(
                        constraint_name=self.name,
                        severity="ERROR",
                        message=f"{assignment.teacher.name}は{time_slot}に{meeting_name}があるため授業できません",
                        time_slot=time_slot,
                        class_ref=assignment.class_ref,
                        teacher=assignment.teacher.name
                    )
                    result.add_violation(violation)
    
    def _validate_fixed_subject_movements(self, context: ValidationContext, result: ConstraintResult):
        """固定教科の移動を検証"""
        if not self.initial_schedule:
            return
            
        for time_slot in context.schedule.all_time_slots:
            for class_ref in context.schedule.all_classes:
                initial_assignment = self.initial_schedule.get_assignment(time_slot, class_ref)
                current_assignment = context.get_assignment_at(time_slot, class_ref)
                
                # 初期配置に固定教科があった場合
                if initial_assignment and initial_assignment.subject:
                    initial_subject = initial_assignment.subject.name
                    
                    if initial_subject in self.fixed_subjects:
                        # 現在の配置と異なる場合
                        if not current_assignment or not current_assignment.subject or \
                           current_assignment.subject.name != initial_subject:
                            current_subject = current_assignment.subject.name if current_assignment and current_assignment.subject else "空き"
                            
                            violation = ConstraintViolation(
                                constraint_name=self.name,
                                severity="ERROR",
                                message=f"{class_ref} {time_slot}: 固定教科{initial_subject}が{current_subject}に変更されています",
                                time_slot=time_slot,
                                class_ref=class_ref,
                                subject=current_subject
                            )
                            result.add_violation(violation)
    
    def check_assignment(self, context: ValidationContext) -> bool:
        """配置前チェック"""
        if not context.time_slot or not context.class_ref:
            return True
            
        key = (context.time_slot, context.class_ref)
        
        # 保護スロットのチェック
        if key in self.protected_slots:
            protected = self.protected_slots[key]
            if protected.protection_level == ProtectionLevel.ABSOLUTE:
                # 絶対保護の場合、指定された教科以外は配置不可
                if context.subject != protected.subject:
                    self.logger.debug(f"保護スロット: {context.subject}は配置できません（{protected.subject}のみ）")
                    return False
        
        # 禁止教科のチェック
        if key in self.forbidden_subjects:
            forbidden = self.forbidden_subjects[key]
            if context.subject in forbidden.forbidden_subjects:
                self.logger.debug(f"禁止教科: {context.subject}は{key}に配置できません")
                return False
        
        # 会議時間のチェック
        if context.teacher:
            for meeting_name, (meeting_time, members) in self.meeting_slots.items():
                if context.time_slot == meeting_time and context.teacher in members:
                    self.logger.debug(f"会議時間: {context.teacher}は{meeting_name}のため配置不可")
                    return False
        
        # 固定教科の移動チェック
        if self.initial_schedule and context.subject in self.fixed_subjects:
            # この教科が初期配置された場所を探す
            for ts in self.initial_schedule.all_time_slots:
                for cr in self.initial_schedule.all_classes:
                    assignment = self.initial_schedule.get_assignment(ts, cr)
                    if assignment and assignment.subject and assignment.subject.name == context.subject:
                        # 同じクラスの同じ時間でない場合は配置不可
                        if (ts, cr) != (context.time_slot, context.class_ref):
                            self.logger.debug(f"固定教科: {context.subject}は移動できません")
                            return False
        
        return True
    
    def is_protected_slot(self, time_slot: TimeSlot, class_ref: ClassReference) -> bool:
        """指定されたスロットが保護されているかチェック"""
        key = (time_slot, class_ref)
        return key in self.protected_slots
    
    def get_protection_level(self, time_slot: TimeSlot, class_ref: ClassReference) -> Optional[ProtectionLevel]:
        """指定されたスロットの保護レベルを取得"""
        key = (time_slot, class_ref)
        if key in self.protected_slots:
            return self.protected_slots[key].protection_level
        return None
    
    def get_required_subject(self, time_slot: TimeSlot, class_ref: ClassReference) -> Optional[str]:
        """指定されたスロットに必要な教科を取得"""
        key = (time_slot, class_ref)
        if key in self.protected_slots:
            return self.protected_slots[key].subject
        return None