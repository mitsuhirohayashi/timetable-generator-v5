"""改良版制約検証サービス

キャッシング機能と学習ルール統合により、高速かつ正確な制約チェックを実現。
"""
import logging
from typing import Dict, List, Optional, Tuple, Set, Any
from datetime import datetime
from functools import lru_cache

from ...entities.schedule import Schedule
from ...entities.school import School
from ...value_objects.assignment import Assignment
from ...value_objects.time_slot import TimeSlot
from ..unified_constraint_system import UnifiedConstraintSystem, AssignmentContext


class ConstraintValidatorImproved:
    """改良版制約検証サービス
    
    キャッシング機能により高速化し、学習ルールを統合した制約検証を提供。
    
    主な改良点:
    1. 制約チェック結果のキャッシング
    2. 教師利用可能性のキャッシング
    3. 日内科目カウントのキャッシング
    4. 学習ルールの自動適用
    """
    
    def __init__(self, unified_system: UnifiedConstraintSystem):
        """初期化
        
        Args:
            unified_system: 統一制約システム
        """
        self.unified_system = unified_system
        self.logger = logging.getLogger(__name__)
        
        # キャッシュの初期化
        self._cache_teacher_availability: Dict[Tuple[str, str, int, str], bool] = {}
        self._cache_daily_counts: Dict[Tuple[str, str, str], int] = {}
        self._cache_validation_results: Dict[str, Any] = {}
        
        # 統計情報
        self._stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'total_checks': 0,
            'learned_rules_applied': 0
        }
        
        # 学習ルール（QandAシステムから）
        self._learned_rules = self._load_learned_rules()
    
    def _load_learned_rules(self) -> List[Dict[str, Any]]:
        """QandAシステムから学習したルールを読み込む"""
        rules = []
        
        # 井上先生の火曜5限ルール
        rules.append({
            'type': 'teacher_period_limit',
            'teacher': '井上',
            'day': '火',
            'period': 5,
            'max_classes': 1,
            'description': '井上先生は火曜5限に最大1クラスまで'
        })
        
        # 3年6組の自立活動ルール
        rules.append({
            'type': 'jiritsu_parent_constraint',
            'exchange_class': '3年6組',
            'parent_class': '3年3組',
            'allowed_subjects': ['数', '英'],
            'description': '3年6組が自立の時、3年3組は数学か英語のみ'
        })
        
        return rules
    
    def check_assignment(self, schedule: Schedule, school: School, 
                        time_slot: TimeSlot, assignment: Assignment) -> Tuple[bool, Optional[str]]:
        """配置前の制約チェック（キャッシング付き）
        
        Args:
            schedule: 現在のスケジュール
            school: 学校情報
            time_slot: 配置する時間枠
            assignment: 配置する授業
            
        Returns:
            (配置可能か, エラーメッセージ)
        """
        self._stats['total_checks'] += 1
        
        # キャッシュキーの生成
        cache_key = self._generate_cache_key(time_slot, assignment)
        
        # キャッシュチェック
        if cache_key in self._cache_validation_results:
            self._stats['cache_hits'] += 1
            return self._cache_validation_results[cache_key]
        
        self._stats['cache_misses'] += 1
        
        # 学習ルールの適用
        learned_check = self._check_learned_rules(schedule, school, time_slot, assignment)
        if not learned_check[0]:
            self._cache_validation_results[cache_key] = learned_check
            return learned_check
        
        # 基本的な制約チェック（キャッシュを活用）
        basic_check = self._check_basic_constraints_cached(schedule, school, time_slot, assignment)
        if not basic_check[0]:
            self._cache_validation_results[cache_key] = basic_check
            return basic_check
        
        # 統一制約システムでのチェック
        context = AssignmentContext(
            schedule=schedule,
            school=school,
            time_slot=time_slot,
            assignment=assignment
        )
        
        result, message = self.unified_system.check_before_assignment(context)
        
        # 結果をキャッシュ
        self._cache_validation_results[cache_key] = (result, message)
        
        return result, message
    
    def _check_learned_rules(self, schedule: Schedule, school: School,
                           time_slot: TimeSlot, assignment: Assignment) -> Tuple[bool, Optional[str]]:
        """学習したルールをチェック"""
        
        for rule in self._learned_rules:
            if rule['type'] == 'teacher_period_limit':
                # 井上先生の火曜5限ルール
                if (assignment.teacher and 
                    rule['teacher'] in assignment.teacher.name and
                    time_slot.day == rule['day'] and 
                    time_slot.period == rule['period']):
                    
                    # 既に配置されているクラス数をカウント
                    count = 0
                    for class_ref in school.get_all_classes():
                        if class_ref == assignment.class_ref:
                            continue
                        existing = schedule.get_assignment(time_slot, class_ref)
                        if existing and existing.teacher and rule['teacher'] in existing.teacher.name:
                            count += 1
                    
                    if count >= rule['max_classes']:
                        self._stats['learned_rules_applied'] += 1
                        return False, f"{rule['description']} (既に{count}クラス担当)"
            
            elif rule['type'] == 'jiritsu_parent_constraint':
                # 自立活動の親学級制約
                if (str(assignment.class_ref) == rule['exchange_class'] and
                    assignment.subject.name == '自立'):
                    
                    # 親学級の科目をチェック
                    parent_class = next((c for c in school.get_all_classes() 
                                       if c.name == rule['parent_class']), None)
                    if parent_class:
                        parent_assignment = schedule.get_assignment(time_slot, parent_class)
                        if parent_assignment and parent_assignment.subject.name not in rule['allowed_subjects']:
                            self._stats['learned_rules_applied'] += 1
                            return False, rule['description']
        
        return True, None
    
    def _check_basic_constraints_cached(self, schedule: Schedule, school: School,
                                      time_slot: TimeSlot, assignment: Assignment) -> Tuple[bool, Optional[str]]:
        """基本制約のチェック（キャッシング活用）"""
        
        # 教師利用可能性チェック（キャッシュ付き）
        if assignment.teacher:
            cache_key = (time_slot.day, str(time_slot.period), assignment.teacher.id, 'availability')
            
            if cache_key in self._cache_teacher_availability:
                is_available = self._cache_teacher_availability[cache_key]
            else:
                is_available = not school.is_teacher_unavailable(
                    time_slot.day, time_slot.period, assignment.teacher
                )
                self._cache_teacher_availability[cache_key] = is_available
            
            if not is_available:
                return False, f"{assignment.teacher.name}先生は{time_slot.day}曜{time_slot.period}限に不在です"
        
        # 日内重複チェック（キャッシュ付き）
        daily_key = (str(assignment.class_ref), time_slot.day, assignment.subject.name)
        
        if daily_key in self._cache_daily_counts:
            count = self._cache_daily_counts[daily_key]
        else:
            count = 0
            for period in range(1, 7):
                if period == time_slot.period:
                    continue
                ts = TimeSlot(time_slot.day, period)
                existing = schedule.get_assignment(ts, assignment.class_ref)
                if existing and existing.subject.name == assignment.subject.name:
                    count += 1
            self._cache_daily_counts[daily_key] = count
        
        if count >= 1:
            return False, f"{str(assignment.class_ref)}は{time_slot.day}曜日に既に{assignment.subject.name}があります"
        
        return True, None
    
    def _generate_cache_key(self, time_slot: TimeSlot, assignment: Assignment) -> str:
        """キャッシュキーを生成"""
        teacher_id = assignment.teacher.id if assignment.teacher else "none"
        return f"{time_slot.day}_{time_slot.period}_{str(assignment.class_ref)}_{assignment.subject.name}_{teacher_id}"
    
    def validate_all(self, schedule: Schedule, school: School) -> List[Any]:
        """スケジュール全体の検証"""
        validation_result = self.unified_system.validate_schedule(schedule, school)
        return validation_result.violations
    
    def clear_cache(self):
        """キャッシュをクリア"""
        self._cache_teacher_availability.clear()
        self._cache_daily_counts.clear()
        self._cache_validation_results.clear()
        
        self.logger.info(f"キャッシュをクリアしました。統計: {self.get_statistics()}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        total = self._stats['cache_hits'] + self._stats['cache_misses']
        hit_rate = (self._stats['cache_hits'] / total * 100) if total > 0 else 0
        
        return {
            'cache_hits': self._stats['cache_hits'],
            'cache_misses': self._stats['cache_misses'],
            'cache_hit_rate': hit_rate,
            'total_checks': self._stats['total_checks'],
            'learned_rules_applied': self._stats['learned_rules_applied']
        }