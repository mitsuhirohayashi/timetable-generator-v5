"""クラス同期制約 - 5組同期、交流学級同期などの統合管理"""
from typing import Dict, Set, List, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
import csv
import json

from .base import (
    ConfigurableConstraint, ConstraintConfig, ConstraintType,
    ConstraintPriority, ValidationContext, ConstraintResult, ConstraintViolation
)
from ...value_objects.time_slot import TimeSlot, ClassReference
from ...value_objects.class_validator import ClassValidator
from ....infrastructure.config.path_config import path_config


@dataclass
class SynchronizationRule:
    """同期ルール"""
    name: str
    classes: Set[ClassReference]
    sync_type: str  # "full", "partial", "jiritsu_aware"
    conditions: Dict[str, any]  # 追加条件


@dataclass
class ExchangeClassPair:
    """交流学級ペア"""
    support_class: ClassReference
    parent_class: ClassReference
    jiritsu_subjects: Set[str]  # 自立活動として扱う教科
    parent_subjects_during_jiritsu: Set[str]  # 自立時の親学級教科


class ClassSynchronizationConstraint(ConfigurableConstraint):
    """クラス同期統合制約
    
    以下の制約を統合:
    - Grade5SameSubjectConstraint: 5組の同一教科制約
    - ExchangeClassConstraint: 交流学級基本制約
    - ExchangeClassSyncConstraint: 交流学級同期制約
    - ExchangeClassFullSyncConstraint: 交流学級完全同期制約
    """
    
    def __init__(self):
        config = ConstraintConfig(
            name="クラス同期制約",
            description="5組同期、交流学級同期など、複数クラス間の教科同期を管理",
            type=ConstraintType.HARD,
            priority=ConstraintPriority.CRITICAL
        )
        super().__init__(config)
        
        self.class_validator = ClassValidator()
        
        # 同期ルール
        self.sync_rules: List[SynchronizationRule] = []
        
        # 交流学級ペア
        self.exchange_pairs: List[ExchangeClassPair] = []
        
        # 5組クラス
        self.grade5_classes = {
            ClassReference(1, 5),
            ClassReference(2, 5), 
            ClassReference(3, 5)
        }
        
    def _load_configuration(self):
        """設定を読み込む"""
        self._load_grade5_sync_rules()
        self._load_exchange_class_pairs()
        self._load_additional_sync_rules()
        
    def _load_grade5_sync_rules(self):
        """5組同期ルールを読み込む"""
        # 5組は常に同じ教科
        rule = SynchronizationRule(
            name="5組同一教科",
            classes=self.grade5_classes,
            sync_type="full",
            conditions={}
        )
        self.sync_rules.append(rule)
        
    def _load_exchange_class_pairs(self):
        """交流学級ペアを読み込む"""
        exchange_pairs_path = path_config.config_dir / "exchange_class_pairs.csv"
        if exchange_pairs_path.exists():
            try:
                with open(exchange_pairs_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        support_grade = int(row.get('支援学級学年', 0))
                        support_class = int(row.get('支援学級組', 0))
                        parent_grade = int(row.get('親学級学年', 0))
                        parent_class = int(row.get('親学級組', 0))
                        
                        if all([support_grade, support_class, parent_grade, parent_class]):
                            pair = ExchangeClassPair(
                                support_class=ClassReference(support_grade, support_class),
                                parent_class=ClassReference(parent_grade, parent_class),
                                jiritsu_subjects={'自立', '自立活動'},
                                parent_subjects_during_jiritsu={'数', '数学', '英', '英語'}
                            )
                            self.exchange_pairs.append(pair)
                            
                            # 交流学級の同期ルールも追加
                            rule = SynchronizationRule(
                                name=f"交流学級同期({support_grade}-{support_class})",
                                classes={pair.support_class, pair.parent_class},
                                sync_type="jiritsu_aware",
                                conditions={"pair": pair}
                            )
                            self.sync_rules.append(rule)
                            
            except Exception as e:
                self.logger.error(f"交流学級ペアの読み込みエラー: {e}")
                # デフォルト値を使用
                self._load_default_exchange_pairs()
        else:
            self._load_default_exchange_pairs()
    
    def _load_default_exchange_pairs(self):
        """デフォルトの交流学級ペアを設定"""
        default_pairs = [
            (ClassReference(1, 6), ClassReference(1, 1)),
            (ClassReference(1, 7), ClassReference(1, 2)),
            (ClassReference(2, 6), ClassReference(2, 1)),
            (ClassReference(2, 7), ClassReference(2, 2)),
            (ClassReference(3, 6), ClassReference(3, 1)),
            (ClassReference(3, 7), ClassReference(3, 2)),
        ]
        
        for support_class, parent_class in default_pairs:
            pair = ExchangeClassPair(
                support_class=support_class,
                parent_class=parent_class,
                jiritsu_subjects={'自立', '自立活動'},
                parent_subjects_during_jiritsu={'数', '数学', '英', '英語'}
            )
            self.exchange_pairs.append(pair)
            
            rule = SynchronizationRule(
                name=f"交流学級同期({support_class})",
                classes={support_class, parent_class},
                sync_type="jiritsu_aware",
                conditions={"pair": pair}
            )
            self.sync_rules.append(rule)
    
    def _load_additional_sync_rules(self):
        """追加の同期ルールを読み込む"""
        # 将来の拡張用：他の同期ルールがあれば読み込む
        pass
    
    def validate(self, context: ValidationContext) -> ConstraintResult:
        """制約を検証する"""
        result = ConstraintResult(constraint_name=self.name)
        
        # 各同期ルールを検証
        for rule in self.sync_rules:
            if rule.sync_type == "full":
                self._validate_full_sync(context, result, rule)
            elif rule.sync_type == "jiritsu_aware":
                self._validate_jiritsu_aware_sync(context, result, rule)
            elif rule.sync_type == "partial":
                self._validate_partial_sync(context, result, rule)
        
        return result
    
    def _validate_full_sync(self, context: ValidationContext, result: ConstraintResult, rule: SynchronizationRule):
        """完全同期を検証（5組など）"""
        for time_slot in context.schedule.all_time_slots:
            subjects_by_class = {}
            
            # 各クラスの教科を収集
            for class_ref in rule.classes:
                assignment = context.get_assignment_at(time_slot, class_ref)
                if assignment and assignment.subject:
                    subjects_by_class[class_ref] = assignment.subject.name
                else:
                    subjects_by_class[class_ref] = None
            
            # 全クラスが同じ教科かチェック
            subjects = list(subjects_by_class.values())
            if subjects and not all(s == subjects[0] for s in subjects):
                # 違反を検出
                violation_details = []
                for class_ref, subject in subjects_by_class.items():
                    violation_details.append(f"{class_ref}: {subject or '空き'}")
                
                violation = ConstraintViolation(
                    constraint_name=self.name,
                    severity="ERROR",
                    message=f"{rule.name} - {time_slot}に教科が異なります: {', '.join(violation_details)}",
                    time_slot=time_slot
                )
                result.add_violation(violation)
    
    def _validate_jiritsu_aware_sync(self, context: ValidationContext, result: ConstraintResult, rule: SynchronizationRule):
        """自立活動考慮の同期を検証（交流学級）"""
        pair = rule.conditions.get("pair")
        if not pair:
            return
        
        for time_slot in context.schedule.all_time_slots:
            support_assignment = context.get_assignment_at(time_slot, pair.support_class)
            parent_assignment = context.get_assignment_at(time_slot, pair.parent_class)
            
            if support_assignment and support_assignment.subject:
                support_subject = support_assignment.subject.name
                parent_subject = parent_assignment.subject.name if parent_assignment and parent_assignment.subject else None
                
                # 支援学級が自立活動の場合
                if support_subject in pair.jiritsu_subjects:
                    # 親学級は数学か英語でなければならない
                    if parent_subject not in pair.parent_subjects_during_jiritsu:
                        violation = ConstraintViolation(
                            constraint_name=self.name,
                            severity="ERROR",
                            message=f"{pair.support_class}が{support_subject}の時、{pair.parent_class}は数学か英語であるべきですが{parent_subject or '空き'}です",
                            time_slot=time_slot,
                            class_ref=pair.support_class
                        )
                        result.add_violation(violation)
                
                # 支援学級が自立活動以外の場合
                else:
                    # 親学級と同じ教科でなければならない
                    if support_subject != parent_subject:
                        violation = ConstraintViolation(
                            constraint_name=self.name,
                            severity="ERROR",
                            message=f"{pair.support_class}は{pair.parent_class}と同じ教科であるべきですが、{support_subject} != {parent_subject or '空き'}",
                            time_slot=time_slot,
                            class_ref=pair.support_class
                        )
                        result.add_violation(violation)
    
    def _validate_partial_sync(self, context: ValidationContext, result: ConstraintResult, rule: SynchronizationRule):
        """部分同期を検証（将来の拡張用）"""
        # 特定の教科のみ同期するなどの部分的な同期ルール
        pass
    
    def check_assignment(self, context: ValidationContext) -> bool:
        """配置前チェック"""
        if not context.time_slot or not context.class_ref or not context.subject:
            return True
        
        # 該当するルールを探す
        for rule in self.sync_rules:
            if context.class_ref in rule.classes:
                if rule.sync_type == "full":
                    return self._check_full_sync(context, rule)
                elif rule.sync_type == "jiritsu_aware":
                    return self._check_jiritsu_aware_sync(context, rule)
        
        return True
    
    def _check_full_sync(self, context: ValidationContext, rule: SynchronizationRule) -> bool:
        """完全同期の配置前チェック"""
        # 他のクラスの現在の教科を確認
        for other_class in rule.classes:
            if other_class == context.class_ref:
                continue
            
            other_assignment = context.get_assignment_at(context.time_slot, other_class)
            if other_assignment and other_assignment.subject:
                # 既に配置されている教科と異なる場合は配置不可
                if other_assignment.subject.name != context.subject:
                    self.logger.debug(
                        f"{rule.name}: {context.class_ref}に{context.subject}を配置できません。"
                        f"{other_class}は既に{other_assignment.subject.name}です"
                    )
                    return False
        
        return True
    
    def _check_jiritsu_aware_sync(self, context: ValidationContext, rule: SynchronizationRule) -> bool:
        """自立活動考慮の同期の配置前チェック"""
        pair = rule.conditions.get("pair")
        if not pair:
            return True
        
        # 支援学級への配置の場合
        if context.class_ref == pair.support_class:
            if context.subject in pair.jiritsu_subjects:
                # 自立活動の場合、親学級が数学か英語であることを確認
                parent_assignment = context.get_assignment_at(context.time_slot, pair.parent_class)
                if parent_assignment and parent_assignment.subject:
                    if parent_assignment.subject.name not in pair.parent_subjects_during_jiritsu:
                        self.logger.debug(
                            f"{pair.support_class}に自立活動を配置できません。"
                            f"{pair.parent_class}が{parent_assignment.subject.name}です"
                        )
                        return False
            else:
                # 自立活動以外の場合、親学級と同じ教科であることを確認
                parent_assignment = context.get_assignment_at(context.time_slot, pair.parent_class)
                if parent_assignment and parent_assignment.subject:
                    if parent_assignment.subject.name != context.subject:
                        self.logger.debug(
                            f"{pair.support_class}に{context.subject}を配置できません。"
                            f"{pair.parent_class}は{parent_assignment.subject.name}です"
                        )
                        return False
        
        # 親学級への配置の場合
        elif context.class_ref == pair.parent_class:
            support_assignment = context.get_assignment_at(context.time_slot, pair.support_class)
            if support_assignment and support_assignment.subject:
                if support_assignment.subject.name in pair.jiritsu_subjects:
                    # 支援学級が自立活動の場合、数学か英語のみ配置可能
                    if context.subject not in pair.parent_subjects_during_jiritsu:
                        self.logger.debug(
                            f"{pair.parent_class}に{context.subject}を配置できません。"
                            f"{pair.support_class}が自立活動中です"
                        )
                        return False
                else:
                    # 支援学級が通常教科の場合、同じ教科のみ配置可能
                    if context.subject != support_assignment.subject.name:
                        self.logger.debug(
                            f"{pair.parent_class}に{context.subject}を配置できません。"
                            f"{pair.support_class}は{support_assignment.subject.name}です"
                        )
                        return False
        
        return True
    
    def get_synchronized_classes(self, class_ref: ClassReference) -> Set[ClassReference]:
        """指定クラスと同期するクラスを取得"""
        synchronized = set()
        
        for rule in self.sync_rules:
            if class_ref in rule.classes:
                synchronized.update(rule.classes)
        
        synchronized.discard(class_ref)  # 自分自身は除外
        return synchronized
    
    def get_required_subject_for_sync(self, class_ref: ClassReference, time_slot: TimeSlot, 
                                    schedule) -> Optional[str]:
        """同期のために必要な教科を取得"""
        # 5組の場合
        if class_ref in self.grade5_classes:
            for other_class in self.grade5_classes:
                if other_class != class_ref:
                    assignment = schedule.get_assignment(time_slot, other_class)
                    if assignment and assignment.subject:
                        return assignment.subject.name
        
        # 交流学級の場合
        for pair in self.exchange_pairs:
            if class_ref == pair.support_class:
                parent_assignment = schedule.get_assignment(time_slot, pair.parent_class)
                if parent_assignment and parent_assignment.subject:
                    # 親学級が数学/英語なら自立活動、それ以外なら同じ教科
                    if parent_assignment.subject.name in pair.parent_subjects_during_jiritsu:
                        return "自立"
                    else:
                        return parent_assignment.subject.name
            
            elif class_ref == pair.parent_class:
                support_assignment = schedule.get_assignment(time_slot, pair.support_class)
                if support_assignment and support_assignment.subject:
                    if support_assignment.subject.name in pair.jiritsu_subjects:
                        # 支援学級が自立なら数学を推奨
                        return "数"
                    else:
                        return support_assignment.subject.name
        
        return None