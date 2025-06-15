"""検証制約 - 教科の妥当性、クラス適合性などの検証"""
from typing import Dict, Set, List, Tuple, Optional
from dataclasses import dataclass, field
from pathlib import Path
import csv

from .base import (
    ConfigurableConstraint, ConstraintConfig, ConstraintType,
    ConstraintPriority, ValidationContext, ConstraintResult, ConstraintViolation
)
from ...value_objects.time_slot import TimeSlot, ClassReference
from ...value_objects.subject_validator import SubjectValidator
from ...value_objects.class_validator import ClassValidator
from ....infrastructure.config.path_config import path_config


@dataclass
class SubjectClassRule:
    """教科-クラス適合性ルール"""
    subject: str
    allowed_class_types: Set[str]  # "regular", "special_needs", "grade5"
    forbidden_class_types: Set[str] = field(default_factory=set)
    specific_classes: Set[ClassReference] = field(default_factory=set)  # 特定クラスのみ/除外


@dataclass
class SubjectCombinationRule:
    """教科組み合わせルール"""
    subjects: Set[str]
    rule_type: str  # "forbidden", "required", "recommended"
    context: str = ""  # ルールの文脈（例：「同じ日」「連続」など）


class SubjectValidationConstraint(ConfigurableConstraint):
    """教科検証統合制約
    
    以下の制約を統合:
    - SubjectValidityConstraint: 教科の妥当性（クラスタイプとの適合性）
    - SpecialNeedsDuplicateConstraint: 特別支援クラスの重複制限
    - その他の検証ルール
    """
    
    def __init__(self):
        config = ConstraintConfig(
            name="教科検証制約",
            description="教科の妥当性、クラス適合性、組み合わせルールなどを検証",
            type=ConstraintType.HARD,
            priority=ConstraintPriority.HIGH
        )
        super().__init__(config)
        
        self.subject_validator = SubjectValidator()
        self.class_validator = ClassValidator()
        
        # ルール定義
        self.subject_class_rules: Dict[str, SubjectClassRule] = {}
        self.combination_rules: List[SubjectCombinationRule] = []
        
        # 有効な教科のセット
        self.valid_subjects: Set[str] = set()
        
        # 特別支援クラス専用教科
        self.special_needs_subjects: Set[str] = set()
        
    def _load_configuration(self):
        """設定を読み込む"""
        self._load_valid_subjects()
        self._load_subject_class_rules()
        self._load_combination_rules()
        
    def _load_valid_subjects(self):
        """有効な教科を読み込む"""
        valid_subjects_path = path_config.config_dir / "valid_subjects.csv"
        if valid_subjects_path.exists():
            try:
                with open(valid_subjects_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        subject = row.get('教科名', '')
                        abbreviation = row.get('略称', '')
                        class_type = row.get('クラスタイプ', '')
                        
                        if subject:
                            self.valid_subjects.add(subject)
                            if abbreviation:
                                self.valid_subjects.add(abbreviation)
                            
                            # 特別支援クラス専用教科
                            if class_type == '特別支援':
                                self.special_needs_subjects.add(subject)
                                if abbreviation:
                                    self.special_needs_subjects.add(abbreviation)
                                    
            except Exception as e:
                self.logger.error(f"有効教科の読み込みエラー: {e}")
        
        # デフォルトの有効教科
        default_subjects = {
            # 通常教科
            '国', '国語', '数', '数学', '英', '英語', '理', '理科', '社', '社会',
            '体', '保体', '保健体育', '音', '音楽', '美', '美術', '技', '技術',
            '家', '家庭', '道', '道徳', '学', '学活', '総', '総合',
            # システム教科
            '欠', '欠課', 'YT', '行', '行事',
            # 特別支援教科
            '自立', '自立活動', '日生', '日常生活', '作業'
        }
        self.valid_subjects.update(default_subjects)
        
    def _load_subject_class_rules(self):
        """教科-クラス適合性ルールを読み込む"""
        # 通常学級用教科
        regular_subjects = {
            '国', '国語', '数', '数学', '英', '英語', '理', '理科', '社', '社会',
            '体', '保体', '保健体育', '音', '音楽', '美', '美術', '技', '技術',
            '家', '家庭', '道', '道徳', '学', '学活', '総', '総合'
        }
        
        for subject in regular_subjects:
            self.subject_class_rules[subject] = SubjectClassRule(
                subject=subject,
                allowed_class_types={'regular', 'grade5'},
                forbidden_class_types={'special_needs'}
            )
        
        # 特別支援クラス専用教科
        special_subjects = {'自立', '自立活動', '日生', '日常生活', '作業'}
        
        for subject in special_subjects:
            self.subject_class_rules[subject] = SubjectClassRule(
                subject=subject,
                allowed_class_types={'special_needs'},
                forbidden_class_types={'regular', 'grade5'}
            )
        
        # システム教科（全クラス共通）
        system_subjects = {'欠', '欠課', 'YT', '行', '行事', '総', '総合'}
        
        for subject in system_subjects:
            self.subject_class_rules[subject] = SubjectClassRule(
                subject=subject,
                allowed_class_types={'regular', 'special_needs', 'grade5'}
            )
        
        # 追加ルールを設定ファイルから読み込む
        subject_rules_path = path_config.config_dir / "subject_class_rules.csv"
        if subject_rules_path.exists():
            try:
                with open(subject_rules_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        subject = row.get('教科', '')
                        allowed = set(row.get('許可クラスタイプ', '').split('、'))
                        forbidden = set(row.get('禁止クラスタイプ', '').split('、'))
                        
                        if subject:
                            self.subject_class_rules[subject] = SubjectClassRule(
                                subject=subject,
                                allowed_class_types=allowed,
                                forbidden_class_types=forbidden
                            )
            except Exception as e:
                self.logger.warning(f"教科クラスルールの読み込みエラー: {e}")
                
    def _load_combination_rules(self):
        """教科組み合わせルールを読み込む"""
        # 特別支援クラスでの重複制限
        special_duplicate_rule = SubjectCombinationRule(
            subjects=self.special_needs_subjects,
            rule_type="forbidden",
            context="same_day_multiple"  # 同じ日に複数回は禁止
        )
        self.combination_rules.append(special_duplicate_rule)
        
        # 他の組み合わせルールがあれば追加
        # （必要に応じて設定ファイルから読み込む）
        
    def validate(self, context: ValidationContext) -> ConstraintResult:
        """制約を検証する"""
        result = ConstraintResult(constraint_name=self.name)
        
        # 教科の妥当性を検証
        self._validate_subject_validity(context, result)
        
        # クラス適合性を検証
        self._validate_class_compatibility(context, result)
        
        # 組み合わせルールを検証
        self._validate_combination_rules(context, result)
        
        return result
        
    def _validate_subject_validity(self, context: ValidationContext, result: ConstraintResult):
        """教科の妥当性を検証"""
        for time_slot in context.schedule.all_time_slots:
            for class_ref in context.schedule.all_classes:
                assignment = context.get_assignment_at(time_slot, class_ref)
                
                if assignment and assignment.subject:
                    subject = assignment.subject.name
                    
                    # 有効な教科かチェック
                    if subject not in self.valid_subjects:
                        violation = ConstraintViolation(
                            constraint_name=self.name,
                            severity="ERROR",
                            message=f"{class_ref} {time_slot}: 無効な教科 '{subject}' が配置されています",
                            time_slot=time_slot,
                            class_ref=class_ref,
                            subject=subject
                        )
                        result.add_violation(violation)
                        
    def _validate_class_compatibility(self, context: ValidationContext, result: ConstraintResult):
        """クラス適合性を検証"""
        for time_slot in context.schedule.all_time_slots:
            for class_ref in context.schedule.all_classes:
                assignment = context.get_assignment_at(time_slot, class_ref)
                
                if assignment and assignment.subject:
                    subject = assignment.subject.name
                    
                    # クラスタイプを判定
                    class_type = self._get_class_type(class_ref)
                    
                    # ルールをチェック
                    if subject in self.subject_class_rules:
                        rule = self.subject_class_rules[subject]
                        
                        # 禁止クラスタイプ
                        if class_type in rule.forbidden_class_types:
                            violation = ConstraintViolation(
                                constraint_name=self.name,
                                severity="ERROR",
                                message=f"{class_ref}（{class_type}）に{subject}は配置できません",
                                time_slot=time_slot,
                                class_ref=class_ref,
                                subject=subject
                            )
                            result.add_violation(violation)
                        
                        # 許可クラスタイプ
                        elif rule.allowed_class_types and class_type not in rule.allowed_class_types:
                            violation = ConstraintViolation(
                                constraint_name=self.name,
                                severity="ERROR",
                                message=f"{class_ref}（{class_type}）に{subject}は不適切です",
                                time_slot=time_slot,
                                class_ref=class_ref,
                                subject=subject
                            )
                            result.add_violation(violation)
                            
    def _validate_combination_rules(self, context: ValidationContext, result: ConstraintResult):
        """組み合わせルールを検証"""
        for rule in self.combination_rules:
            if rule.rule_type == "forbidden" and rule.context == "same_day_multiple":
                # 同じ日の重複をチェック
                self._check_daily_duplicates(context, result, rule.subjects)
                
    def _check_daily_duplicates(self, context: ValidationContext, result: ConstraintResult, 
                              subjects: Set[str]):
        """特定教科の日内重複をチェック"""
        # 特別支援クラスのみチェック
        for class_ref in context.schedule.all_classes:
            if not self.class_validator.is_special_needs_class(class_ref):
                continue
                
            # 日ごとの教科カウント
            daily_counts = defaultdict(lambda: defaultdict(int))
            
            for time_slot in context.schedule.all_time_slots:
                assignment = context.get_assignment_at(time_slot, class_ref)
                if assignment and assignment.subject:
                    subject = assignment.subject.name
                    if subject in subjects:
                        daily_counts[time_slot.day][subject] += 1
            
            # 重複をチェック
            for day, subject_counts in daily_counts.items():
                for subject, count in subject_counts.items():
                    if count > 1:
                        violation = ConstraintViolation(
                            constraint_name=self.name,
                            severity="WARNING",
                            message=f"{class_ref}の{day}曜日に{subject}が{count}回配置されています（特別支援教科は1日1回推奨）",
                            class_ref=class_ref,
                            subject=subject
                        )
                        result.add_violation(violation)
                        
    def _get_class_type(self, class_ref: ClassReference) -> str:
        """クラスタイプを判定"""
        if self.class_validator.is_special_needs_class(class_ref):
            return "special_needs"
        elif class_ref.class_number == 5:
            return "grade5"
        else:
            return "regular"
            
    def check_assignment(self, context: ValidationContext) -> bool:
        """配置前チェック"""
        if not context.subject or not context.class_ref:
            return True
            
        # 有効な教科かチェック
        if context.subject not in self.valid_subjects:
            self.logger.debug(f"無効な教科: {context.subject}")
            return False
            
        # クラス適合性チェック
        class_type = self._get_class_type(context.class_ref)
        
        if context.subject in self.subject_class_rules:
            rule = self.subject_class_rules[context.subject]
            
            # 禁止クラスタイプ
            if class_type in rule.forbidden_class_types:
                self.logger.debug(
                    f"{context.class_ref}（{class_type}）に{context.subject}は配置不可"
                )
                return False
            
            # 許可クラスタイプ
            if rule.allowed_class_types and class_type not in rule.allowed_class_types:
                self.logger.debug(
                    f"{context.class_ref}（{class_type}）に{context.subject}は不適切"
                )
                return False
                
        return True
        
    def is_valid_subject(self, subject: str) -> bool:
        """教科が有効かチェック"""
        return subject in self.valid_subjects
        
    def is_special_needs_subject(self, subject: str) -> bool:
        """特別支援教科かチェック"""
        return subject in self.special_needs_subjects
        
    def get_allowed_subjects_for_class(self, class_ref: ClassReference) -> Set[str]:
        """クラスに配置可能な教科を取得"""
        class_type = self._get_class_type(class_ref)
        allowed = set()
        
        for subject, rule in self.subject_class_rules.items():
            if (class_type not in rule.forbidden_class_types and
                (not rule.allowed_class_types or class_type in rule.allowed_class_types)):
                allowed.add(subject)
                
        return allowed