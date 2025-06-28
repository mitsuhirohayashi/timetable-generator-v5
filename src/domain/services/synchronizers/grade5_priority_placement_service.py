"""5組優先配置サービス - 5組を最初に一括配置して教師重複を防ぐ"""
import logging
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
from ....shared.mixins.logging_mixin import LoggingMixin

from ...entities.schedule import Schedule
from ...entities.school import School
from ...value_objects.time_slot import TimeSlot, Subject, Teacher
from ...value_objects.assignment import Assignment
from ...constraints.base import ConstraintPriority
from ...utils import parse_class_reference
from .grade5_teacher_selector import Grade5TeacherSelector


class Grade5PriorityPlacementService(LoggingMixin):
    """5組（1年5組、2年5組、3年5組）を優先的に一括配置するサービス"""
    
    def __init__(self, preferred_teachers=None, teacher_ratios=None):
        super().__init__()
        self.grade5_classes = ['1年5組', '2年5組', '3年5組']
        # 5組優先教師（QA.txtから読み込み）
        self.preferred_teachers = preferred_teachers or []
        # 5組教師選択サービス（教師比率を注入）
        self.teacher_selector = Grade5TeacherSelector(teacher_ratios)
        
    def place_grade5_first(self, schedule: Schedule, school: School) -> bool:
        """5組を最初に配置する"""
        self.logger.info("5組優先配置を開始します")
        
        # 1. 固定スロットを識別（欠、YT、テストなど）
        fixed_slots = self._identify_fixed_slots(schedule)
        
        # 2. 5組で必要な科目と時数を計算
        required_subjects = self._calculate_required_subjects(school)
        
        # 3. 利用可能なスロットを評価
        available_slots = self._evaluate_available_slots(schedule, fixed_slots)
        
        # 4. 科目を優先順位付けして配置
        placement_success = self._place_subjects_by_priority(
            schedule, school, required_subjects, available_slots
        )
        
        if placement_success:
            self.logger.info("5組の優先配置が完了しました")
        else:
            self.logger.warning("5組の配置が一部失敗しました")
            
        return placement_success
    
    def _identify_fixed_slots(self, schedule: Schedule) -> Set[Tuple[str, int]]:
        """固定スロット（変更不可）を識別"""
        fixed_slots = set()
        
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 各5組クラスの固定スロットをチェック
                for class_name in self.grade5_classes:
                    assignment = schedule.get_assignment(time_slot, class_name)
                    if assignment and assignment.subject:
                        # 固定科目（欠、YT、学活、道徳など）
                        if assignment.subject.name in ['欠', 'YT', '学活', '学', '道', '道徳', '総', '総合', '学総', 'テスト']:
                            fixed_slots.add((day, period))
                            break
        
        self.logger.debug(f"固定スロット数: {len(fixed_slots)}")
        return fixed_slots
    
    def _calculate_required_subjects(self, school: School) -> Dict[str, int]:
        """5組で必要な科目と時数を計算"""
        required = defaultdict(int)
        
        # 各5組クラスの標準時数を集計
        for class_name in self.grade5_classes:
            # クラスを取得（get_all_classesから探す）
            class_ref = None
            for c in school.get_all_classes():
                if str(c) == class_name:
                    class_ref = c
                    break
            
            if class_ref:
                # クラスの標準時数を取得
                standard_hours = school.get_all_standard_hours(class_ref)
                for subject, hours in standard_hours.items():
                    if hours > 0:
                        # 固定科目は除外
                        if subject.name not in ['欠', 'YT', '学活', '学', '道', '道徳', '総', '総合', '学総']:
                            required[subject.name] = max(required[subject.name], int(hours))
        
        self.logger.debug(f"必要科目: {dict(required)}")
        return dict(required)
    
    def _evaluate_available_slots(self, schedule: Schedule, 
                                 fixed_slots: Set[Tuple[str, int]]) -> List[Tuple[TimeSlot, float]]:
        """利用可能なスロットを評価してスコア付け"""
        available_slots = []
        
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 7):
                if (day, period) in fixed_slots:
                    continue
                    
                time_slot = TimeSlot(day, period)
                
                # スロットのスコアを計算（高いほど良い）
                score = self._calculate_slot_score(time_slot, schedule)
                
                # 全5組クラスが空いているか確認
                all_empty = True
                for class_name in self.grade5_classes:
                    assignment = schedule.get_assignment(time_slot, class_name)
                    if assignment and assignment.subject:
                        all_empty = False
                        break
                
                if all_empty:
                    available_slots.append((time_slot, score))
        
        # スコアの高い順にソート
        available_slots.sort(key=lambda x: x[1], reverse=True)
        self.logger.debug(f"利用可能スロット数: {len(available_slots)}")
        
        return available_slots
    
    def _calculate_slot_score(self, time_slot: TimeSlot, schedule: Schedule) -> float:
        """スロットのスコアを計算（配置の優先度）"""
        score = 100.0
        
        # 午前中は高スコア
        if time_slot.period <= 3:
            score += 20.0
        
        # 月曜1限と金曜6限は低スコア
        if (time_slot.day == '月' and time_slot.period == 1):
            score -= 30.0
        if (time_slot.day == '金' and time_slot.period == 6):
            score -= 20.0
        
        # 水曜4限は中程度
        if (time_slot.day == '水' and time_slot.period == 4):
            score -= 10.0
            
        return score
    
    def _place_subjects_by_priority(self, schedule: Schedule, school: School,
                                   required_subjects: Dict[str, int],
                                   available_slots: List[Tuple[TimeSlot, float]]) -> bool:
        """科目を優先順位付けして配置"""
        # 主要教科を優先
        priority_order = ['国', '数', '英', '理', '社', '音', '美', '保', '技', '家']
        
        # 科目を優先順位でソート
        sorted_subjects = []
        for subject in priority_order:
            if subject in required_subjects:
                sorted_subjects.append((subject, required_subjects[subject]))
        
        # その他の科目を追加
        for subject, hours in required_subjects.items():
            if subject not in priority_order:
                sorted_subjects.append((subject, hours))
        
        # 配置実行
        total_placed = 0
        for subject_name, required_hours in sorted_subjects:
            placed = self._place_subject(
                schedule, school, subject_name, required_hours, available_slots
            )
            total_placed += placed
            
            if placed < required_hours:
                self.logger.warning(
                    f"{subject_name}の配置が不足: {placed}/{required_hours}時間"
                )
        
        return total_placed > 0
    
    def _place_subject(self, schedule: Schedule, school: School,
                      subject_name: str, required_hours: int,
                      available_slots: List[Tuple[TimeSlot, float]]) -> int:
        """特定の科目を配置"""
        placed_count = 0
        used_slots = []
        
        # 最適な教師を選択
        teacher = self._select_best_teacher(school, subject_name)
        if not teacher:
            self.logger.error(f"{subject_name}の教師が見つかりません")
            return 0
        
        subject = Subject(subject_name)
        
        # スコアの高いスロットから配置を試みる
        for time_slot, score in available_slots:
            if placed_count >= required_hours:
                break
                
            if (time_slot.day, time_slot.period) in used_slots:
                continue
            
            # 同じ日に同じ科目を配置しない
            if self._has_subject_on_day(schedule, time_slot.day, subject_name):
                continue
            
            # 全5組クラスに同時配置を試みる
            success = True
            assignments = []
            
            for class_name in self.grade5_classes:
                assignment = Assignment(
                    class_ref=parse_class_reference(class_name),
                    subject=subject,
                    teacher=teacher
                )
                
                try:
                    # 仮配置
                    schedule.assign(time_slot, assignment)
                    assignments.append((time_slot, class_name))
                except Exception as e:
                    self.logger.debug(f"配置失敗: {class_name} {time_slot} - {e}")
                    success = False
                    break
            
            if success:
                placed_count += 1
                used_slots.append((time_slot.day, time_slot.period))
                self.logger.info(
                    f"5組に{subject_name}を配置: {time_slot.day}{time_slot.period}限 "
                    f"(教師: {teacher.name})"
                )
            else:
                # 失敗した場合はロールバック
                for ts, cn in assignments:
                    class_ref = parse_class_reference(cn)
                    schedule.remove_assignment(ts, class_ref)
        
        return placed_count
    
    def _select_best_teacher(self, school: School, subject_name: str) -> Optional[Teacher]:
        """科目に最適な教師を選択"""
        subject = Subject(subject_name)
        
        # 5組の教師選択は専用サービスに委譲
        # parse_class_referenceを使って最初の5組クラスを代表として渡す
        class_ref = parse_class_reference(self.grade5_classes[0])
        return self.teacher_selector.select_teacher(school, subject, class_ref)
    
    def _has_subject_on_day(self, schedule: Schedule, day: str, subject_name: str) -> bool:
        """特定の日に既に科目が配置されているかチェック"""
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            for class_name in self.grade5_classes:
                assignment = schedule.get_assignment(time_slot, class_name)
                if assignment and assignment.subject and assignment.subject.name == subject_name:
                    return True
        
        return False