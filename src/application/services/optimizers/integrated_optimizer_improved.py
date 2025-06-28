"""統合最適化サービス - 交流学級同期を改善"""
import logging
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.value_objects.time_slot import TimeSlot, ClassReference, Subject
from ....domain.value_objects.assignment import Assignment
from ....domain.interfaces.followup_parser import IFollowUpParser


class IntegratedOptimizerImproved:
    """統合最適化サービス - 交流学級同期を強化"""
    
    def __init__(self, followup_parser: IFollowUpParser = None):
        self.logger = logging.getLogger(__name__)
        
        # 固定科目
        self.fixed_subjects = {"欠", "YT", "道", "学", "学活", "学総", "総", "総合", "行", "行事", "テスト", "技家"}
        
        # 優先配置科目（標準時数が多い順）
        self.priority_subjects = ["国", "数", "英", "理", "社", "保", "音", "美", "技", "家"]
        
        # 交流学級マッピング（双方向）
        self.exchange_pairs = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2)
        }
        
        # 逆引きマッピング（親学級→交流学級）
        self.parent_to_exchange = {v: k for k, v in self.exchange_pairs.items()}
        
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
            from ....infrastructure.di_container import get_followup_parser
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
        self.logger.info("=== 統合最適化を開始（改良版） ===")
        
        results = {
            'empty_slots_filled': 0,
            'standard_hours_improved': 0,
            'test_periods_protected': len(self.test_periods),
            'violations_before': 0,
            'violations_after': 0,
            'exchange_sync_fixed': 0
        }
        
        # 初期状態の分析
        initial_analysis = self._analyze_schedule(schedule, school)
        results['violations_before'] = initial_analysis['total_violations']
        
        self.logger.info(f"初期状態: 空きコマ={initial_analysis['empty_slots']}個, "
                        f"標準時数違反={initial_analysis['hour_violations']}件, "
                        f"交流学級同期違反={initial_analysis['exchange_violations']}件")
        
        # Step 1: テスト期間の保護（最優先）
        self._protect_test_periods(schedule)
        
        # Step 2: 交流学級の同期を修正
        sync_fixed = self._fix_exchange_class_sync(schedule, school)
        results['exchange_sync_fixed'] = sync_fixed
        
        # Step 3: 空きコマを埋める（交流学級同期を考慮）
        filled = self._fill_empty_slots(schedule, school)
        results['empty_slots_filled'] = filled
        
        # Step 4: 標準時数の最適化
        improved = self._optimize_standard_hours(schedule, school)
        results['standard_hours_improved'] = improved
        
        # 最終分析
        final_analysis = self._analyze_schedule(schedule, school)
        results['violations_after'] = final_analysis['total_violations']
        
        self.logger.info(f"=== 統合最適化完了: "
                        f"空きコマ埋め={results['empty_slots_filled']}個, "
                        f"標準時数改善={results['standard_hours_improved']}件, "
                        f"交流学級同期修正={results['exchange_sync_fixed']}件 ===")
        
        return results
    
    def _analyze_schedule(self, schedule: Schedule, school: School) -> Dict[str, int]:
        """スケジュールの現状を分析（交流学級同期違反を含む）"""
        analysis = {
            'empty_slots': 0,
            'hour_violations': 0,
            'exchange_violations': 0,
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
            class_subjects = self._get_subjects_for_class(school, class_ref)
            for subject in class_subjects:
                standard = school.get_standard_hours(class_ref, subject)
                current = current_hours.get(subject, 0)
                if standard > 0 and current < standard:
                    analysis['hour_violations'] += 1
        
        # 交流学級同期違反をカウント
        for exchange_class, parent_class in self.exchange_pairs.items():
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    
                    if exchange_assignment and parent_assignment:
                        # 交流学級が特別活動以外で親学級と異なる場合
                        if (exchange_assignment.subject.name not in {"自立", "日生", "作業"} and
                            exchange_assignment.subject != parent_assignment.subject):
                            analysis['exchange_violations'] += 1
        
        analysis['total_violations'] = (analysis['empty_slots'] + 
                                       analysis['hour_violations'] + 
                                       analysis['exchange_violations'])
        return analysis
    
    def _fix_exchange_class_sync(self, schedule: Schedule, school: School) -> int:
        """交流学級の同期違反を修正"""
        fixed_count = 0
        
        for exchange_class, parent_class in self.exchange_pairs.items():
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    # ロックされている場合はスキップ
                    if schedule.is_locked(time_slot, exchange_class):
                        continue
                    
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    
                    if not exchange_assignment or not parent_assignment:
                        continue
                    
                    # 交流学級が特別活動の場合はスキップ
                    if exchange_assignment.subject.name in {"自立", "日生", "作業"}:
                        continue
                    
                    # 同期が必要な場合
                    if exchange_assignment.subject != parent_assignment.subject:
                        # 親学級の教師を使用して交流学級を更新
                        new_assignment = Assignment(
                            exchange_class, 
                            parent_assignment.subject, 
                            parent_assignment.teacher
                        )
                        
                        schedule.remove_assignment(time_slot, exchange_class)
                        if schedule.assign(time_slot, new_assignment):
                            self.logger.info(f"交流学級同期修正: {exchange_class} {time_slot} "
                                           f"{exchange_assignment.subject.name} → {parent_assignment.subject.name}")
                            fixed_count += 1
        
        return fixed_count
    
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
        """空きコマを適切に埋める（交流学級同期を考慮）"""
        filled_count = 0
        empty_slots_found = 0
        blocked_by_constraint = {}
        
        # schoolから全クラスを取得
        all_classes = list(school.get_all_classes())
        self.logger.info(f"空きコマ埋めを開始: {len(all_classes)}クラスを処理")
        
        # 親学級を優先的に処理（交流学級の同期のため）
        parent_classes = [c for c in all_classes if c in self.parent_to_exchange]
        other_classes = [c for c in all_classes if c not in parent_classes and c not in self.exchange_pairs]
        exchange_classes = [c for c in all_classes if c in self.exchange_pairs]
        
        # 処理順序：親学級 → その他 → 交流学級
        ordered_classes = parent_classes + other_classes + exchange_classes
        
        for class_ref in ordered_classes:
            # 交流学級（6組、7組）の場合、特別活動以外はスキップ
            if class_ref in self.exchange_pairs:
                self.logger.info(f"{class_ref}は交流学級のため、通常科目の配置をスキップ（親学級からの同期で処理）")
                continue
            
            # 現在の時数をカウント
            current_hours = self._count_current_hours(schedule, class_ref)
            
            # 不足している科目を優先度順にソート（固定科目は除外）
            needed_subjects = []
            class_subjects = self._get_subjects_for_class(school, class_ref)
            for subject in class_subjects:
                # 固定科目は空きスロット埋めに使用しない
                if subject.name in self.fixed_subjects:
                    continue
                    
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
                    
                    # 配置する科目を選択
                    placed = False
                    
                    # まず不足している科目から試す
                    for subject, shortage, _ in needed_subjects:
                        if shortage <= 0:
                            continue
                        
                        # 配置可能かチェック
                        if self._can_place_subject_improved(schedule, school, class_ref, time_slot, subject):
                            teacher = self._get_teacher_for_subject(school, class_ref, subject)
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
                                    
                                    # 交流学級の同期処理
                                    self._sync_exchange_class_if_needed(schedule, school, class_ref, time_slot, assignment)
                                    
                                    self.logger.info(f"空きコマを埋めました: {class_ref} {time_slot} → {subject.name}")
                                    break
        
        self.logger.info(f"空きコマ埋め完了: {empty_slots_found}個中{filled_count}個を埋めました")
        return filled_count
    
    def _can_place_subject_improved(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        time_slot: TimeSlot,
        subject: Subject
    ) -> bool:
        """指定科目を配置可能かチェック（交流学級同期を考慮）"""
        # 基本チェック
        if not self._basic_placement_checks(schedule, school, class_ref, time_slot, subject):
            return False
        
        # 親学級の場合、交流学級との同期を考慮
        if class_ref in self.parent_to_exchange:
            exchange_class = self.parent_to_exchange[class_ref]
            exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
            
            if exchange_assignment:
                # 交流学級が自立活動の場合、親学級は数学または英語のみ
                if exchange_assignment.subject.name in {"自立", "日生", "作業"}:
                    if subject.name not in {"数", "英", "算"}:
                        self.logger.debug(f"{class_ref} {time_slot}: 交流学級が自立活動のため、数/英のみ配置可能")
                        return False
                # 交流学級が特別活動でない場合、同じ科目である必要がある
                elif exchange_assignment.subject != subject:
                    return False
        
        # 交流学級の場合、親学級との同期を考慮
        if class_ref in self.exchange_pairs:
            parent_class = self.exchange_pairs[class_ref]
            parent_assignment = schedule.get_assignment(time_slot, parent_class)
            
            if parent_assignment:
                # 自立活動を配置する場合、親学級は数学または英語でなければならない
                if subject.name in {"自立", "日生", "作業"}:
                    if parent_assignment.subject.name not in {"数", "英", "算"}:
                        self.logger.debug(f"{class_ref} {time_slot}: 親学級が数/英でないため自立活動を配置不可")
                        return False
                # 特別活動以外は親学級と同じである必要
                elif parent_assignment.subject != subject:
                    return False
        
        return True
    
    def _basic_placement_checks(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        time_slot: TimeSlot,
        subject: Subject
    ) -> bool:
        """基本的な配置チェック"""
        # テスト期間チェック
        if (time_slot.day, time_slot.period) in self.test_periods:
            return False
        
        # 固定科目は配置しない
        if subject.name in self.fixed_subjects:
            return False
        
        # 教師の可用性チェック
        teacher = self._get_teacher_for_subject(school, class_ref, subject)
        if not teacher:
            return False
        
        # 教師の重複チェック（5組は除外）
        if class_ref not in self.grade5_classes:
            for other_class in school.get_all_classes():
                if other_class == class_ref or other_class in self.grade5_classes:
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
        
        # 5組同期チェック
        if class_ref in self.grade5_classes:
            for other_class in self.grade5_classes:
                if other_class != class_ref:
                    other_assignment = schedule.get_assignment(time_slot, other_class)
                    if other_assignment and other_assignment.subject != subject:
                        return False
        
        return True
    
    def _get_teacher_for_subject(self, school: School, class_ref: ClassReference, subject: Subject):
        """科目の教師を取得（交流学級の場合は親学級の教師も考慮）"""
        teacher = school.get_assigned_teacher(subject, class_ref)
        
        # 交流学級で教師が見つからない場合、親学級の教師を使用
        if not teacher and class_ref in self.exchange_pairs:
            parent_class = self.exchange_pairs[class_ref]
            teacher = school.get_assigned_teacher(subject, parent_class)
            
            if teacher:
                self.logger.debug(f"{class_ref}の{subject.name}に親学級{parent_class}の教師{teacher.name}を使用")
        
        return teacher
    
    def _sync_exchange_class_if_needed(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        time_slot: TimeSlot,
        assignment: Assignment
    ):
        """必要に応じて交流学級を同期"""
        # 親学級の場合、交流学級も同じ科目にする
        if class_ref in self.parent_to_exchange:
            exchange_class = self.parent_to_exchange[class_ref]
            exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
            
            # 交流学級が空きまたは異なる科目の場合
            if not exchange_assignment or (
                exchange_assignment.subject.name not in {"自立", "日生", "作業"} and
                exchange_assignment.subject != assignment.subject
            ):
                # 交流学級に同じ科目を配置
                exchange_teacher = self._get_teacher_for_subject(school, exchange_class, assignment.subject)
                if exchange_teacher:
                    new_assignment = Assignment(exchange_class, assignment.subject, exchange_teacher)
                    if exchange_assignment:
                        schedule.remove_assignment(time_slot, exchange_class)
                    if schedule.assign(time_slot, new_assignment):
                        self.logger.info(f"交流学級を同期: {exchange_class} {time_slot} → {assignment.subject.name}")
    
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
                    # to_subjectに置換可能かチェック
                    if self._can_place_subject_improved(schedule, school, class_ref, time_slot, to_subject):
                        # 一時的に削除
                        schedule.remove_assignment(time_slot, class_ref)
                        
                        # 新しい割り当て
                        teacher = self._get_teacher_for_subject(school, class_ref, to_subject)
                        if teacher:
                            new_assignment = Assignment(class_ref, to_subject, teacher)
                            if schedule.assign(time_slot, new_assignment):
                                swapped += 1
                                self.logger.debug(f"{class_ref} {time_slot}: {from_subject.name} → {to_subject.name}")
                                
                                # 交流学級の同期
                                self._sync_exchange_class_if_needed(schedule, school, class_ref, time_slot, new_assignment)
                            else:
                                # 失敗したら元に戻す
                                schedule.assign(time_slot, assignment)
        
        return swapped