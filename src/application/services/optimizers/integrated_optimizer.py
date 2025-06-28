"""統合最適化サービス - 空きコマ埋め、標準時数調整、テスト期間保護を統合"""
import logging
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from ...domain.value_objects.time_slot import TimeSlot, ClassReference, Subject
from ...domain.value_objects.assignment import Assignment
from ...domain.interfaces.followup_parser import IFollowUpParser


class IntegratedOptimizer:
    """統合最適化サービス - すべての最適化を一元管理"""
    
    def __init__(self, followup_parser: IFollowUpParser = None):
        self.logger = logging.getLogger(__name__)
        
        # 固定科目
        self.fixed_subjects = {"欠", "YT", "道", "学", "学活", "学総", "総", "総合", "行", "行事", "テスト", "技家"}
        
        # 優先配置科目（標準時数が多い順）
        self.priority_subjects = ["国", "数", "英", "理", "社", "保", "音", "美", "技", "家"]
        
        # 交流学級マッピング
        self.exchange_pairs = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2)
        }
        
        # 5組クラス
        self.grade5_classes = {
            ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)
        }
        
        # テスト期間
        self.test_periods: Set[Tuple[str, int]] = set()
        self._load_test_periods(followup_parser)
    
    def _load_test_periods(self, followup_parser: IFollowUpParser):
        """テスト期間を読み込み"""
        if not followup_parser:
            from ...infrastructure.di_container import get_followup_parser
            followup_parser = get_followup_parser()
        
        try:
            test_periods = followup_parser.parse_test_periods()
            for test_period_info in test_periods:
                day = test_period_info.day
                for period in test_period_info.periods:
                    self.test_periods.add((day, period))
            
            if self.test_periods:
                self.logger.info(f"テスト期間を{len(self.test_periods)}スロット読み込みました")
        except Exception as e:
            self.logger.error(f"テスト期間の読み込みエラー: {e}")
    
    def optimize_schedule(self, schedule: Schedule, school: School) -> Dict[str, int]:
        """スケジュールを包括的に最適化"""
        self.logger.info("=== 統合最適化を開始 ===")
        
        results = {
            'empty_slots_filled': 0,
            'standard_hours_improved': 0,
            'test_periods_protected': len(self.test_periods),
            'violations_before': 0,
            'violations_after': 0
        }
        
        # 初期状態の分析
        initial_analysis = self._analyze_schedule(schedule, school)
        results['violations_before'] = initial_analysis['total_violations']
        
        self.logger.info(f"初期状態: 空きコマ={initial_analysis['empty_slots']}個, "
                        f"標準時数違反={initial_analysis['hour_violations']}件")
        
        # Step 1: テスト期間の保護（最優先）
        self._protect_test_periods(schedule)
        
        # Step 2: 空きコマを埋める
        filled = self._fill_empty_slots(schedule, school)
        results['empty_slots_filled'] = filled
        
        # Step 3: 標準時数の最適化
        improved = self._optimize_standard_hours(schedule, school)
        results['standard_hours_improved'] = improved
        
        # 最終分析
        final_analysis = self._analyze_schedule(schedule, school)
        results['violations_after'] = final_analysis['total_violations']
        
        self.logger.info(f"=== 統合最適化完了: "
                        f"空きコマ埋め={results['empty_slots_filled']}個, "
                        f"標準時数改善={results['standard_hours_improved']}件 ===")
        
        return results
    
    def _analyze_schedule(self, schedule: Schedule, school: School) -> Dict[str, int]:
        """スケジュールの現状を分析"""
        analysis = {
            'empty_slots': 0,
            'hour_violations': 0,
            'total_violations': 0
        }
        
        # 空きコマをカウント
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    if not schedule.get_assignment(time_slot, class_ref):
                        analysis['empty_slots'] += 1
        
        # 標準時数違反をカウント
        for class_ref in school.get_all_classes():
            current_hours = self._count_current_hours(schedule, class_ref)
            
            # クラスの標準時数が定義されている科目を取得
            class_subjects = self._get_subjects_for_class(school, class_ref)
            for subject in class_subjects:
                standard = school.get_standard_hours(class_ref, subject)
                current = current_hours.get(subject, 0)
                
                if standard > 0 and current < standard:
                    analysis['hour_violations'] += 1
        
        analysis['total_violations'] = analysis['empty_slots'] + analysis['hour_violations']
        return analysis
    
    def _protect_test_periods(self, schedule: Schedule):
        """テスト期間を保護（ロック）"""
        protected_count = 0
        
        # 全ての割り当てからクラスを抽出
        all_classes = set()
        for _, assignment in schedule.get_all_assignments():
            all_classes.add(assignment.class_ref)
        
        for day, period in self.test_periods:
            time_slot = TimeSlot(day, period)
            
            for class_ref in all_classes:
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and not schedule.is_locked(time_slot, class_ref):
                    schedule.lock_cell(time_slot, class_ref)
                    protected_count += 1
        
        if protected_count > 0:
            self.logger.info(f"テスト期間を{protected_count}セル保護しました")
    
    def _fill_empty_slots(self, schedule: Schedule, school: School) -> int:
        """空きコマを適切に埋める"""
        filled_count = 0
        empty_slots_found = 0
        blocked_by_constraint = {}
        
        # schoolから全クラスを取得
        all_classes = list(school.get_all_classes())
        self.logger.info(f"空きコマ埋めを開始: {len(all_classes)}クラスを処理")
        
        # 各クラスの空きコマを処理
        for class_ref in all_classes:
            # 現在の時数をカウント
            current_hours = self._count_current_hours(schedule, class_ref)
            
            # 不足している科目を優先度順にソート
            needed_subjects = []
            class_subjects = self._get_subjects_for_class(school, class_ref)
            for subject in class_subjects:
                standard = school.get_standard_hours(class_ref, subject)
                current = current_hours.get(subject, 0)
                
                if current < standard:
                    shortage = standard - current
                    priority = self.priority_subjects.index(subject.name) if subject.name in self.priority_subjects else 99
                    needed_subjects.append((subject, shortage, priority))
            
            needed_subjects.sort(key=lambda x: (x[1], -x[2]), reverse=True)
            
            # 空きコマに配置
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    # テスト期間はスキップ
                    if (day, period) in self.test_periods:
                        continue
                    
                    # 既に埋まっているかロックされている場合はスキップ
                    existing = schedule.get_assignment(time_slot, class_ref)
                    is_locked = schedule.is_locked(time_slot, class_ref)
                    
                    if existing or is_locked:
                        continue
                    
                    # 空きスロットを発見
                    empty_slots_found += 1
                    if empty_slots_found <= 10:  # 最初の10個のみ詳細ログ
                        self.logger.info(f"空きスロット発見: {class_ref} {time_slot}")
                    
                    # 配置する科目を選択
                    placed = False
                    
                    # 3年生の水曜6限の特別処理
                    if class_ref.grade == 3 and day == "水" and period == 6:
                        # 3年生の水曜6限は特殊時限のためスキップ
                        self.logger.info(f"{class_ref} 水曜6限は特殊時限のためスキップ")
                        continue
                    
                    # まず不足している科目から試す
                    for subject, shortage, _ in needed_subjects:
                        if shortage <= 0:
                            continue
                        
                        # 配置可能かチェック（柔軟な制約モード）
                        if self._can_place_subject(schedule, school, class_ref, time_slot, subject, allow_flexible_constraints=True):
                            teacher = school.get_assigned_teacher(subject, class_ref)
                            if teacher:
                                assignment = Assignment(class_ref, subject, teacher)
                                if schedule.assign(time_slot, assignment):
                                    filled_count += 1
                                    current_hours[subject] = current_hours.get(subject, 0) + 1
                                    # shortageを更新
                                    for i, (s, sh, p) in enumerate(needed_subjects):
                                        if s == subject:
                                            needed_subjects[i] = (s, sh - 1, p)
                                            break
                                    placed = True
                                    self.logger.info(f"空きコマを埋めました: {class_ref} {time_slot} → {subject.name}")
                                    break
                    
                    # 不足科目で埋められない場合、全ての有効な科目を試す
                    if not placed:
                        # クラスで有効な全科目を取得
                        all_subjects = self._get_subjects_for_class(school, class_ref)
                        
                        # 優先度順にソート（主要5教科を優先）
                        sorted_subjects = sorted(all_subjects, 
                            key=lambda s: (0 if s.name in ["国", "数", "英", "理", "社"] else 1, s.name))
                        
                        for subject in sorted_subjects:
                            if subject.name in self.fixed_subjects:
                                continue
                                
                            if self._can_place_subject(schedule, school, class_ref, time_slot, subject):
                                teacher = school.get_assigned_teacher(subject, class_ref)
                                if teacher:
                                    assignment = Assignment(class_ref, subject, teacher)
                                    if schedule.assign(time_slot, assignment):
                                        filled_count += 1
                                        current_hours[subject] = current_hours.get(subject, 0) + 1
                                        self.logger.info(f"空きコマを埋めました: {class_ref} {time_slot} → {subject.name}")
                                        placed = True
                                        break
                                else:
                                    self.logger.debug(f"{class_ref}の{subject.name}に教師が割り当てられていません")
                                    blocked_by_constraint["教師未割当"] = blocked_by_constraint.get("教師未割当", 0) + 1
                            else:
                                reason = self._get_cannot_place_reason(schedule, school, class_ref, time_slot, subject, allow_flexible_constraints=True)
                                self.logger.debug(f"{class_ref} {time_slot}に{subject.name}を配置不可: {reason}")
                                # ブロック理由を記録
                                blocked_by_constraint[reason] = blocked_by_constraint.get(reason, 0) + 1
        
        self.logger.info(f"空きコマ埋め完了: {empty_slots_found}個中{filled_count}個を埋めました")
        
        # ブロック理由の統計を出力
        if blocked_by_constraint:
            self.logger.info("空きコマが埋められなかった理由:")
            for reason, count in sorted(blocked_by_constraint.items(), key=lambda x: x[1], reverse=True):
                self.logger.info(f"  {reason}: {count}件")
        
        return filled_count
    
    def _optimize_standard_hours(self, schedule: Schedule, school: School) -> int:
        """標準時数を最適化"""
        improvements = 0
        
        # 各クラスで最適化
        for class_ref in school.get_all_classes():
            # 交流学級と5組は特殊処理が必要なのでスキップ
            if class_ref in self.exchange_pairs or class_ref in self.grade5_classes:
                continue
            
            # 現在の時数をカウント
            current_hours = self._count_current_hours(schedule, class_ref)
            
            # 不足と過剰を分析
            shortages = []
            excesses = []
            
            class_subjects = self._get_subjects_for_class(school, class_ref)
            for subject in class_subjects:
                standard = school.get_standard_hours(class_ref, subject)
                current = current_hours.get(subject, 0)
                
                if standard > 0:
                    diff = current - standard
                    if diff < 0:
                        shortages.append((subject, -diff))
                    elif diff > 0:
                        excesses.append((subject, diff))
            
            # 過剰な科目を不足している科目に置換
            for shortage_subject, shortage_amount in shortages:
                for excess_subject, excess_amount in excesses:
                    if shortage_amount <= 0 or excess_amount <= 0:
                        continue
                    
                    # 置換を試みる
                    swaps = self._try_swap_subjects(
                        schedule, school, class_ref,
                        excess_subject, shortage_subject,
                        min(shortage_amount, excess_amount)
                    )
                    
                    if swaps > 0:
                        improvements += swaps
                        # 更新
                        for i, (s, a) in enumerate(shortages):
                            if s == shortage_subject:
                                shortages[i] = (s, a - swaps)
                        for i, (s, a) in enumerate(excesses):
                            if s == excess_subject:
                                excesses[i] = (s, a - swaps)
        
        return improvements
    
    def _count_current_hours(self, schedule: Schedule, class_ref: ClassReference) -> Dict[Subject, float]:
        """現在の時数をカウント"""
        current_hours = defaultdict(float)
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                
                if assignment:
                    if assignment.subject.name == "技家":
                        current_hours[Subject("技")] += 0.5
                        current_hours[Subject("家")] += 0.5
                    else:
                        current_hours[assignment.subject] += 1.0
        
        return dict(current_hours)
    
    def _can_place_subject(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        time_slot: TimeSlot,
        subject: Subject,
        allow_flexible_constraints: bool = False
    ) -> bool:
        """指定科目を配置可能かチェック"""
        # テスト期間チェック
        if (time_slot.day, time_slot.period) in self.test_periods:
            return False
        
        # 固定科目は配置しない
        if subject.name in self.fixed_subjects:
            return False
        
        # 教師の可用性チェック
        teacher = school.get_assigned_teacher(subject, class_ref)
        if not teacher:
            return False
        
        # 教師の重複チェック
        for other_class in school.get_all_classes():
            if other_class == class_ref:
                continue
            other_assignment = schedule.get_assignment(time_slot, other_class)
            if other_assignment and other_assignment.teacher == teacher:
                return False
        
        # 1日1コマ制限
        day_count = 0
        for period in range(1, 7):
            check_slot = TimeSlot(time_slot.day, period)
            assignment = schedule.get_assignment(check_slot, class_ref)
            if assignment and assignment.subject == subject:
                day_count += 1
        
        if day_count >= 1:
            return False
        
        # 交流学級チェック
        if class_ref in self.exchange_pairs:
            parent_class = self.exchange_pairs[class_ref]
            parent_assignment = schedule.get_assignment(time_slot, parent_class)
            if parent_assignment and parent_assignment.subject != subject:
                # 自立活動以外は親学級と同じである必要
                if subject.name not in {"自立", "日生", "作業"}:
                    return False
        
        # 5組同期チェック
        if class_ref in self.grade5_classes:
            for other_class in self.grade5_classes:
                if other_class != class_ref:
                    other_assignment = schedule.get_assignment(time_slot, other_class)
                    if other_assignment and other_assignment.subject != subject:
                        return False
        
        return True
    
    def _get_cannot_place_reason(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        time_slot: TimeSlot,
        subject: Subject
    ) -> str:
        """配置できない理由を取得"""
        # テスト期間チェック
        if (time_slot.day, time_slot.period) in self.test_periods:
            return "テスト期間"
        
        # 固定科目は配置しない
        if subject.name in self.fixed_subjects:
            return "固定科目"
        
        # 教師の可用性チェック
        teacher = school.get_assigned_teacher(subject, class_ref)
        if not teacher:
            return "教師未割当"
        
        # 教師の重複チェック
        for other_class in school.get_all_classes():
            if other_class == class_ref:
                continue
            other_assignment = schedule.get_assignment(time_slot, other_class)
            if other_assignment and other_assignment.teacher == teacher:
                return f"教師重複({other_class})"
        
        # 1日1コマ制限
        day_count = 0
        for period in range(1, 7):
            check_slot = TimeSlot(time_slot.day, period)
            assignment = schedule.get_assignment(check_slot, class_ref)
            if assignment and assignment.subject == subject:
                day_count += 1
        
        if day_count >= 1:
            return "1日1コマ制限"
        
        # 交流学級チェック
        if class_ref in self.exchange_pairs:
            parent_class = self.exchange_pairs[class_ref]
            parent_assignment = schedule.get_assignment(time_slot, parent_class)
            if parent_assignment and parent_assignment.subject != subject:
                if subject.name not in {"自立", "日生", "作業"}:
                    return f"親学級と不一致({parent_assignment.subject.name})"
        
        # 5組同期チェック
        if class_ref in self.grade5_classes:
            for other_class in self.grade5_classes:
                if other_class != class_ref:
                    other_assignment = schedule.get_assignment(time_slot, other_class)
                    if other_assignment and other_assignment.subject != subject:
                        return f"5組同期不一致({other_class}:{other_assignment.subject.name})"
        
        return "不明"
    
    def _get_subjects_for_class(self, school: School, class_ref: ClassReference) -> List[Subject]:
        """クラスの科目リストを取得（標準時数が設定されている科目）"""
        subjects = set()
        
        # 主要科目
        main_subjects = ["国", "数", "英", "理", "社", "保", "音", "美", "技", "家"]
        for subject_name in main_subjects:
            subject = Subject(subject_name)
            if school.get_standard_hours(class_ref, subject) > 0:
                subjects.add(subject)
        
        # 特別科目（交流学級用）
        if class_ref.is_exchange_class():
            special_subjects = ["自立", "日生", "作業"]
            for subject_name in special_subjects:
                subject = Subject(subject_name)
                if school.get_standard_hours(class_ref, subject) > 0:
                    subjects.add(subject)
        
        return list(subjects)
    
    def _try_swap_subjects(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        from_subject: Subject,
        to_subject: Subject,
        max_swaps: int
    ) -> int:
        """科目を入れ替える"""
        swapped = 0
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                if swapped >= max_swaps:
                    return swapped
                
                time_slot = TimeSlot(day, period)
                
                # テスト期間とロックされたセルはスキップ
                if (day, period) in self.test_periods or schedule.is_locked(time_slot, class_ref):
                    continue
                
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject == from_subject:
                    # to_subjectに置換可能かチェック（通常の制約で）
                    if self._can_place_subject(schedule, school, class_ref, time_slot, to_subject, allow_flexible_constraints=False):
                        # 一時的に削除
                        schedule.remove_assignment(time_slot, class_ref)
                        
                        # 新しい割り当て
                        teacher = school.get_assigned_teacher(to_subject, class_ref)
                        if teacher:
                            new_assignment = Assignment(class_ref, to_subject, teacher)
                            if schedule.assign(time_slot, new_assignment):
                                swapped += 1
                                self.logger.debug(f"{class_ref} {time_slot}: {from_subject.name} → {to_subject.name}")
                            else:
                                # 失敗したら元に戻す
                                schedule.assign(time_slot, assignment)
        
        return swapped