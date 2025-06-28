"""教師コンテキスト分析モジュール

教師の経験年数、担任情報、協力関係などのコンテキスト情報を分析します。
"""
import logging
from typing import Dict, List, Optional, Any
from collections import defaultdict

from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School
from .....domain.value_objects.time_slot import TimeSlot
from ..configs.teacher_optimization_config import TeacherOptimizationConfig


class TeacherContextAnalyzer:
    """教師コンテキスト分析クラス"""
    
    def __init__(self, teacher_config: TeacherOptimizationConfig, teacher_pattern_analyzer: Optional[object] = None):
        self.logger = logging.getLogger(__name__)
        self.teacher_config = teacher_config
        self.teacher_pattern_analyzer = teacher_pattern_analyzer
    
    def analyze_teacher_context(
        self,
        school: School,
        followup_data: Optional[Dict]
    ) -> Dict[str, Any]:
        """教師のコンテキスト情報を分析"""
        context = {
            'teachers': {},
            'new_teachers': [],
            'veteran_teachers': [],
            'mentor_pairs': [],
            'collaboration_groups': []
        }
        
        # 各教師の情報を収集
        for teacher in school.get_all_teachers():
            teacher_info = {
                'name': teacher.name,
                'subjects': [s.name for s in school.get_teacher_subjects(teacher)],
                'experience_years': self.estimate_experience_years(teacher.name),
                'is_homeroom': self.is_homeroom_teacher(teacher.name, school),
                'workload': 0  # 後で計算
            }
            
            context['teachers'][teacher.name] = teacher_info
            
            # 経験年数で分類
            if teacher_info['experience_years'] < 3:
                context['new_teachers'].append(teacher.name)
            elif teacher_info['experience_years'] > 10:
                context['veteran_teachers'].append(teacher.name)
        
        # メンターペアの推定（新任とベテランのペア）
        if self.teacher_config.new_teacher_support:
            for new_teacher in context['new_teachers']:
                # 同じ教科のベテランを探す
                new_subjects = set(context['teachers'][new_teacher]['subjects'])
                for veteran in context['veteran_teachers']:
                    veteran_subjects = set(context['teachers'][veteran]['subjects'])
                    if new_subjects & veteran_subjects:  # 共通の教科がある
                        context['mentor_pairs'].append((new_teacher, veteran))
                        break
        
        # 協力グループの分析（過去のパターンから）
        if self.teacher_pattern_analyzer:
            for teacher_name in context['teachers']:
                pattern = self.teacher_pattern_analyzer.get_teacher_pattern(teacher_name)
                if pattern.collaboration_patterns:
                    # 頻繁に協力する教師のグループを形成
                    frequent_partners = [
                        partner for partner, count in pattern.collaboration_patterns.items()
                        if count > 5
                    ]
                    if frequent_partners:
                        group = [teacher_name] + frequent_partners
                        # 既存のグループと重複しないか確認
                        if not any(set(group) & set(g) for g in context['collaboration_groups']):
                            context['collaboration_groups'].append(group)
        
        return context
    
    def get_placement_context(
        self,
        schedule: Schedule,
        teacher_name: str,
        day: str
    ) -> Dict[str, Any]:
        """配置のコンテキスト情報を取得"""
        context = {
            'daily_count': 0,
            'is_consecutive': False,
            'team_teaching': False,
            'near_mentor': False
        }
        
        # その日の授業数をカウント
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            for class_ref in schedule.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                    context['daily_count'] += 1
        
        # 他のコンテキスト情報は必要に応じて追加
        
        return context
    
    def estimate_experience_years(self, teacher_name: str) -> int:
        """教師の経験年数を推定（実際は外部データから取得すべき）"""
        # 仮の実装：名前から推定
        if "新" in teacher_name or "若" in teacher_name:
            return 2
        elif "ベテラン" in teacher_name or "主任" in teacher_name:
            return 15
        else:
            return 7
    
    def is_homeroom_teacher(self, teacher_name: str, school: School) -> bool:
        """担任教師かどうかを判定"""
        for class_ref in school.get_all_classes():
            homeroom = school.get_homeroom_teacher(class_ref)
            if homeroom and homeroom.name == teacher_name:
                return True
        return False