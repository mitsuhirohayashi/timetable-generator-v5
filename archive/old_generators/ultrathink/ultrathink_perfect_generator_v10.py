#!/usr/bin/env python3
"""
Ultrathink Perfect Generator V10（教師重複完全解決版）
教師の割り当てと重複チェックを完全修正

V9からの改善点：
1. 教師情報の復元処理を修正（全assignment対象）
2. 教師利用可能性の正確な追跡
3. デバッグ情報の充実
4. 5組の合同授業を正しく処理
"""

from typing import List, Optional, Dict, Set, Tuple, Any
import logging
from copy import deepcopy
from collections import defaultdict
import random

from ....domain.entities import School, Schedule
from ....domain.constraints.base import Constraint
from ....domain.value_objects.time_slot import TimeSlot, Subject, Teacher, ClassReference as ClassRef
from ....domain.value_objects.assignment import Assignment

logger = logging.getLogger(__name__)


class UltrathinkPerfectGeneratorV10:
    """最初から完璧な時間割を生成する革新的ジェネレーター（V10）"""
    
    def __init__(self):
        self.stats = {
            'initial_assignments': 0,
            'placed_assignments': 0,
            'backtrack_count': 0,
            'conflicts_avoided': 0,
            'jiritsu_placed': 0,
            'jiritsu_violations_fixed': 0,
            'exchange_sync_count': 0,
            'exchange_violations_fixed': 0,
            'teacher_conflicts_avoided': 0,
            'teacher_assignments_restored': 0,
            'teacher_duplicates_found': 0,
            'existing_teacher_assignments': 0
        }
        
        # テスト期間情報
        self.test_periods = {
            ("月", 1), ("月", 2), ("月", 3),
            ("火", 1), ("火", 2), ("火", 3),
            ("水", 1), ("水", 2)
        }
        
        # テスト期間の科目マッピング
        self.test_subjects = {
            ("月", 1): {"1": "英", "2": "数", "3": "国"},
            ("月", 2): {"1": "保", "2": "技家", "3": "音"},
            ("月", 3): {"1": "技家", "2": "社", "3": "理"},
            ("火", 1): {"1": "社", "2": "国", "3": "数"},
            ("火", 2): {"1": "音", "2": "保", "3": "英"},
            ("火", 3): {"1": "国", "2": "理", "3": "技家"},
            ("水", 1): {"1": "理", "2": "英", "3": "保"},
            ("水", 2): {"1": "数", "2": "音", "3": "社"}
        }
        
        # 交流学級マッピング
        self.exchange_parent_map = {
            "1-6": "1-1", "1-7": "1-2",
            "2-6": "2-3", "2-7": "2-2",
            "3-6": "3-3", "3-7": "3-2"
        }
        
        # 固定科目（新規配置禁止）
        self.fixed_subjects = {"欠", "YT", "学", "学活", "道", "道徳", "総", "総合", "学総", "行", "行事", "テスト"}
        
        # 交流学級が持つことができる唯一の独自科目
        self.exchange_only_subject = "自立"
        
        # 5組専用科目
        self.grade5_only_subjects = {"日生", "作業"}
    
    def generate(self, school: School, constraints: List[Constraint],
                 initial_schedule: Optional[Schedule] = None) -> Schedule:
        """完璧な時間割を生成"""
        logger.info("=== Ultrathink Perfect Generator V10 開始 ===")
        
        # 初期化
        schedule = initial_schedule or Schedule()
        self.stats['initial_assignments'] = len(schedule.get_all_assignments())
        logger.info(f"初期割り当て数: {self.stats['initial_assignments']}")
        
        # 教師の利用可能時間を初期化（既存配置を考慮）
        self.teacher_availability = self._initialize_teacher_availability(school, schedule)
        
        # 1. 交流学級の不正な配置を削除
        self._clean_exchange_classes(schedule, school)
        
        # 2. テスト期間の配置
        self._place_test_periods_only(schedule, school)
        
        # 3. 5組の同期配置
        self._place_grade5_synchronized(schedule, school)
        
        # 4. 既存の自立活動の検証と修正
        self._validate_and_fix_existing_jiritsu(schedule, school)
        
        # 5. 新規自立活動の配置
        self._place_jiritsu_activities(schedule, school)
        
        # 6. 残りの通常授業を配置（バックトラッキング）
        self._place_regular_classes(schedule, school)
        
        # 7. 交流学級と親学級の同期（最終処理）
        self._sync_exchange_with_parent(schedule, school)
        
        # 統計出力
        self._print_statistics(schedule, school)
        
        return schedule
    
    def _initialize_teacher_availability(self, school: School, schedule: Schedule) -> Dict[str, Set[Tuple[str, int]]]:
        """教師の利用可能時間を初期化（既存配置を正確に反映）"""
        availability = {}
        
        # 全教師の全時間を利用可能として初期化
        for teacher in school.get_all_teachers():
            availability[teacher.name] = set()
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    availability[teacher.name].add((day, period))
        
        # 既存配置から教師を特定してbusy状態にする
        busy_count = 0
        teacher_assignments = defaultdict(list)  # 教師ごとの配置を追跡
        
        for time_slot, assignment in schedule.get_all_assignments():
            # テスト期間はスキップ（教師重複OK）
            if (time_slot.day, time_slot.period) in self.test_periods:
                logger.debug(f"テスト期間をスキップ: {time_slot}")
                continue
                
            # 固定科目でも教師情報は取得する（欠課以外）
            if assignment.subject.name == "欠":
                logger.debug(f"欠課をスキップ: @ {time_slot}")
                continue
            
            # 教師が未設定の場合、schoolから取得
            teacher = assignment.teacher
            if not teacher:
                # 重要: Subject objectを作成して正しく取得
                subject_obj = Subject(assignment.subject.name)
                teacher = school.get_assigned_teacher(subject_obj, assignment.class_ref)
                
                if teacher:
                    logger.debug(f"教師を推定: {assignment.class_ref} {assignment.subject.name} → {teacher.name}先生")
                else:
                    logger.warning(f"教師が見つかりません: {assignment.class_ref} {assignment.subject.name}")
                    continue
            
            if teacher and teacher.name in availability:
                # 5組の合同授業をチェック
                if assignment.class_ref.class_number == 5:
                    # 5組の場合、他の5組も同じ教師が担当しているか確認
                    grade5_classes = [self._get_class_ref(school, g, 5) for g in [1, 2, 3]]
                    grade5_classes = [c for c in grade5_classes if c]
                    
                    # 他の5組も同じ時間に同じ教師か確認
                    same_teacher_count = 0
                    for g5_class in grade5_classes:
                        g5_assignment = schedule.get_assignment(time_slot, g5_class)
                        if g5_assignment:
                            # 教師が未設定の場合はschoolから取得
                            g5_teacher = g5_assignment.teacher
                            if not g5_teacher:
                                g5_subject_obj = Subject(g5_assignment.subject.name)
                                g5_teacher = school.get_assigned_teacher(g5_subject_obj, g5_class)
                            
                            if g5_teacher and g5_teacher.name == teacher.name:
                                same_teacher_count += 1
                    
                    if same_teacher_count == len(grade5_classes):
                        # 全5組が同じ教師なので正常（合同授業）
                        logger.debug(f"5組合同授業: {teacher.name}先生 @ {time_slot.day}{time_slot.period}限")
                        teacher_assignments[teacher.name].append((time_slot, "5組合同"))
                        continue
                
                # この時間帯を利用不可にマーク
                availability[teacher.name].discard((time_slot.day, time_slot.period))
                busy_count += 1
                teacher_assignments[teacher.name].append((time_slot, assignment.class_ref))
                logger.debug(f"既存配置: {teacher.name}先生 @ {time_slot.day}{time_slot.period}限 ({assignment.class_ref})")
        
        # 統計情報を更新
        self.stats['existing_teacher_assignments'] = busy_count
        
        # 教師ごとの配置状況をログ出力
        logger.info(f"教師利用可能性を初期化: {busy_count}個の既存配置を検出")
        for teacher_name, assignments in teacher_assignments.items():
            logger.debug(f"{teacher_name}先生の既存配置: {len(assignments)}個")
            for slot, class_info in assignments[:3]:  # 最初の3つだけ表示
                logger.debug(f"  - {slot.day}{slot.period}限: {class_info}")
        
        return availability
    
    def _clean_exchange_classes(self, schedule: Schedule, school: School) -> None:
        """交流学級の不正な配置を削除"""
        logger.info("【フェーズ1: 交流学級のクリーンアップ】")
        removed = 0
        
        for exchange_name, parent_name in self.exchange_parent_map.items():
            grade, class_num = exchange_name.split("-")
            exchange_ref = self._get_class_ref(school, int(grade), int(class_num))
            
            if not exchange_ref:
                continue
            
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day=day, period=period)
                    assignment = schedule.get_assignment(time_slot, exchange_ref)
                    
                    if assignment and assignment.subject.name in self.grade5_only_subjects:
                        # 5組専用科目を削除
                        schedule.remove_assignment(time_slot, exchange_ref)
                        removed += 1
                        logger.debug(f"{exchange_ref} @ {time_slot}: {assignment.subject.name}を削除")
        
        logger.info(f"交流学級から{removed}個の不正な配置を削除")
    
    def _place_test_periods_only(self, schedule: Schedule, school: School) -> None:
        """テスト期間の配置のみ（固定科目の新規配置はしない）"""
        logger.info("【フェーズ2: テスト期間の配置】")
        placed = 0
        
        for (day, period), subjects in self.test_subjects.items():
            time_slot = TimeSlot(day=day, period=period)
            
            for grade_str, subject in subjects.items():
                grade = int(grade_str)
                
                # 該当学年の全クラス
                for class_ref in school.get_all_classes():
                    if class_ref.grade != grade:
                        continue
                    
                    # 既に配置されている場合はスキップ
                    if schedule.get_assignment(time_slot, class_ref):
                        continue
                    
                    # 5組・6組・7組以外のクラスに配置
                    if class_ref.class_number not in [5, 6, 7]:
                        # クラスに応じた正しい教師を取得
                        teacher = self._get_teacher_for_class_subject(school, class_ref, subject)
                        if teacher:
                            assignment = Assignment(
                                class_ref=class_ref,
                                subject=Subject(subject),
                                teacher=teacher
                            )
                            try:
                                schedule.assign(time_slot, assignment)
                                placed += 1
                                # テスト期間は教師の重複OK（巡回指導）
                            except Exception:
                                pass
        
        logger.info(f"テスト期間: {placed}スロット配置")
        self.stats['placed_assignments'] += placed
    
    def _place_grade5_synchronized(self, schedule: Schedule, school: School) -> None:
        """5組の同期配置"""
        logger.info("【フェーズ3: 5組の同期配置】")
        placed = 0
        
        # 5組のクラスを取得
        grade5_classes = []
        for grade in [1, 2, 3]:
            class_ref = self._get_class_ref(school, grade, 5)
            if class_ref:
                grade5_classes.append(class_ref)
        
        if not grade5_classes:
            logger.warning("5組が見つかりません")
            return
        
        # 5組に共通して配置
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day=day, period=period)
                
                # 既に配置されているかチェック
                if any(schedule.get_assignment(time_slot, c) for c in grade5_classes):
                    continue
                
                # テスト期間はスキップ
                if (day, period) in self.test_periods:
                    continue
                
                # 配置する科目を選択
                subject = self._select_subject_for_grade5(schedule, school, time_slot)
                if not subject:
                    continue
                
                # 5組の教師を取得（通常は金子み先生）
                teacher = self._get_teacher_for_class_subject(school, grade5_classes[0], subject)
                
                if teacher and self._is_teacher_available(teacher.name, day, period):
                    # 3クラスすべてに配置
                    success = True
                    for class_ref in grade5_classes:
                        assignment = Assignment(
                            class_ref=class_ref,
                            subject=Subject(subject),
                            teacher=teacher
                        )
                        try:
                            schedule.assign(time_slot, assignment)
                        except Exception:
                            success = False
                            break
                    
                    if success:
                        placed += len(grade5_classes)
                        # 5組の合同授業なので教師は1回分のみマーク
                        self._mark_teacher_busy(teacher.name, day, period)
        
        logger.info(f"5組同期配置: {placed // 3}スロット")
        self.stats['placed_assignments'] += placed
    
    def _validate_and_fix_existing_jiritsu(self, schedule: Schedule, school: School) -> None:
        """既存の自立活動を検証し、違反があれば修正"""
        logger.info("【フェーズ4: 既存自立活動の検証】")
        violations_fixed = 0
        
        for exchange_name, parent_name in self.exchange_parent_map.items():
            grade, class_num = exchange_name.split("-")
            exchange_ref = self._get_class_ref(school, int(grade), int(class_num))
            parent_grade, parent_num = parent_name.split("-")
            parent_ref = self._get_class_ref(school, int(parent_grade), int(parent_num))
            
            if not exchange_ref or not parent_ref:
                continue
            
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day=day, period=period)
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_ref)
                    
                    if exchange_assignment and exchange_assignment.subject.name == "自立":
                        # 親学級をチェック
                        parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                        
                        if not parent_assignment or parent_assignment.subject.name not in ["数", "英"]:
                            # 違反：親学級が数学/英語でない
                            logger.warning(f"自立活動違反: {exchange_ref} @ {time_slot} - 親学級{parent_ref}が{parent_assignment.subject.name if parent_assignment else '空き'}")
                            
                            # 自立活動を削除
                            schedule.remove_assignment(time_slot, exchange_ref)
                            violations_fixed += 1
                            self.stats['jiritsu_violations_fixed'] += 1
        
        logger.info(f"自立活動違反を{violations_fixed}件修正")
    
    def _place_jiritsu_activities(self, schedule: Schedule, school: School) -> None:
        """新規自立活動の配置（親学級が数学/英語の時のみ）"""
        logger.info("【フェーズ5: 新規自立活動の配置】")
        placed = 0
        
        for exchange_name, parent_name in self.exchange_parent_map.items():
            grade, class_num = exchange_name.split("-")
            exchange_ref = self._get_class_ref(school, int(grade), int(class_num))
            parent_grade, parent_num = parent_name.split("-")
            parent_ref = self._get_class_ref(school, int(parent_grade), int(parent_num))
            
            if not exchange_ref or not parent_ref:
                continue
            
            # 週2コマの自立活動を配置
            jiritsu_count = self._count_subject_hours(schedule, exchange_ref, "自立")
            needed = 2 - jiritsu_count
            
            if needed <= 0:
                continue
            
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    if needed <= 0:
                        break
                    
                    time_slot = TimeSlot(day=day, period=period)
                    
                    # 既に配置済みならスキップ
                    if schedule.get_assignment(time_slot, exchange_ref):
                        continue
                    
                    # 親学級をチェック
                    parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                    if parent_assignment and parent_assignment.subject.name in ["数", "英"]:
                        # 配置可能
                        teacher = self._get_teacher_for_class_subject(school, exchange_ref, "自立")
                        if teacher and self._is_teacher_available(teacher.name, day, period):
                            assignment = Assignment(
                                class_ref=exchange_ref,
                                subject=Subject("自立"),
                                teacher=teacher
                            )
                            try:
                                schedule.assign(time_slot, assignment)
                                self._mark_teacher_busy(teacher.name, day, period)
                                placed += 1
                                needed -= 1
                                self.stats['jiritsu_placed'] += 1
                            except Exception:
                                pass
        
        logger.info(f"新規自立活動: {placed}スロット配置")
    
    def _place_regular_classes(self, schedule: Schedule, school: School) -> None:
        """通常授業の配置（バックトラッキング）"""
        logger.info("【フェーズ6: 通常授業の配置】")
        
        # 空きスロットを収集
        empty_slots = []
        for class_ref in school.get_all_classes():
            # 5組・6組・7組は特別扱い
            if class_ref.class_number in [5, 6, 7]:
                continue
            
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day=day, period=period)
                    
                    if not schedule.get_assignment(time_slot, class_ref):
                        empty_slots.append((time_slot, class_ref))
        
        # ランダムに並べ替え
        random.shuffle(empty_slots)
        
        # バックトラッキングで配置
        placed = self._backtrack_placement(schedule, school, empty_slots, 0)
        
        logger.info(f"通常授業: {placed}スロット配置")
        self.stats['placed_assignments'] += placed
    
    def _sync_exchange_with_parent(self, schedule: Schedule, school: School) -> None:
        """交流学級と親学級の最終同期"""
        logger.info("【フェーズ7: 交流学級の最終同期】")
        synced = 0
        
        for exchange_name, parent_name in self.exchange_parent_map.items():
            grade, class_num = exchange_name.split("-")
            exchange_ref = self._get_class_ref(school, int(grade), int(class_num))
            parent_grade, parent_num = parent_name.split("-")
            parent_ref = self._get_class_ref(school, int(parent_grade), int(parent_num))
            
            if not exchange_ref or not parent_ref:
                continue
            
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day=day, period=period)
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_ref)
                    parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                    
                    # 交流学級が自立活動の場合はスキップ
                    if exchange_assignment and exchange_assignment.subject.name == "自立":
                        continue
                    
                    # 親学級に合わせて同期
                    if parent_assignment and not exchange_assignment:
                        # 親学級の授業を交流学級にコピー
                        assignment = Assignment(
                            class_ref=exchange_ref,
                            subject=parent_assignment.subject,
                            teacher=parent_assignment.teacher
                        )
                        try:
                            schedule.assign(time_slot, assignment)
                            synced += 1
                            self.stats['exchange_sync_count'] += 1
                        except Exception:
                            pass
                    elif parent_assignment and exchange_assignment:
                        # 既存配置が違う場合は修正
                        if exchange_assignment.subject.name != parent_assignment.subject.name:
                            schedule.remove_assignment(time_slot, exchange_ref)
                            assignment = Assignment(
                                class_ref=exchange_ref,
                                subject=parent_assignment.subject,
                                teacher=parent_assignment.teacher
                            )
                            try:
                                schedule.assign(time_slot, assignment)
                                synced += 1
                                self.stats['exchange_violations_fixed'] += 1
                            except Exception:
                                pass
        
        logger.info(f"交流学級同期: {synced}スロット")
    
    def _backtrack_placement(self, schedule: Schedule, school: School,
                            empty_slots: List[Tuple[TimeSlot, ClassRef]],
                            index: int) -> int:
        """バックトラッキングで配置（教師重複を防ぐ）"""
        if index >= len(empty_slots):
            return 0
        
        time_slot, class_ref = empty_slots[index]
        
        # 配置可能な科目と教師を取得
        candidates = self._get_placement_candidates(schedule, school, class_ref, time_slot)
        
        if not candidates:
            # このスロットは配置できない
            return self._backtrack_placement(schedule, school, empty_slots, index + 1)
        
        # ランダムに並べ替え
        random.shuffle(candidates)
        
        for subject, teacher in candidates:
            # 教師の重複チェック（ここで厳密にチェック）
            if teacher and not self._is_teacher_available(teacher.name, time_slot.day, time_slot.period):
                self.stats['teacher_conflicts_avoided'] += 1
                continue
            
            # 制約チェック
            assignment = Assignment(
                class_ref=class_ref,
                subject=Subject(subject),
                teacher=teacher
            )
            
            try:
                # 配置
                schedule.assign(time_slot, assignment)
                if teacher:
                    self._mark_teacher_busy(teacher.name, time_slot.day, time_slot.period)
                
                # 次のスロットを再帰的に配置
                placed = 1 + self._backtrack_placement(schedule, school, empty_slots, index + 1)
                
                if placed > 0:
                    # 成功
                    return placed
                else:
                    # 失敗したので戻す
                    schedule.remove_assignment(time_slot, class_ref)
                    if teacher:
                        self._mark_teacher_available(teacher.name, time_slot.day, time_slot.period)
                    self.stats['backtrack_count'] += 1
                    
            except Exception:
                # 配置できなかった
                continue
        
        # このスロットは配置できなかった
        return self._backtrack_placement(schedule, school, empty_slots, index + 1)
    
    def _get_placement_candidates(self, schedule: Schedule, school: School,
                                 class_ref: ClassRef, time_slot: TimeSlot) -> List[Tuple[str, Optional[Teacher]]]:
        """配置可能な科目と教師の組み合わせを取得（通常学級用）"""
        candidates = []
        
        # 必要な科目を取得
        needed_subjects = self._get_needed_subjects(schedule, school, class_ref)
        
        for subject, needed_hours in needed_subjects.items():
            if needed_hours <= 0:
                continue
            
            # 日内重複チェック
            if self._would_create_daily_duplicate(schedule, class_ref, time_slot, subject):
                continue
            
            # このクラス・科目の正しい教師を取得
            teacher = self._get_teacher_for_class_subject(school, class_ref, subject)
            
            if teacher:
                # 教師が利用可能かチェック
                if self._is_teacher_available(teacher.name, time_slot.day, time_slot.period):
                    candidates.append((subject, teacher))
                else:
                    # 教師が利用不可
                    logger.debug(f"{class_ref} {subject}: {teacher.name}先生は{time_slot.day}{time_slot.period}限に利用不可")
            else:
                # 教師が見つからない場合も候補に含める（エラーにはしない）
                candidates.append((subject, None))
        
        return candidates
    
    def _get_teacher_for_class_subject(self, school: School, class_ref: ClassRef, subject: str) -> Optional[Teacher]:
        """クラスと科目の組み合わせから正しい教師を取得"""
        subject_obj = Subject(subject)
        
        # schoolから割り当てられた教師を取得
        teacher = school.get_assigned_teacher(subject_obj, class_ref)
        
        if teacher:
            logger.debug(f"{class_ref} {subject} → {teacher.name}先生")
            return teacher
        else:
            logger.warning(f"{class_ref} {subject}の担当教師が見つかりません")
            return None
    
    def _is_teacher_available(self, teacher_name: str, day: str, period: int) -> bool:
        """教師が利用可能かチェック"""
        if teacher_name not in self.teacher_availability:
            return True
        
        available = (day, period) in self.teacher_availability[teacher_name]
        
        if not available:
            logger.debug(f"{teacher_name}先生は{day}{period}限に利用不可")
        
        return available
    
    def _mark_teacher_busy(self, teacher_name: str, day: str, period: int) -> None:
        """教師を利用不可にマーク"""
        if teacher_name in self.teacher_availability:
            self.teacher_availability[teacher_name].discard((day, period))
    
    def _mark_teacher_available(self, teacher_name: str, day: str, period: int) -> None:
        """教師を利用可能にマーク"""
        if teacher_name in self.teacher_availability:
            self.teacher_availability[teacher_name].add((day, period))
    
    def _select_subject_for_grade5(self, schedule: Schedule, school: School, 
                                   time_slot: TimeSlot) -> Optional[str]:
        """5組用の科目を選択"""
        # 週間必要時数
        required = {
            "日生": 3, "自立": 6, "作業": 3,
            "国": 4, "数": 3, "社": 3, "理": 3, "英": 3,
            "音": 1, "美": 1, "保": 3, "技": 1, "家": 1
        }
        
        # 現在の時数をカウント（3クラス分の平均）
        current_hours = defaultdict(int)
        grade5_classes = [self._get_class_ref(school, g, 5) for g in [1, 2, 3]]
        grade5_classes = [c for c in grade5_classes if c]
        
        for c in grade5_classes:
            for subject, hours in self._count_all_subjects(schedule, c).items():
                current_hours[subject] += hours
        
        # 平均を計算
        for subject in current_hours:
            current_hours[subject] = current_hours[subject] // len(grade5_classes)
        
        # 必要時数が多い科目を優先
        candidates = []
        for subject, required_hours in required.items():
            if subject in self.fixed_subjects:
                continue
            
            needed = required_hours - current_hours[subject]
            if needed > 0:
                # 日内重複チェック（1つの5組でチェック）
                if not self._would_create_grade5_daily_duplicate(schedule, grade5_classes[0], time_slot, subject):
                    candidates.append((subject, needed))
        
        if not candidates:
            return None
        
        # 必要時数が多い順にソート
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        # 上位からランダムに選択
        top_candidates = [c[0] for c in candidates[:3]]
        return random.choice(top_candidates)
    
    def _get_needed_subjects(self, schedule: Schedule, school: School, 
                            class_ref: ClassRef) -> Dict[str, int]:
        """必要な科目と時数を取得"""
        # 固定科目は除外
        if class_ref.class_number == 5:
            # 5組用
            required = {
                "日生": 3, "自立": 6, "作業": 3,
                "国": 4, "数": 3, "社": 3, "理": 3, "英": 3,
                "音": 1, "美": 1, "保": 3, "技": 1, "家": 1
            }
        elif class_ref.class_number in [6, 7]:
            # 6組・7組には作業はない
            required = {
                "自立": 2, "日生": 1,
                "国": 4, "数": 3, "社": 3, "理": 3, "英": 3,
                "音": 1, "美": 1, "保": 3, "技": 1, "家": 1
            }
        else:
            # 通常学級
            required = {
                "国": 4, "数": 3, "社": 3, "理": 3, "英": 3,
                "音": 1, "美": 1, "保": 3, "技": 1, "家": 1
            }
        
        # 現在の時数をカウント
        current_hours = self._count_all_subjects(schedule, class_ref)
        
        # 必要時数を計算
        needed = {}
        for subject, req_hours in required.items():
            if subject not in self.fixed_subjects:
                needed[subject] = req_hours - current_hours.get(subject, 0)
        
        return needed
    
    def _count_subject_hours(self, schedule: Schedule, class_ref: ClassRef, subject: str) -> int:
        """特定科目の現在の時数をカウント"""
        count = 0
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day=day, period=period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject.name == subject:
                    count += 1
        return count
    
    def _count_all_subjects(self, schedule: Schedule, class_ref: ClassRef) -> Dict[str, int]:
        """全科目の現在の時数をカウント"""
        hours = defaultdict(int)
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day=day, period=period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment:
                    hours[assignment.subject.name] += 1
        return dict(hours)
    
    def _would_create_daily_duplicate(self, schedule: Schedule, class_ref: ClassRef,
                                     time_slot: TimeSlot, subject: str) -> bool:
        """日内重複を作るかチェック"""
        for period in range(1, 7):
            if period == time_slot.period:
                continue
            
            other_slot = TimeSlot(day=time_slot.day, period=period)
            assignment = schedule.get_assignment(other_slot, class_ref)
            
            if assignment and assignment.subject.name == subject:
                return True
        
        return False
    
    def _would_create_grade5_daily_duplicate(self, schedule: Schedule,
                                            class_ref: ClassRef,
                                            time_slot: TimeSlot,
                                            subject: str) -> bool:
        """5組の日内重複チェック"""
        return self._would_create_daily_duplicate(schedule, class_ref, time_slot, subject)
    
    def _get_class_ref(self, school: School, grade: int, class_num: int) -> Optional[ClassRef]:
        """指定された学年・クラス番号のClassRefを取得"""
        for class_ref in school.get_all_classes():
            if class_ref.grade == grade and class_ref.class_number == class_num:
                return class_ref
        return None
    
    def _print_statistics(self, schedule: Schedule, school: School) -> None:
        """統計情報を出力"""
        logger.info("=== 生成統計 ===")
        logger.info(f"初期割り当て数: {self.stats['initial_assignments']}")
        logger.info(f"既存教師割り当て検出数: {self.stats['existing_teacher_assignments']}")
        logger.info(f"新規配置数: {self.stats['placed_assignments']}")
        logger.info(f"自立活動配置数: {self.stats['jiritsu_placed']}")
        logger.info(f"自立活動違反修正数: {self.stats['jiritsu_violations_fixed']}")
        logger.info(f"交流学級同期数: {self.stats['exchange_sync_count']}")
        logger.info(f"交流学級違反検出数: {self.stats['exchange_violations_fixed']}")
        logger.info(f"教師重複回避数: {self.stats['teacher_conflicts_avoided']}")
        logger.info(f"バックトラック回数: {self.stats['backtrack_count']}")
        
        # 最終割り当て数
        final_assignments = len(schedule.get_all_assignments())
        logger.info(f"最終割り当て数: {final_assignments}")
        
        # 教師重複のチェック（デバッグ用）
        teacher_conflicts = 0
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day=day, period=period)
                
                # テスト期間はスキップ
                if (day, period) in self.test_periods:
                    continue
                
                teacher_assignments = defaultdict(list)
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        teacher_assignments[assignment.teacher.name].append(class_ref)
                
                for teacher_name, classes in teacher_assignments.items():
                    if len(classes) > 1:
                        # 5組の合同授業は除外
                        if not all(c.class_number == 5 for c in classes):
                            teacher_conflicts += 1
                            logger.warning(f"{time_slot.day}{time_slot.period}限: {teacher_name}先生が重複 - {[str(c) for c in classes]}")
        
        logger.info(f"教師重複数: {teacher_conflicts} (テスト期間を除く)")
        self.stats['teacher_duplicates_found'] = teacher_conflicts