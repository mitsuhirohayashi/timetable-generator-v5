"""空きスロット埋め戦略の具体的な実装"""

import random
from typing import List, Tuple, Dict
from ....domain.interfaces.fill_strategy import FillStrategy
from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School, Subject, Teacher
from ....domain.value_objects.time_slot import ClassReference
from ....domain.value_objects.time_slot import TimeSlot
from ....domain.value_objects.assignment import Assignment


class StrictFillStrategy(FillStrategy):
    """厳格な制約戦略（第1パス）"""
    
    def __init__(self):
        super().__init__("strict")
    
    def should_check_consecutive_periods(self) -> bool:
        return True
    
    def should_check_daily_duplicate_strictly(self) -> bool:
        return True
    
    def should_filter_forbidden_subjects(self) -> bool:
        return True
    
    def get_max_daily_occurrences(self, subject: Subject) -> int:
        # 厳格モード：1日1回まで
        return 1
    
    def create_candidates(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        shortage_subjects: Dict[Subject, int],
        teacher_loads: Dict[str, int]
    ) -> List[Tuple[Subject, Teacher]]:
        """教師負担を厳密に考慮した候補リストを作成（標準時数順）"""
        candidates = []
        
        # 標準時数を取得
        base_hours = school.get_all_standard_hours(class_ref)
        
        # 標準時数の多い順でソート
        sorted_subjects = sorted(shortage_subjects.items(),
                               key=lambda x: base_hours.get(x[0], 0),
                               reverse=True)
        
        # 主要教科を優先
        for subject, shortage in sorted_subjects:
            if subject.name in {"算", "国", "理", "社", "英", "数"}:
                teachers = list(school.get_subject_teachers(subject))
                
                for teacher in teachers:
                    # スコア計算（バランス重視 + 標準時数ボーナス）
                    score = self.calculate_candidate_score(subject, teacher, shortage, teacher_loads)
                    score += base_hours.get(subject, 0) * 10  # 標準時数によるボーナス
                    candidates.append((subject, teacher, score))
        
        # その他の教科
        for subject, shortage in sorted_subjects:
            if subject.name not in {"算", "国", "理", "社", "英", "数"}:
                teachers = list(school.get_subject_teachers(subject))
                
                for teacher in teachers:
                    # スコア計算（バランス重視）
                    score = self.calculate_candidate_score(subject, teacher, shortage, teacher_loads)
                    candidates.append((subject, teacher, score))
        
        # スコアでソート（高い順）
        candidates.sort(key=lambda x: x[2], reverse=True)
        
        return [(subj, teacher) for subj, teacher, _ in candidates]


class BalancedFillStrategy(FillStrategy):
    """バランス重視戦略（第2パス）"""
    
    def __init__(self):
        super().__init__("balanced")
    
    def should_check_consecutive_periods(self) -> bool:
        return True
    
    def should_check_daily_duplicate_strictly(self) -> bool:
        return True
    
    def should_filter_forbidden_subjects(self) -> bool:
        return True
    
    def get_max_daily_occurrences(self, subject: Subject) -> int:
        # バランスモード：主要教科は1日2回まで許可
        if subject.name in self.core_subjects:
            return 2
        return 1
    
    def create_candidates(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        shortage_subjects: Dict[Subject, int],
        teacher_loads: Dict[str, int]
    ) -> List[Tuple[Subject, Teacher]]:
        """バランスを考慮した候補リストを作成（標準時数順）"""
        candidates = []
        
        # 標準時数を取得
        base_hours = school.get_all_standard_hours(class_ref)
        
        # 標準時数の多い順でソート
        sorted_subjects = sorted(shortage_subjects.items(), 
                               key=lambda x: base_hours.get(x[0], 0), 
                               reverse=True)
        
        # 主要教科を優先
        primary_subjects = []
        other_subjects = []
        
        for subject, shortage in sorted_subjects:
            if subject.name in {"算", "国", "理", "社", "英", "数"}:
                primary_subjects.append((subject, shortage))
            else:
                other_subjects.append((subject, shortage))
        
        # 主要教科を先に処理
        for subject_list in [primary_subjects, other_subjects]:
            for subject, shortage in subject_list:
                teachers = list(school.get_subject_teachers(subject))
                
                # 教師負担でソート（少ない順）
                teachers.sort(key=lambda t: teacher_loads.get(t.name, 0))
                
                # 上位3人まで候補に追加
                for teacher in teachers[:3]:
                    score = self.calculate_candidate_score(subject, teacher, shortage, teacher_loads)
                    candidates.append((subject, teacher, score))
        
        # スコアでソート
        candidates.sort(key=lambda x: x[2], reverse=True)
        
        return [(subj, teacher) for subj, teacher, _ in candidates]


