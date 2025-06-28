"""スマート時数バランサー - 標準時数不足を解消する高度な最適化サービス"""
import logging
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict
from ...entities.schedule import Schedule
from ...entities.school import School
from ...value_objects.time_slot import TimeSlot, ClassReference, Subject
from ...value_objects.assignment import Assignment
from ....shared.mixins.logging_mixin import LoggingMixin


class SmartHourBalancer(LoggingMixin):
    """標準時数のバランスを最適化する高度なサービス
    
    戦略：
    1. 過剰配置科目から不足科目への再配分
    2. 交換可能なスロットの特定と最適な交換
    3. 制約を守りながら最大限の改善
    """
    
    def __init__(self):
        super().__init__()
        
        # 固定科目（移動不可）
        self.fixed_subjects = {"欠", "YT", "道", "学", "学活", "学総", "総", "総合", "行", "行事", "テスト", "技家"}
        
        # 優先度の高い主要教科
        self.core_subjects = {"国", "数", "英", "理", "社"}
        
        # 交流学級関連
        self.exchange_classes = {
            ClassReference(1, 6), ClassReference(1, 7),
            ClassReference(2, 6), ClassReference(2, 7),
            ClassReference(3, 6), ClassReference(3, 7)
        }
        
        # 5組
        self.grade5_classes = {
            ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)
        }
    
    def balance_standard_hours(
        self, 
        schedule: Schedule, 
        school: School,
        max_iterations: int = 100
    ) -> Tuple[int, Dict[str, int]]:
        """標準時数のバランスを最適化
        
        Returns:
            (改善数, 詳細な統計情報)
        """
        self.logger.info("=== スマート時数バランス最適化を開始 ===")
        
        improvements = 0
        stats = {
            'swaps': 0,
            'replacements': 0,
            'violations_before': 0,
            'violations_after': 0
        }
        
        # 現状分析
        hour_analysis = self._analyze_hour_balance(schedule, school)
        stats['violations_before'] = sum(len(data['shortage']) for data in hour_analysis.values())
        
        self.logger.info(f"標準時数違反: {stats['violations_before']}件")
        
        # 最適化ループ
        for iteration in range(max_iterations):
            # 最も深刻な不足を特定
            worst_shortage = self._find_worst_shortage(hour_analysis)
            if not worst_shortage:
                break
            
            class_ref, subject, shortage = worst_shortage
            
            # 解決策を探す
            solution = self._find_best_solution(
                schedule, school, class_ref, subject, shortage, hour_analysis
            )
            
            if solution:
                # 解決策を適用
                if self._apply_solution(schedule, school, solution):
                    improvements += 1
                    stats[solution['type']] += 1
                    
                    # 分析を更新
                    hour_analysis = self._analyze_hour_balance(schedule, school)
                    
                    self.logger.debug(
                        f"改善 {improvements}: {class_ref} {subject} "
                        f"(不足 {shortage}時間) - {solution['type']}"
                    )
            
            # 改善が停滞したら終了
            if iteration > 20 and improvements == 0:
                break
        
        # 最終分析
        final_analysis = self._analyze_hour_balance(schedule, school)
        stats['violations_after'] = sum(len(data['shortage']) for data in final_analysis.values())
        
        self.logger.info(
            f"=== 時数バランス最適化完了: {improvements}件改善 "
            f"(違反: {stats['violations_before']}→{stats['violations_after']}) ==="
        )
        
        return improvements, stats
    
    def _analyze_hour_balance(
        self, 
        schedule: Schedule, 
        school: School
    ) -> Dict[ClassReference, Dict]:
        """各クラスの時数バランスを分析"""
        analysis = {}
        
        for class_ref in school.get_all_classes():
            # 現在の時数をカウント
            current_hours = defaultdict(float)
            
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    
                    if assignment:
                        # 技家は0.5時間ずつ
                        if assignment.subject.name == "技家":
                            current_hours[Subject("技")] += 0.5
                            current_hours[Subject("家")] += 0.5
                        else:
                            current_hours[assignment.subject] += 1.0
            
            # 標準時数と比較
            shortage = {}
            excess = {}
            
            for subject in school.get_subjects_for_class(class_ref):
                standard = school.get_standard_hours(class_ref, subject)
                current = current_hours.get(subject, 0)
                
                if standard > 0:
                    diff = current - standard
                    if diff < 0:
                        shortage[subject] = -diff
                    elif diff > 0:
                        excess[subject] = diff
            
            analysis[class_ref] = {
                'current': dict(current_hours),
                'shortage': shortage,
                'excess': excess
            }
        
        return analysis
    
    def _find_worst_shortage(
        self, 
        hour_analysis: Dict
    ) -> Optional[Tuple[ClassReference, Subject, float]]:
        """最も深刻な不足を特定"""
        worst = None
        max_shortage = 0
        
        for class_ref, data in hour_analysis.items():
            for subject, shortage in data['shortage'].items():
                # 主要教科を優先
                priority = 2.0 if subject.name in self.core_subjects else 1.0
                weighted_shortage = shortage * priority
                
                if weighted_shortage > max_shortage:
                    max_shortage = weighted_shortage
                    worst = (class_ref, subject, shortage)
        
        return worst
    
    def _find_best_solution(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        target_subject: Subject,
        shortage: float,
        hour_analysis: Dict
    ) -> Optional[Dict]:
        """最適な解決策を探す"""
        # 戦略1: 過剰科目との交換
        swap_solution = self._find_swap_solution(
            schedule, school, class_ref, target_subject, hour_analysis
        )
        
        if swap_solution:
            return swap_solution
        
        # 戦略2: 空きスロットへの配置（もしあれば）
        empty_solution = self._find_empty_slot_solution(
            schedule, school, class_ref, target_subject
        )
        
        if empty_solution:
            return empty_solution
        
        # 戦略3: 低優先度科目の置換
        replace_solution = self._find_replacement_solution(
            schedule, school, class_ref, target_subject, hour_analysis
        )
        
        return replace_solution
    
    def _find_swap_solution(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        target_subject: Subject,
        hour_analysis: Dict
    ) -> Optional[Dict]:
        """過剰科目とのスワップを探す"""
        data = hour_analysis[class_ref]
        
        # 過剰科目を優先度順にソート
        excess_subjects = sorted(
            data['excess'].items(),
            key=lambda x: (x[0].name not in self.core_subjects, -x[1])
        )
        
        for excess_subject, excess_hours in excess_subjects:
            if excess_subject.name in self.fixed_subjects:
                continue
            
            # このクラスの全スロットを検査
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    # ロックされていないスロットのみ
                    if schedule.is_locked(time_slot, class_ref):
                        continue
                    
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject == excess_subject:
                        # このスロットに目標科目を配置可能か確認
                        if self._can_place_subject(
                            schedule, school, class_ref, time_slot, target_subject
                        ):
                            return {
                                'type': 'swaps',
                                'action': 'replace',
                                'time_slot': time_slot,
                                'class_ref': class_ref,
                                'old_subject': excess_subject,
                                'new_subject': target_subject
                            }
        
        return None
    
    def _find_empty_slot_solution(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        target_subject: Subject
    ) -> Optional[Dict]:
        """空きスロットを探す（通常はないが念のため）"""
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                if not schedule.get_assignment(time_slot, class_ref):
                    if self._can_place_subject(
                        schedule, school, class_ref, time_slot, target_subject
                    ):
                        return {
                            'type': 'replacements',
                            'action': 'fill',
                            'time_slot': time_slot,
                            'class_ref': class_ref,
                            'new_subject': target_subject
                        }
        
        return None
    
    def _find_replacement_solution(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        target_subject: Subject,
        hour_analysis: Dict
    ) -> Optional[Dict]:
        """低優先度科目を置換"""
        # 置換可能な科目の優先度（低い順）
        replaceable_priority = {
            "音": 1, "美": 1, "技": 2, "家": 2, 
            "保": 3, "社": 4, "理": 4
        }
        
        candidates = []
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                if schedule.is_locked(time_slot, class_ref):
                    continue
                
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment:
                    subject_name = assignment.subject.name
                    
                    # 固定科目や主要教科は置換しない
                    if (subject_name in self.fixed_subjects or 
                        subject_name in self.core_subjects):
                        continue
                    
                    # 不足している科目は置換しない
                    if assignment.subject in hour_analysis[class_ref]['shortage']:
                        continue
                    
                    # 置換候補として追加
                    priority = replaceable_priority.get(subject_name, 10)
                    candidates.append((priority, time_slot, assignment.subject))
        
        # 優先度順にソート
        candidates.sort(key=lambda x: x[0])
        
        # 最も低優先度の科目を置換
        for _, time_slot, old_subject in candidates:
            if self._can_place_subject(
                schedule, school, class_ref, time_slot, target_subject
            ):
                return {
                    'type': 'replacements',
                    'action': 'replace',
                    'time_slot': time_slot,
                    'class_ref': class_ref,
                    'old_subject': old_subject,
                    'new_subject': target_subject
                }
        
        return None
    
    def _can_place_subject(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        time_slot: TimeSlot,
        subject: Subject
    ) -> bool:
        """指定科目を配置可能かチェック"""
        # 基本チェック
        if not subject.is_valid_for_class(class_ref):
            return False
        
        # 教師を取得
        teacher = school.get_assigned_teacher(subject, class_ref)
        if not teacher:
            return False
        
        # 教師の可用性チェック
        unavailable_teachers = school.get_unavailable_teachers(
            time_slot.day, time_slot.period
        )
        if teacher.name in unavailable_teachers:
            return False
        
        # 教師の重複チェック
        for other_class in school.get_all_classes():
            if other_class == class_ref:
                continue
            
            other_assignment = schedule.get_assignment(time_slot, other_class)
            if (other_assignment and 
                other_assignment.teacher and 
                other_assignment.teacher.name == teacher.name):
                return False
        
        # 1日1コマ制限チェック
        day_count = 0
        for period in range(1, 7):
            check_slot = TimeSlot(time_slot.day, period)
            assignment = schedule.get_assignment(check_slot, class_ref)
            if assignment and assignment.subject == subject:
                day_count += 1
        
        if day_count >= 1:
            return False
        
        # 交流学級の特殊チェック
        if class_ref in self.exchange_classes:
            # 交流学級の特殊ルールをチェック
            return self._check_exchange_class_rules(
                schedule, class_ref, time_slot, subject
            )
        
        # 5組の同期チェック
        if class_ref in self.grade5_classes:
            return self._check_grade5_sync(
                schedule, class_ref, time_slot, subject
            )
        
        return True
    
    def _check_exchange_class_rules(
        self,
        schedule: Schedule,
        class_ref: ClassReference,
        time_slot: TimeSlot,
        subject: Subject
    ) -> bool:
        """交流学級の特殊ルールをチェック"""
        # 自立活動は配置しない（別の最適化で処理）
        if subject.name in {"自立", "日生", "作業"}:
            return False
        
        # 親学級との同期が必要
        parent_map = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2),
        }
        
        parent_class = parent_map.get(class_ref)
        if parent_class:
            parent_assignment = schedule.get_assignment(time_slot, parent_class)
            if parent_assignment and parent_assignment.subject != subject:
                return False
        
        return True
    
    def _check_grade5_sync(
        self,
        schedule: Schedule,
        class_ref: ClassReference,
        time_slot: TimeSlot,
        subject: Subject
    ) -> bool:
        """5組の同期をチェック"""
        # 他の5組クラスと同じ科目である必要がある
        for other_class in self.grade5_classes:
            if other_class == class_ref:
                continue
            
            other_assignment = schedule.get_assignment(time_slot, other_class)
            if other_assignment and other_assignment.subject != subject:
                return False
        
        return True
    
    def _apply_solution(
        self,
        schedule: Schedule,
        school: School,
        solution: Dict
    ) -> bool:
        """解決策を適用"""
        try:
            time_slot = solution['time_slot']
            class_ref = solution['class_ref']
            new_subject = solution['new_subject']
            
            # 教師を取得
            teacher = school.get_assigned_teacher(new_subject, class_ref)
            if not teacher:
                return False
            
            # 既存の割り当てを削除
            if solution['action'] in ['replace', 'fill']:
                current = schedule.get_assignment(time_slot, class_ref)
                if current:
                    schedule.remove_assignment(time_slot, class_ref)
            
            # 新しい割り当てを作成
            new_assignment = Assignment(class_ref, new_subject, teacher)
            
            # 配置
            if schedule.assign(time_slot, new_assignment):
                self.logger.debug(
                    f"解決策適用: {time_slot} {class_ref} -> {new_subject.name}"
                )
                return True
            else:
                # ロールバック
                if current:
                    schedule.assign(time_slot, current)
                return False
                
        except Exception as e:
            self.logger.error(f"解決策適用エラー: {e}")
            return False