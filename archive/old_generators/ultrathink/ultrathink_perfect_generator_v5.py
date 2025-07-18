#!/usr/bin/env python3
"""
Ultrathink Perfect Generator V5（最終版）
最初から完璧な時間割を生成するための革新的なジェネレーター

V4からの改善点：
1. 空白スロットに固定科目を勝手に配置しない
2. input.csvの内容を完全に尊重
3. 既存の内容がある場合のみ、それを保護
4. 空白スロットは通常教科で埋める
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


class UltrathinkPerfectGeneratorV5:
    """最初から完璧な時間割を生成する革新的ジェネレーター（V5）"""
    
    def __init__(self):
        self.stats = {
            'initial_assignments': 0,
            'placed_assignments': 0,
            'backtrack_count': 0,
            'conflicts_avoided': 0,
            'jiritsu_placed': 0,
            'jiritsu_violations_fixed': 0
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
    
    def generate(self, school: School, constraints: List[Constraint],
                 initial_schedule: Optional[Schedule] = None) -> Schedule:
        """完璧な時間割を生成"""
        logger.info("=== Ultrathink Perfect Generator V5 開始 ===")
        
        # 初期化
        schedule = initial_schedule or Schedule()
        self.stats['initial_assignments'] = len(schedule.get_all_assignments())
        logger.info(f"初期割り当て数: {self.stats['initial_assignments']}")
        
        # 教師の利用可能時間を追跡
        self.teacher_availability = self._initialize_teacher_availability(school)
        
        # 1. テスト期間の配置のみ（固定科目は既存のものを保護するだけ）
        self._place_test_periods_only(schedule, school)
        
        # 2. 5組の同期配置
        self._place_grade5_synchronized(schedule, school)
        
        # 3. 既存の自立活動の検証と修正
        self._validate_and_fix_existing_jiritsu(schedule, school)
        
        # 4. 交流学級の自立活動準備（親学級に数学/英語を優先配置）
        self._prepare_jiritsu_placement(schedule, school)
        
        # 5. 自立活動の配置（親学級が適切な科目の時のみ）
        self._place_jiritsu_activities(schedule, school)
        
        # 6. 通常科目の配置（バックトラッキング付き）
        self._place_regular_subjects_with_backtracking(schedule, school)
        
        # 7. 交流学級の同期
        self._synchronize_exchange_classes(schedule, school)
        
        # 8. 統計情報
        self._log_statistics(schedule, school)
        
        return schedule
    
    def _initialize_teacher_availability(self, school: School) -> Dict[str, Set[Tuple[str, int]]]:
        """教師の利用可能時間を初期化"""
        availability = {}
        all_slots = {(day, period) for day in ["月", "火", "水", "木", "金"] for period in range(1, 7)}
        
        for teacher in school.get_all_teachers():
            availability[teacher.name] = all_slots.copy()
        
        return availability
    
    def _place_test_periods_only(self, schedule: Schedule, school: School) -> None:
        """テスト期間の配置のみ（固定科目の新規配置はしない）"""
        logger.info("【フェーズ1: テスト期間の配置】")
        placed = 0
        
        # テスト期間の配置
        test_supervisors = {
            "1": {"英": "井野口", "保": "野口", "技家": "池田", "社": "梶永", "音": "山口", "国": "塚本", "理": "永山", "数": "永山"},
            "2": {"数": "井上", "技家": "池田", "社": "北", "国": "塚本", "保": "野口", "理": "永山", "英": "小野塚", "音": "山口"},
            "3": {"国": "塚本", "音": "山口", "理": "福山", "数": "小野塚", "英": "林", "技家": "池田", "保": "野口", "社": "北"}
        }
        
        for (day, period), grade_subjects in self.test_subjects.items():
            time_slot = TimeSlot(day=day, period=period)
            
            for class_ref in school.get_all_classes():
                # 5組は除外
                if class_ref.class_number == 5:
                    continue
                
                grade_str = str(class_ref.grade)
                if grade_str in grade_subjects:
                    subject = grade_subjects[grade_str]
                    
                    if schedule.is_locked(time_slot, class_ref):
                        continue
                    
                    # 既に何か配置されている場合はスキップ
                    if schedule.get_assignment(time_slot, class_ref):
                        continue
                    
                    # テスト監督教師を取得
                    supervisor_name = test_supervisors.get(grade_str, {}).get(subject)
                    teacher = None
                    if supervisor_name:
                        for t in school.get_all_teachers():
                            if t.name == supervisor_name:
                                teacher = t
                                break
                    
                    if teacher:
                        assignment = Assignment(
                            class_ref=class_ref,
                            subject=Subject(subject),
                            teacher=teacher
                        )
                        try:
                            schedule.assign(time_slot, assignment)
                            placed += 1
                        except Exception as e:
                            logger.debug(f"テスト期間配置エラー: {e}")
        
        self.stats['placed_assignments'] += placed
        logger.info(f"テスト期間: {placed}スロット配置")
    
    def _validate_and_fix_existing_jiritsu(self, schedule: Schedule, school: School) -> None:
        """既存の自立活動を検証し、違反があれば修正"""
        logger.info("【フェーズ3: 既存の自立活動の検証と修正】")
        fixed_count = 0
        
        for exchange_name, parent_name in self.exchange_parent_map.items():
            grade, class_num = exchange_name.split("-")
            exchange_ref = self._get_class_ref(school, int(grade), int(class_num))
            
            parent_grade, parent_class = parent_name.split("-")
            parent_ref = self._get_class_ref(school, int(parent_grade), int(parent_class))
            
            if not exchange_ref or not parent_ref:
                continue
            
            # 全ての時間スロットをチェック
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day=day, period=period)
                    
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_ref)
                    if exchange_assignment and exchange_assignment.subject.name == "自立":
                        # 親学級の科目をチェック
                        parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                        
                        if not parent_assignment or parent_assignment.subject.name not in ["数", "英"]:
                            # 違反している自立活動を削除
                            logger.warning(
                                f"違反: {exchange_ref} {time_slot} の自立活動 "
                                f"(親学級: {parent_assignment.subject.name if parent_assignment else '空き'})"
                            )
                            
                            try:
                                # ロックされている場合は一時的に解除
                                was_locked = schedule.is_locked(time_slot, exchange_ref)
                                if was_locked:
                                    schedule.unlock_cell(time_slot, exchange_ref)
                                
                                schedule.remove_assignment(time_slot, exchange_ref)
                                fixed_count += 1
                                
                                # ロックを復元
                                if was_locked:
                                    schedule.lock_cell(time_slot, exchange_ref)
                                
                                logger.info(f"違反した自立活動を削除: {exchange_ref} {time_slot}")
                                
                                # 親学級と同じ授業を受けるように同期
                                if parent_assignment and parent_assignment.subject.name not in self.fixed_subjects:
                                    sync_assignment = Assignment(
                                        class_ref=exchange_ref,
                                        subject=parent_assignment.subject,
                                        teacher=parent_assignment.teacher
                                    )
                                    try:
                                        schedule.assign(time_slot, sync_assignment)
                                        logger.info(f"親学級と同期: {exchange_ref} {time_slot} -> {parent_assignment.subject.name}")
                                    except Exception:
                                        pass
                            except Exception as e:
                                logger.debug(f"自立活動修正エラー: {e}")
        
        if fixed_count > 0:
            self.stats['jiritsu_violations_fixed'] = fixed_count
            logger.info(f"既存の自立活動違反を{fixed_count}件修正しました")
    
    def _prepare_jiritsu_placement(self, schedule: Schedule, school: School) -> None:
        """自立活動の準備（親学級に数学/英語を優先配置）"""
        logger.info("【フェーズ4: 自立活動の準備】")
        
        # 自立活動が必要なスロットを特定
        jiritsu_slots = []
        
        for exchange_name, parent_name in self.exchange_parent_map.items():
            grade, class_num = exchange_name.split("-")
            exchange_ref = self._get_class_ref(school, int(grade), int(class_num))
            
            parent_grade, parent_class = parent_name.split("-")
            parent_ref = self._get_class_ref(school, int(parent_grade), int(parent_class))
            
            if not exchange_ref or not parent_ref:
                continue
            
            # 既存の自立活動をカウント
            current_jiritsu = 0
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day=day, period=period)
                    assignment = schedule.get_assignment(time_slot, exchange_ref)
                    if assignment and assignment.subject.name == "自立":
                        current_jiritsu += 1
            
            # 必要な自立活動時数（2時間）
            needed = 2 - current_jiritsu
            if needed > 0:
                # 配置可能なスロットを探す
                for day in ["月", "火", "水", "木", "金"]:
                    for period in range(1, 6):  # 6限は除外
                        time_slot = TimeSlot(day=day, period=period)
                        
                        # テスト期間はスキップ
                        if (day, period) in self.test_periods:
                            continue
                        
                        # 既に配置されているかチェック
                        if schedule.get_assignment(time_slot, exchange_ref):
                            continue
                        
                        # 親学級も空いているか
                        if not schedule.get_assignment(time_slot, parent_ref):
                            jiritsu_slots.append((exchange_ref, parent_ref, time_slot))
        
        # 親学級に数学または英語を優先的に配置
        for exchange_ref, parent_ref, time_slot in jiritsu_slots:
            # 数学を優先、次に英語
            for subject in ["数", "英"]:
                if self._would_create_daily_duplicate(schedule, parent_ref, time_slot, subject):
                    continue
                
                teacher = self._find_available_teacher(school, subject, time_slot)
                if teacher:
                    assignment = Assignment(
                        class_ref=parent_ref,
                        subject=Subject(subject),
                        teacher=teacher
                    )
                    try:
                        schedule.assign(time_slot, assignment)
                        if teacher.name in self.teacher_availability:
                            self.teacher_availability[teacher.name].discard((time_slot.day, time_slot.period))
                        self.stats['placed_assignments'] += 1
                        logger.debug(f"自立準備: {parent_ref} {time_slot} に {subject} を配置")
                        break
                    except Exception:
                        pass
    
    def _place_jiritsu_activities(self, schedule: Schedule, school: School) -> None:
        """自立活動の配置（親学級が数学/英語の時のみ）"""
        logger.info("【フェーズ5: 自立活動の配置】")
        placed = 0
        
        jiritsu_requirements = {
            "1-6": 2, "1-7": 2, "2-6": 2, "2-7": 2, "3-6": 2, "3-7": 2
        }
        
        jiritsu_teachers = {
            "1-6": "財津", "1-7": "智田",
            "2-6": "財津", "2-7": "智田",
            "3-6": "財津", "3-7": "智田"
        }
        
        for class_name, required_hours in jiritsu_requirements.items():
            grade, class_num = class_name.split("-")
            class_ref = self._get_class_ref(school, int(grade), int(class_num))
            if not class_ref:
                continue
            
            parent_name = self.exchange_parent_map.get(class_name)
            if not parent_name:
                continue
            
            parent_grade, parent_class = parent_name.split("-")
            parent_ref = self._get_class_ref(school, int(parent_grade), int(parent_class))
            if not parent_ref:
                continue
            
            # 現在の自立活動をカウント
            current_jiritsu = 0
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day=day, period=period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name == "自立":
                        current_jiritsu += 1
            
            # 自立活動を配置
            jiritsu_placed = current_jiritsu
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 6):  # 6限は除外
                    if jiritsu_placed >= required_hours:
                        break
                    
                    time_slot = TimeSlot(day=day, period=period)
                    
                    # テスト期間はスキップ
                    if (day, period) in self.test_periods:
                        continue
                    
                    # 既に配置されているかチェック
                    if schedule.get_assignment(time_slot, class_ref):
                        continue
                    
                    # 親学級の科目をチェック（必ず数学か英語でなければならない）
                    parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                    if parent_assignment and parent_assignment.subject.name in ["数", "英"]:
                        # 自立活動を配置
                        teacher_name = jiritsu_teachers.get(class_name)
                        teacher = None
                        if teacher_name:
                            for t in school.get_all_teachers():
                                if t.name == teacher_name:
                                    teacher = t
                                    break
                        
                        if teacher and self._is_teacher_available(teacher.name, day, period):
                            assignment = Assignment(
                                class_ref=class_ref,
                                subject=Subject("自立"),
                                teacher=teacher
                            )
                            try:
                                schedule.assign(time_slot, assignment)
                                jiritsu_placed += 1
                                placed += 1
                                self._mark_teacher_busy(teacher.name, day, period)
                                logger.debug(f"自立配置: {class_ref} {time_slot} (親: {parent_assignment.subject.name})")
                            except Exception as e:
                                logger.debug(f"自立活動配置エラー: {e}")
        
        self.stats['placed_assignments'] += placed
        self.stats['jiritsu_placed'] = placed
        logger.info(f"自立活動配置: {placed}スロット")
    
    def _place_grade5_synchronized(self, schedule: Schedule, school: School) -> None:
        """5組の同期配置"""
        logger.info("【フェーズ2: 5組の同期配置】")
        placed = 0
        
        grade5_classes = [c for c in school.get_all_classes() if c.class_number == 5]
        if not grade5_classes:
            return
        
        # 時間スロットごとに処理
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day=day, period=period)
                
                # テスト期間はスキップ
                if (day, period) in self.test_periods:
                    continue
                
                # 既に配置されているかチェック
                if any(schedule.get_assignment(time_slot, c) for c in grade5_classes):
                    continue
                
                # 配置する科目を決定
                subject = self._select_subject_for_grade5(schedule, school, time_slot)
                if not subject:
                    continue
                
                # 教師を探す
                teacher = self._find_available_teacher(school, subject, time_slot)
                if not teacher:
                    continue
                
                # 全ての5組に同じ科目・教師で配置
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
                    # 教師の利用可能時間を更新（5組は1人で3クラス担当可）
                    if teacher.name in self.teacher_availability:
                        self.teacher_availability[teacher.name].discard((day, period))
        
        self.stats['placed_assignments'] += placed
        logger.info(f"5組同期配置: {placed}スロット")
    
    def _place_regular_subjects_with_backtracking(self, schedule: Schedule, school: School) -> None:
        """通常科目の配置（バックトラッキング付き）"""
        logger.info("【フェーズ6: 通常科目の配置】")
        
        # 配置が必要なスロットを収集
        empty_slots = []
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day=day, period=period)
                    if not schedule.get_assignment(time_slot, class_ref):
                        empty_slots.append((class_ref, time_slot))
        
        # 優先度順にソート
        empty_slots.sort(key=lambda x: (
            0 if x[0].grade == 3 and x[0].class_number in [6, 7] else 1,
            x[0].grade,
            x[0].class_number
        ))
        
        logger.info(f"{len(empty_slots)}個の空きスロットを検出")
        
        # バックトラッキングで配置
        placed = self._backtrack_placement(schedule, school, empty_slots, 0)
        
        self.stats['placed_assignments'] += placed
        logger.info(f"通常科目配置: {placed}スロット")
    
    def _backtrack_placement(self, schedule: Schedule, school: School,
                            empty_slots: List[Tuple[ClassRef, TimeSlot]],
                            index: int) -> int:
        """バックトラッキングによる配置"""
        if index >= len(empty_slots):
            return 0  # 全て配置完了
        
        class_ref, time_slot = empty_slots[index]
        
        # このスロットに配置可能な科目と教師の組み合わせを取得
        candidates = self._get_placement_candidates(schedule, school, class_ref, time_slot)
        
        # ランダムに並び替えて多様性を確保
        random.shuffle(candidates)
        
        for subject, teacher in candidates:
            # 配置を試みる
            assignment = Assignment(
                class_ref=class_ref,
                subject=Subject(subject),
                teacher=teacher
            )
            
            try:
                # 配置
                schedule.assign(time_slot, assignment)
                if teacher and teacher.name in self.teacher_availability:
                    self.teacher_availability[teacher.name].discard((time_slot.day, time_slot.period))
                
                # 次のスロットを再帰的に配置
                placed = 1 + self._backtrack_placement(schedule, school, empty_slots, index + 1)
                
                if placed > 0:
                    # 成功
                    return placed
                else:
                    # 失敗したので戻す
                    schedule.remove_assignment(time_slot, class_ref)
                    if teacher and teacher.name in self.teacher_availability:
                        self.teacher_availability[teacher.name].add((time_slot.day, time_slot.period))
                    self.stats['backtrack_count'] += 1
                    
            except Exception:
                # 配置できなかった
                continue
        
        # このスロットは配置できなかった
        return self._backtrack_placement(schedule, school, empty_slots, index + 1)
    
    def _get_placement_candidates(self, schedule: Schedule, school: School,
                                 class_ref: ClassRef, time_slot: TimeSlot) -> List[Tuple[str, Optional[Teacher]]]:
        """配置可能な科目と教師の組み合わせを取得"""
        candidates = []
        
        # 必要な科目を取得
        needed_subjects = self._get_needed_subjects(schedule, school, class_ref)
        
        for subject, needed_hours in needed_subjects.items():
            if needed_hours <= 0:
                continue
            
            # 日内重複チェック
            if self._would_create_daily_duplicate(schedule, class_ref, time_slot, subject):
                continue
            
            # 教師を探す
            teachers = self._find_teachers_for_subject(school, class_ref, subject)
            
            for teacher in teachers:
                if teacher and not self._is_teacher_available(teacher.name, time_slot.day, time_slot.period):
                    continue
                
                candidates.append((subject, teacher))
            
            # 教師がいない場合も候補に含める
            if not teachers:
                candidates.append((subject, None))
        
        return candidates
    
    def _synchronize_exchange_classes(self, schedule: Schedule, school: School) -> None:
        """交流学級の同期"""
        logger.info("【フェーズ7: 交流学級の同期】")
        synced = 0
        
        for exchange_name, parent_name in self.exchange_parent_map.items():
            grade, class_num = exchange_name.split("-")
            exchange_ref = self._get_class_ref(school, int(grade), int(class_num))
            
            parent_grade, parent_class = parent_name.split("-")
            parent_ref = self._get_class_ref(school, int(parent_grade), int(parent_class))
            
            if not exchange_ref or not parent_ref:
                continue
            
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day=day, period=period)
                    
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_ref)
                    parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                    
                    # 交流学級が空きで、親学級に通常授業がある場合
                    if not exchange_assignment and parent_assignment:
                        subject_name = parent_assignment.subject.name
                        if subject_name not in ["自立", "日生", "作業"] and subject_name not in self.fixed_subjects:
                            # 同じ授業を受ける
                            sync_assignment = Assignment(
                                class_ref=exchange_ref,
                                subject=parent_assignment.subject,
                                teacher=parent_assignment.teacher
                            )
                            try:
                                schedule.assign(time_slot, sync_assignment)
                                synced += 1
                            except Exception:
                                pass
        
        logger.info(f"交流学級同期: {synced}スロット")
    
    # ヘルパーメソッド
    def _get_class_ref(self, school: School, grade: int, class_num: int) -> Optional[ClassRef]:
        """クラス参照を取得"""
        for class_ref in school.get_all_classes():
            if class_ref.grade == grade and class_ref.class_number == class_num:
                return class_ref
        return None
    
    def _get_homeroom_teacher(self, school: School, class_ref: ClassRef) -> Optional[Teacher]:
        """担任教師を取得"""
        homeroom_teachers = {
            (1, 1): "金子ひ", (1, 2): "井野口", (1, 3): "梶永",
            (2, 1): "塚本", (2, 2): "野口", (2, 3): "永山",
            (3, 1): "白石", (3, 2): "森山", (3, 3): "北",
            (1, 5): "金子み", (2, 5): "金子み", (3, 5): "金子み"
        }
        
        teacher_name = homeroom_teachers.get((class_ref.grade, class_ref.class_number))
        if teacher_name:
            for teacher in school.get_all_teachers():
                if teacher.name == teacher_name:
                    return teacher
        return None
    
    def _is_teacher_available(self, teacher_name: str, day: str, period: int) -> bool:
        """教師が利用可能かチェック"""
        if teacher_name not in self.teacher_availability:
            return True
        return (day, period) in self.teacher_availability[teacher_name]
    
    def _mark_teacher_busy(self, teacher_name: str, day: str, period: int) -> None:
        """教師を使用中にマーク"""
        if teacher_name in self.teacher_availability:
            self.teacher_availability[teacher_name].discard((day, period))
    
    def _select_subject_for_grade5(self, schedule: Schedule, school: School,
                                  time_slot: TimeSlot) -> Optional[str]:
        """5組に配置する科目を選択"""
        # 5組の標準時数
        required_hours = {
            "国": 4, "社": 1, "数": 4, "理": 3, "音": 1,
            "美": 1, "保": 2, "技": 1, "家": 1, "英": 2,
            "自立": 3, "日生": 1, "作業": 1
        }
        
        # 現在の配置数をカウント
        current_hours = defaultdict(int)
        grade5_classes = [c for c in school.get_all_classes() if c.class_number == 5]
        
        for c in grade5_classes:
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    ts = TimeSlot(day=day, period=period)
                    assignment = schedule.get_assignment(ts, c)
                    if assignment:
                        current_hours[assignment.subject.name] += 1
        
        # 各科目の実際の時数を計算（3クラス分なので3で割る）
        for subject in current_hours:
            current_hours[subject] //= len(grade5_classes)
        
        # 不足している科目から選択（固定科目を除外）
        candidates = []
        for subject, required in required_hours.items():
            if subject in self.fixed_subjects:
                continue
            current = current_hours.get(subject, 0)
            if current < required:
                # 日内重複チェック
                if not self._would_create_daily_duplicate_for_grade5(
                    schedule, grade5_classes[0], time_slot, subject
                ):
                    candidates.append(subject)
        
        return random.choice(candidates) if candidates else None
    
    def _find_available_teacher(self, school: School, subject: str,
                               time_slot: TimeSlot) -> Optional[Teacher]:
        """利用可能な教師を探す"""
        subject_obj = Subject(subject)
        teachers = list(school.get_subject_teachers(subject_obj))
        
        # テスト期間の場合は特別処理
        if (time_slot.day, time_slot.period) in self.test_periods:
            # テスト期間は同じ教師が複数クラスを担当可能
            return teachers[0] if teachers else None
        
        # 通常授業の場合
        random.shuffle(teachers)
        for teacher in teachers:
            if self._is_teacher_available(teacher.name, time_slot.day, time_slot.period):
                return teacher
        
        return None
    
    def _find_teachers_for_subject(self, school: School, class_ref: ClassRef,
                                  subject: str) -> List[Teacher]:
        """科目を教えられる教師を探す"""
        subject_obj = Subject(subject)
        return list(school.get_subject_teachers(subject_obj))
    
    def _would_create_daily_duplicate(self, schedule: Schedule, class_ref: ClassRef,
                                     time_slot: TimeSlot, subject: str) -> bool:
        """日内重複が発生するかチェック"""
        for period in range(1, 7):
            ts = TimeSlot(day=time_slot.day, period=period)
            assignment = schedule.get_assignment(ts, class_ref)
            if assignment and assignment.subject.name == subject:
                return True
        return False
    
    def _would_create_daily_duplicate_for_grade5(self, schedule: Schedule,
                                                class_ref: ClassRef,
                                                time_slot: TimeSlot,
                                                subject: str) -> bool:
        """5組の日内重複チェック"""
        return self._would_create_daily_duplicate(schedule, class_ref, time_slot, subject)
    
    def _get_needed_subjects(self, schedule: Schedule, school: School,
                            class_ref: ClassRef) -> Dict[str, int]:
        """必要な科目と時数を取得（固定科目を除外）"""
        # 標準時数
        if class_ref.class_number == 5:
            required = {
                "国": 4, "社": 1, "数": 4, "理": 3, "音": 1,
                "美": 1, "保": 2, "技": 1, "家": 1, "英": 2,
                "自立": 3, "日生": 1, "作業": 1
            }
        elif class_ref.class_number in [6, 7]:
            required = {
                "自立": 2, "日生": 1, "作業": 1,
                "国": 3, "社": 2, "数": 3, "理": 2, "音": 1,
                "美": 1, "保": 2, "技": 1, "家": 1, "英": 3
            }
        else:
            required = {
                "国": 4, "社": 3, "数": 4, "理": 3, "音": 1,
                "美": 1, "保": 3, "技": 1, "家": 1, "英": 4
            }
            # 学年による調整
            if class_ref.grade == 2:
                required["技家"] = 1
                required["技"] = 0
                required["家"] = 0
            elif class_ref.grade == 3:
                required["国"] = 3
                required["社"] = 4
                required["技"] = 0
                required["家"] = 0
        
        # 現在の時数をカウント
        current = defaultdict(int)
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                ts = TimeSlot(day=day, period=period)
                assignment = schedule.get_assignment(ts, class_ref)
                if assignment:
                    current[assignment.subject.name] += 1
        
        # 不足分を計算（固定科目を除外）
        needed = {}
        for subject, req in required.items():
            if subject in self.fixed_subjects:
                continue
            cur = current.get(subject, 0)
            if cur < req:
                needed[subject] = req - cur
        
        return needed
    
    def _log_statistics(self, schedule: Schedule, school: School) -> None:
        """統計情報をログ出力"""
        logger.info("=== 生成統計 ===")
        logger.info(f"初期割り当て数: {self.stats['initial_assignments']}")
        logger.info(f"新規配置数: {self.stats['placed_assignments']}")
        logger.info(f"自立活動配置数: {self.stats['jiritsu_placed']}")
        logger.info(f"自立活動違反修正数: {self.stats['jiritsu_violations_fixed']}")
        logger.info(f"バックトラック回数: {self.stats['backtrack_count']}")
        logger.info(f"最終割り当て数: {len(schedule.get_all_assignments())}")
        
        # 教師重複チェック
        conflicts = self._count_teacher_conflicts(schedule, school)
        logger.info(f"教師重複数: {conflicts} (テスト期間を除く)")
    
    def _count_teacher_conflicts(self, schedule: Schedule, school: School) -> int:
        """教師重複をカウント（テスト期間を除く）"""
        conflicts = 0
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                if (day, period) in self.test_periods:
                    continue  # テスト期間はスキップ
                
                time_slot = TimeSlot(day=day, period=period)
                teacher_assignments = defaultdict(list)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        teacher_assignments[assignment.teacher.name].append(class_ref)
                
                for teacher_name, classes in teacher_assignments.items():
                    if len(classes) > 1:
                        # 5組の合同授業は除外
                        grade5_classes = [c for c in classes if c.class_number == 5]
                        if len(grade5_classes) == len(classes):
                            continue
                        conflicts += 1
        
        return conflicts