class RelaxedFillStrategy(FillStrategy):
    """緩い制約戦略（第3パス）"""
    
    def __init__(self):
        super().__init__("relaxed")
    
    def should_check_consecutive_periods(self) -> bool:
        return False  # 連続コマ許可
    
    def should_check_daily_duplicate_strictly(self) -> bool:
        return False  # 日内重複を緩く
    
    def should_filter_forbidden_subjects(self) -> bool:
        return True
    
    def get_max_daily_occurrences(self, subject: Subject) -> int:
        # 緩いモード：1日2回まで許可
        return 2
    
    def create_candidates(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        shortage_subjects: Dict[Subject, int],
        teacher_loads: Dict[str, int]
    ) -> List[Tuple[Subject, Teacher]]:
        """標準時数を優先した候補リストを作成"""
        candidates = []
        
        # 標準時数を取得
        base_hours = school.get_all_standard_hours(class_ref)
        
        # 標準時数の多い順でソート（不足数も考慮）
        sorted_subjects = sorted(shortage_subjects.items(), 
                               key=lambda x: (base_hours.get(x[0], 0), x[1]), 
                               reverse=True)
        
        # 主要教科を優先
        primary_candidates = []
        other_candidates = []
        
        for subject, shortage in sorted_subjects[:8]:  # 上位8教科
            teachers = list(school.get_subject_teachers(subject))
            
            # ランダムに教師を選択
            if teachers:
                random.shuffle(teachers)
                for teacher in teachers[:2]:  # 各教科2人まで
                    if subject.name in {"算", "国", "理", "社", "英", "数"}:
                        primary_candidates.append((subject, teacher))
                    else:
                        other_candidates.append((subject, teacher))
        
        # 主要教科を先に追加
        candidates = primary_candidates + other_candidates
        
        return candidates


class UltraRelaxedFillStrategy(FillStrategy):
    """最大限緩い制約戦略（第4パス）"""
    
    def __init__(self):
        super().__init__("ultra_relaxed")
    
    def should_check_consecutive_periods(self) -> bool:
        return False
    
    def should_check_daily_duplicate_strictly(self) -> bool:
        return False
    
    def should_filter_forbidden_subjects(self) -> bool:
        return False  # 禁止教科も考慮
    
    def get_max_daily_occurrences(self, subject: Subject) -> int:
        # 最大限緩い：1日3回まで許可
        return 3
    
    def create_candidates(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        shortage_subjects: Dict[Subject, int],
        teacher_loads: Dict[str, int]
    ) -> List[Tuple[Subject, Teacher]]:
        """すべての可能な組み合わせを候補に（標準時数順）"""
        candidates = []
        
        # 標準時数を取得
        base_hours = school.get_all_standard_hours(class_ref)
        
        # 標準時数の多い順でソート
        sorted_subjects = sorted(shortage_subjects.items(),
                               key=lambda x: base_hours.get(x[0], 0),
                               reverse=True)
        
        # 主要教科を優先
        primary_candidates = []
        other_candidates = []
        
        # すべての教科を対象に
        for subject, shortage in sorted_subjects:
            teachers = list(school.get_subject_teachers(subject))
            
            for teacher in teachers:
                if subject.name in {"算", "国", "理", "社", "英", "数"}:
                    primary_candidates.append((subject, teacher))
                else:
                    other_candidates.append((subject, teacher))
        
        # 主要教科を先に、その後その他の教科
        # 各グループ内でランダムシャッフル
        random.shuffle(primary_candidates)
        random.shuffle(other_candidates)
        
        candidates = primary_candidates + other_candidates
        
        return candidates


