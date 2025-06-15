"""スケジューリングルール制約 - 日内重複、標準時数、その他のスケジューリングルール"""
from typing import Dict, Set, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path
import csv

from .base import (
    ConfigurableConstraint, ConstraintConfig, ConstraintType,
    ConstraintPriority, ValidationContext, ConstraintResult, ConstraintViolation,
    CompositeConstraint
)
from ...value_objects.time_slot import TimeSlot, ClassReference
from ...value_objects.weekly_requirement import WeeklyRequirement
from ....infrastructure.config.path_config import path_config


@dataclass
class DuplicationRule:
    """重複ルール"""
    subject: str
    max_daily_count: int
    severity: str = "ERROR"  # ERROR or WARNING
    exceptions: Set[str] = field(default_factory=set)  # 例外教科


@dataclass
class StandardHoursRule:
    """標準時数ルール"""
    class_ref: ClassReference
    subject: str
    required_hours: int
    tolerance: int = 0  # 許容誤差


@dataclass
class PreferredTimeRule:
    """推奨時間ルール"""
    subject: str
    preferred_days: Set[str] = field(default_factory=set)
    preferred_periods: Set[int] = field(default_factory=set)
    weight: float = 1.0  # 推奨の重み


class SchedulingRuleConstraint(CompositeConstraint):
    """スケジューリングルール統合制約
    
    以下の制約を統合:
    - DailySubjectDuplicateConstraint: 日内重複制限
    - DailyDuplicateConstraint: 日内重複制約
    - TuesdayPEMultipleConstraint: 火曜体育推奨
    - StandardHoursConstraint: 標準時数制約
    """
    
    def __init__(self):
        config = ConstraintConfig(
            name="スケジューリングルール制約",
            description="日内重複、標準時数、推奨時間など一般的なスケジューリングルールを管理",
            type=ConstraintType.HARD,
            priority=ConstraintPriority.MEDIUM
        )
        super().__init__(config)
        
        # ルール定義
        self.duplication_rules: Dict[str, DuplicationRule] = {}
        self.standard_hours_rules: List[StandardHoursRule] = []
        self.preferred_time_rules: List[PreferredTimeRule] = []
        
        # 週間要件
        self.weekly_requirements: Dict[Tuple[ClassReference, str], WeeklyRequirement] = {}
        
        # サブ制約を作成
        self._create_sub_constraints()
        
    def _create_sub_constraints(self):
        """サブ制約を作成"""
        # 日内重複制約
        daily_duplicate_config = ConstraintConfig(
            name="日内重複制約",
            description="同じ日に同じ教科が過度に重複することを防ぐ",
            type=ConstraintType.HARD,
            priority=ConstraintPriority.MEDIUM
        )
        self.add_constraint(DailyDuplicateSubConstraint(daily_duplicate_config, self))
        
        # 標準時数制約
        standard_hours_config = ConstraintConfig(
            name="標準時数制約",
            description="各教科の週間標準時数を満たす",
            type=ConstraintType.SOFT,
            priority=ConstraintPriority.LOW
        )
        self.add_constraint(StandardHoursSubConstraint(standard_hours_config, self))
        
        # 推奨時間制約
        preferred_time_config = ConstraintConfig(
            name="推奨時間制約",
            description="特定教科の推奨時間帯への配置",
            type=ConstraintType.SOFT,
            priority=ConstraintPriority.SUGGESTION
        )
        self.add_constraint(PreferredTimeSubConstraint(preferred_time_config, self))
        
    def _load_configuration(self):
        """設定を読み込む"""
        self._load_duplication_rules()
        self._load_standard_hours()
        self._load_preferred_times()
        
    def _load_duplication_rules(self):
        """重複ルールを読み込む"""
        # デフォルトルール
        default_rules = {
            # 主要教科は1日2コマまで
            "国": DuplicationRule("国", 2, "ERROR"),
            "国語": DuplicationRule("国語", 2, "ERROR"),
            "数": DuplicationRule("数", 2, "ERROR"),
            "数学": DuplicationRule("数学", 2, "ERROR"),
            "英": DuplicationRule("英", 2, "ERROR"),
            "英語": DuplicationRule("英語", 2, "ERROR"),
            "理": DuplicationRule("理", 2, "ERROR"),
            "理科": DuplicationRule("理科", 2, "ERROR"),
            "社": DuplicationRule("社", 2, "ERROR"),
            "社会": DuplicationRule("社会", 2, "ERROR"),
            
            # 実技系は1日1コマが望ましい
            "体": DuplicationRule("体", 1, "WARNING"),
            "保体": DuplicationRule("保体", 1, "WARNING"),
            "音": DuplicationRule("音", 1, "WARNING"),
            "音楽": DuplicationRule("音楽", 1, "WARNING"),
            "美": DuplicationRule("美", 1, "WARNING"),
            "美術": DuplicationRule("美術", 1, "WARNING"),
            "技": DuplicationRule("技", 1, "WARNING"),
            "技術": DuplicationRule("技術", 1, "WARNING"),
            "家": DuplicationRule("家", 1, "WARNING"),
            "家庭": DuplicationRule("家庭", 1, "WARNING"),
        }
        
        # time_constraints.csvから追加ルールを読み込む
        time_constraints_path = path_config.config_dir / "time_constraints.csv"
        if time_constraints_path.exists():
            try:
                with open(time_constraints_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get('制約タイプ') == '日内制限':
                            subject = row.get('教科', '')
                            max_count = int(row.get('最大回数', 2))
                            severity = row.get('重要度', 'ERROR')
                            
                            if subject:
                                self.duplication_rules[subject] = DuplicationRule(
                                    subject, max_count, severity
                                )
            except Exception as e:
                self.logger.warning(f"時間制約の読み込みエラー: {e}")
        
        # デフォルトをマージ
        for subject, rule in default_rules.items():
            if subject not in self.duplication_rules:
                self.duplication_rules[subject] = rule
                
    def _load_standard_hours(self):
        """標準時数を読み込む"""
        base_timetable_path = path_config.config_dir / "base_timetable.csv"
        if base_timetable_path.exists():
            try:
                with open(base_timetable_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        subject = row.get('教科', '')
                        if not subject:
                            continue
                            
                        # 各クラスの時数を読み込む
                        for grade in range(1, 4):  # 1-3年
                            for class_num in range(1, 8):  # 1-7組
                                class_key = f"{grade}-{class_num}"
                                if class_key in row:
                                    try:
                                        hours = int(row[class_key])
                                        if hours > 0:
                                            class_ref = ClassReference(grade, class_num)
                                            rule = StandardHoursRule(
                                                class_ref=class_ref,
                                                subject=subject,
                                                required_hours=hours,
                                                tolerance=1  # ±1時間の誤差を許容
                                            )
                                            self.standard_hours_rules.append(rule)
                                            
                                            # WeeklyRequirementも作成
                                            key = (class_ref, subject)
                                            self.weekly_requirements[key] = WeeklyRequirement(
                                                class_ref=class_ref,
                                                subject=subject,
                                                required_hours=hours
                                            )
                                    except:
                                        pass
            except Exception as e:
                self.logger.error(f"標準時数の読み込みエラー: {e}")
                
    def _load_preferred_times(self):
        """推奨時間を読み込む"""
        # 火曜日の体育を推奨
        pe_rule = PreferredTimeRule(
            subject="体",
            preferred_days={"火"},
            preferred_periods={1, 2, 3},
            weight=2.0
        )
        self.preferred_time_rules.append(pe_rule)
        
        # 保健体育も同様
        pe_rule2 = PreferredTimeRule(
            subject="保体",
            preferred_days={"火"},
            preferred_periods={1, 2, 3},
            weight=2.0
        )
        self.preferred_time_rules.append(pe_rule2)
        
        # 他の推奨時間があれば設定ファイルから読み込む
        # （必要に応じて実装）


class DailyDuplicateSubConstraint(ConfigurableConstraint):
    """日内重複サブ制約"""
    
    def __init__(self, config: ConstraintConfig, parent: SchedulingRuleConstraint):
        super().__init__(config)
        self.parent = parent
        
    def _load_configuration(self):
        # 親から設定を参照
        pass
        
    def validate(self, context: ValidationContext) -> ConstraintResult:
        """日内重複を検証"""
        result = ConstraintResult(constraint_name=self.name)
        
        # クラスごと、日ごとに教科の出現回数を集計
        daily_subject_counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        
        for time_slot in context.schedule.all_time_slots:
            for class_ref in context.schedule.all_classes:
                assignment = context.get_assignment_at(time_slot, class_ref)
                if assignment and assignment.subject:
                    subject = assignment.subject.name
                    daily_subject_counts[class_ref][time_slot.day][subject] += 1
        
        # ルールに基づいて検証
        for class_ref, daily_data in daily_subject_counts.items():
            for day, subject_counts in daily_data.items():
                for subject, count in subject_counts.items():
                    if subject in self.parent.duplication_rules:
                        rule = self.parent.duplication_rules[subject]
                        if count > rule.max_daily_count:
                            violation = ConstraintViolation(
                                constraint_name=self.name,
                                severity=rule.severity,
                                message=f"{class_ref}の{day}曜日に{subject}が{count}回配置されています（上限: {rule.max_daily_count}回）",
                                class_ref=class_ref
                            )
                            result.add_violation(violation)
        
        return result
        
    def check_assignment(self, context: ValidationContext) -> bool:
        """配置前チェック"""
        if not context.subject or not context.time_slot or not context.class_ref:
            return True
            
        if context.subject not in self.parent.duplication_rules:
            return True
            
        rule = self.parent.duplication_rules[context.subject]
        
        # その日の現在の配置数を数える
        count = 0
        for period in range(1, 7):
            ts = TimeSlot(day=context.time_slot.day, period=period)
            assignment = context.get_assignment_at(ts, context.class_ref)
            if assignment and assignment.subject and assignment.subject.name == context.subject:
                count += 1
        
        # 上限チェック（配置予定のスロットは除く）
        if context.get_assignment_at(context.time_slot, context.class_ref):
            count -= 1
            
        if count >= rule.max_daily_count:
            self.logger.debug(
                f"{context.class_ref}の{context.time_slot.day}に{context.subject}は既に{count}回配置済み"
            )
            return False
            
        return True


class StandardHoursSubConstraint(ConfigurableConstraint):
    """標準時数サブ制約"""
    
    def __init__(self, config: ConstraintConfig, parent: SchedulingRuleConstraint):
        super().__init__(config)
        self.parent = parent
        
    def _load_configuration(self):
        pass
        
    def validate(self, context: ValidationContext) -> ConstraintResult:
        """標準時数を検証"""
        result = ConstraintResult(constraint_name=self.name)
        
        # クラスごと、教科ごとの時数を集計
        actual_hours = defaultdict(lambda: defaultdict(int))
        
        for time_slot in context.schedule.all_time_slots:
            for class_ref in context.schedule.all_classes:
                assignment = context.get_assignment_at(time_slot, class_ref)
                if assignment and assignment.subject:
                    actual_hours[class_ref][assignment.subject.name] += 1
        
        # 標準時数と比較
        for rule in self.parent.standard_hours_rules:
            actual = actual_hours[rule.class_ref].get(rule.subject, 0)
            diff = abs(actual - rule.required_hours)
            
            if diff > rule.tolerance:
                severity = "WARNING" if diff <= rule.tolerance * 2 else "ERROR"
                violation = ConstraintViolation(
                    constraint_name=self.name,
                    severity=severity,
                    message=f"{rule.class_ref}の{rule.subject}が{actual}時間です（標準: {rule.required_hours}時間）",
                    class_ref=rule.class_ref,
                    subject=rule.subject
                )
                result.add_violation(violation)
        
        return result


class PreferredTimeSubConstraint(ConfigurableConstraint):
    """推奨時間サブ制約"""
    
    def __init__(self, config: ConstraintConfig, parent: SchedulingRuleConstraint):
        super().__init__(config)
        self.parent = parent
        
    def _load_configuration(self):
        pass
        
    def validate(self, context: ValidationContext) -> ConstraintResult:
        """推奨時間を検証"""
        result = ConstraintResult(constraint_name=self.name)
        
        # 推奨時間外の配置を検出
        for rule in self.parent.preferred_time_rules:
            non_preferred_count = 0
            preferred_count = 0
            
            for time_slot in context.schedule.all_time_slots:
                is_preferred = (
                    (not rule.preferred_days or time_slot.day in rule.preferred_days) and
                    (not rule.preferred_periods or time_slot.period in rule.preferred_periods)
                )
                
                for class_ref in context.schedule.all_classes:
                    assignment = context.get_assignment_at(time_slot, class_ref)
                    if assignment and assignment.subject and assignment.subject.name == rule.subject:
                        if is_preferred:
                            preferred_count += 1
                        else:
                            non_preferred_count += 1
            
            # 推奨時間外の配置が多い場合は提案
            if non_preferred_count > preferred_count:
                violation = ConstraintViolation(
                    constraint_name=self.name,
                    severity="INFO",
                    message=f"{rule.subject}の{non_preferred_count}コマが推奨時間外に配置されています",
                    subject=rule.subject
                )
                result.add_violation(violation)
        
        return result