class ForcedFillStrategy(FillStrategy):
    """強制埋め戦略（最終手段）"""
    
    def __init__(self):
        super().__init__("forced")
    
    def should_check_consecutive_periods(self) -> bool:
        return False
    
    def should_check_daily_duplicate_strictly(self) -> bool:
        return False
    
    def should_filter_forbidden_subjects(self) -> bool:
        return False
    
    def get_max_daily_occurrences(self, subject: Subject) -> int:
        # 強制モード：制限なし
        return 999
    
    def create_candidates(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        shortage_subjects: Dict[Subject, int],
        teacher_loads: Dict[str, int]
    ) -> List[Tuple[Subject, Teacher]]:
        """利用可能なすべての教科・教師の組み合わせを返す（標準時数順）"""
        candidates = []
        
        # 標準時数のあるすべての教科から選択
        base_hours = school.get_all_standard_hours(class_ref)
        
        # 標準時数の多い順でソート
        sorted_subjects = sorted(base_hours.items(), key=lambda x: x[1], reverse=True)
        
        # 主要教科を優先
        primary_candidates = []
        other_candidates = []
        
        for subject, hours in sorted_subjects:
            # 除外教科はスキップ
            if subject.name in self.excluded_subjects:
                continue
                
            teachers = list(school.get_subject_teachers(subject))
            
            for teacher in teachers:
                if subject.name in {"算", "国", "理", "社", "英", "数"}:
                    primary_candidates.append((subject, teacher))
                else:
                    other_candidates.append((subject, teacher))
        
        # 主要教科を先に、その後その他の教科
        candidates = primary_candidates + other_candidates
        
        return candidates


class FlexibleFillingStrategy(FillStrategy):
    """人間的な柔軟性を持つ最終戦略（第5パス）"""
    
    def __init__(self):
        super().__init__("flexible")
    
    def should_check_consecutive_periods(self) -> bool:
        return False
    
    def should_check_daily_duplicate_strictly(self) -> bool:
        return False
    
    def should_filter_forbidden_subjects(self) -> bool:
        return False
    
    def get_max_daily_occurrences(self, subject: Subject) -> int:
        # 最大限の柔軟性：制限なし
        return 999
    
    def create_candidates(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        shortage_subjects: Dict[Subject, int],
        teacher_loads: Dict[str, int]
    ) -> List[Tuple[Subject, Teacher]]:
        """利用可能なすべての教科・教師の組み合わせを返す（標準時数順）"""
        candidates = []
        
        # 標準時数のあるすべての教科から選択
        base_hours = school.get_all_standard_hours(class_ref)
        
        # 標準時数の多い順でソート
        sorted_subjects = sorted(base_hours.items(), key=lambda x: x[1], reverse=True)
        
        # 主要教科を優先
        primary_candidates = []
        other_candidates = []
        
        for subject, hours in sorted_subjects:
            # 除外教科はスキップ
            if subject.name in self.excluded_subjects:
                continue
                
            teachers = list(school.get_subject_teachers(subject))
            
            for teacher in teachers:
                if subject.name in {"算", "国", "理", "社", "英", "数"}:
                    primary_candidates.append((subject, teacher))
                else:
                    other_candidates.append((subject, teacher))
        
        # 主要教科を先に、その後その他の教科
        candidates = primary_candidates + other_candidates
        
        return candidates