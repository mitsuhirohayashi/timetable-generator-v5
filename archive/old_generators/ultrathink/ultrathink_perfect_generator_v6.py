#!/usr/bin/env python3
"""
Ultrathink Perfect Generator V6（修正版）
最初から完璧な時間割を生成するための革新的なジェネレーター

V5からの改善点：
1. 「作業」は5組専用科目として正しく処理
2. 交流学級の6限への自立活動配置を防止
3. 交流学級同期を強化（自立・日生・作業以外は必ず親学級と同じ）
4. 自立活動の配置条件を厳格化
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


class UltrathinkPerfectGeneratorV6:
    """最初から完璧な時間割を生成する革新的ジェネレーター（V6）"""
    
    def __init__(self):
        self.stats = {
            'initial_assignments': 0,
            'placed_assignments': 0,
            'backtrack_count': 0,
            'conflicts_avoided': 0,
            'jiritsu_placed': 0,
            'jiritsu_violations_fixed': 0,
            'exchange_sync_count': 0
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
        
        # 特別科目（交流学級専用）
        self.exchange_special_subjects = {"自立", "日生", "作業"}
    
    def generate(self, school: School, constraints: List[Constraint],
                 initial_schedule: Optional[Schedule] = None) -> Schedule:
        """完璧な時間割を生成"""
        logger.info("=== Ultrathink Perfect Generator V6 開始 ===")
        
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
        
        # 5. 自立活動の配置（親学級が適切な科目の時のみ、6限は除外）
        self._place_jiritsu_activities(schedule, school)
        
        # 6. 通常科目の配置（バックトラッキング付き）
        self._place_regular_subjects_with_backtracking(schedule, school)
        
        # 7. 交流学級の同期（強化版）
        self._synchronize_exchange_classes_enhanced(schedule, school)
        
        # 8. 最終検証と修正
        self._final_validation_and_fix(schedule, school)
        
        # 統計情報を出力
        self._print_statistics(schedule, school)
        
        return schedule
    
    def _validate_and_fix_existing_jiritsu(self, schedule: Schedule, school: School) -> None:
        """既存の自立活動を検証し、違反があれば修正"""
        logger.info("【フェーズ3: 既存の自立活動の検証と修正】")
        
        violations_fixed = 0
        
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
                    if exchange_assignment and exchange_assignment.subject.name == "自立":
                        # 親学級の科目をチェック
                        parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                        
                        # 6限に自立活動がある場合は削除
                        if period == 6:
                            logger.warning(f"6限の自立活動を削除: {exchange_ref} {time_slot}")
                            schedule.remove_assignment(time_slot, exchange_ref)
                            violations_fixed += 1
                            continue
                        
                        # 親学級が数学/英語でない場合は削除
                        if not parent_assignment or parent_assignment.subject.name not in ["数", "英"]:
                            logger.warning(f"自立活動違反を修正: {exchange_ref} {time_slot} (親: {parent_assignment.subject.name if parent_assignment else 'なし'})")
                            schedule.remove_assignment(time_slot, exchange_ref)
                            violations_fixed += 1
        
        self.stats['jiritsu_violations_fixed'] = violations_fixed
        if violations_fixed > 0:
            logger.info(f"自立活動違反を{violations_fixed}件修正しました")
    
    def _place_jiritsu_activities(self, schedule: Schedule, school: School) -> None:
        """自立活動の配置（親学級が数学/英語の時のみ、6限は絶対に除外）"""
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
                for period in range(1, 6):  # 6限は絶対に除外
                    time_slot = TimeSlot(day=day, period=period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name == "自立":
                        current_jiritsu += 1
            
            # 自立活動を配置
            jiritsu_placed = current_jiritsu
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 6):  # 6限は絶対に除外
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
    
    def _synchronize_exchange_classes_enhanced(self, schedule: Schedule, school: School) -> None:
        """交流学級の同期（強化版）"""
        logger.info("【フェーズ7: 交流学級の同期（強化版）】")
        synced = 0
        fixed = 0
        
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
                    
                    # 交流学級に特別科目（自立・日生・作業）がある場合はスキップ
                    if exchange_assignment and exchange_assignment.subject.name in self.exchange_special_subjects:
                        continue
                    
                    # 親学級に通常授業がある場合
                    if parent_assignment and parent_assignment.subject.name not in self.fixed_subjects:
                        # 交流学級が空きの場合
                        if not exchange_assignment:
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
                        # 交流学級に異なる授業がある場合
                        elif (exchange_assignment.subject.name != parent_assignment.subject.name and
                              exchange_assignment.subject.name not in self.exchange_special_subjects):
                            # 親学級と同じ授業に修正
                            logger.warning(f"交流学級同期修正: {exchange_ref} {time_slot} {exchange_assignment.subject.name} → {parent_assignment.subject.name}")
                            schedule.remove_assignment(time_slot, exchange_ref)
                            sync_assignment = Assignment(
                                class_ref=exchange_ref,
                                subject=parent_assignment.subject,
                                teacher=parent_assignment.teacher
                            )
                            try:
                                schedule.assign(time_slot, sync_assignment)
                                fixed += 1
                            except Exception:
                                pass
        
        self.stats['exchange_sync_count'] = synced + fixed
        logger.info(f"交流学級同期: {synced}スロット追加、{fixed}スロット修正")
    
    def _get_needed_subjects(self, schedule: Schedule, school: School,
                            class_ref: ClassRef) -> Dict[str, int]:
        """必要な科目と時数を取得（固定科目を除外、作業は5組のみ）"""
        # 標準時数
        if class_ref.class_number == 5:
            # 5組のみ作業がある
            required = {
                "国": 4, "社": 1, "数": 4, "理": 3, "音": 1,
                "美": 1, "保": 2, "技": 1, "家": 1, "英": 2,
                "自立": 3, "日生": 1, "作業": 1
            }
        elif class_ref.class_number in [6, 7]:
            # 6組・7組には作業はない
            required = {
                "自立": 2, "日生": 1,  # 作業を削除
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
                time_slot = TimeSlot(day=day, period=period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment:
                    current[assignment.subject.name] += 1
        
        # 必要時数を計算（固定科目を除外）
        needed = {}
        for subject, hours in required.items():
            if subject in self.fixed_subjects:
                continue
            need = hours - current.get(subject, 0)
            if need > 0:
                needed[subject] = need
        
        return needed
    
    def _final_validation_and_fix(self, schedule: Schedule, school: School) -> None:
        """最終検証と修正"""
        logger.info("【フェーズ8: 最終検証と修正】")
        
        # 交流学級の「作業」を削除
        for exchange_name in ["1-6", "1-7", "2-6", "2-7", "3-6", "3-7"]:
            grade, class_num = exchange_name.split("-")
            exchange_ref = self._get_class_ref(school, int(grade), int(class_num))
            
            if not exchange_ref:
                continue
            
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day=day, period=period)
                    assignment = schedule.get_assignment(time_slot, exchange_ref)
                    
                    if assignment and assignment.subject.name == "作業":
                        logger.warning(f"交流学級から作業を削除: {exchange_ref} {time_slot}")
                        schedule.remove_assignment(time_slot, exchange_ref)
    
    # 以下、V5から変更のないヘルパーメソッドは省略（必要に応じて追加）
    def _initialize_teacher_availability(self, school: School) -> Dict[str, Set[Tuple[str, int]]]:
        """教師の利用可能時間を初期化"""
        availability = {}
        for teacher in school.get_all_teachers():
            availability[teacher.name] = set()
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    availability[teacher.name].add((day, period))
        return availability
    
    def _place_test_periods_only(self, schedule: Schedule, school: School) -> None:
        """テスト期間の配置のみ（固定科目の新規配置はしない）"""
        logger.info("【フェーズ1: テスト期間の配置】")
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
                    
                    # 5組以外のクラスに配置
                    if class_ref.class_number != 5:
                        teacher = self._find_available_teacher(school, subject, time_slot)
                        if teacher:
                            assignment = Assignment(
                                class_ref=class_ref,
                                subject=Subject(subject),
                                teacher=teacher
                            )
                            try:
                                schedule.assign(time_slot, assignment)
                                placed += 1
                            except Exception:
                                pass
        
        logger.info(f"テスト期間: {placed}スロット配置")
        self.stats['placed_assignments'] += placed
    
    def _place_grade5_synchronized(self, schedule: Schedule, school: School) -> None:
        """5組の同期配置"""
        # V5と同じ実装
        logger.info("【フェーズ2: 5組の同期配置】")
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
                
                # 教師を探す（金子み先生を優先）
                teacher = None
                for t in school.get_all_teachers():
                    if t.name == "金子み" and subject in [s.name for s in t.subjects]:
                        teacher = t
                        break
                
                if not teacher:
                    teacher = self._find_available_teacher(school, subject, time_slot)
                
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
                        self._mark_teacher_busy(teacher.name, day, period)
        
        logger.info(f"5組同期配置: {placed // 3}スロット")
        self.stats['placed_assignments'] += placed
    
    def _prepare_jiritsu_placement(self, schedule: Schedule, school: School) -> None:
        """自立活動の準備（親学級に数学/英語を優先配置）"""
        # V5と同じ実装
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
    
    def _place_regular_subjects_with_backtracking(self, schedule: Schedule, school: School) -> None:
        """通常科目の配置（バックトラッキング付き）"""
        # V5と同じ実装だが、6限への交流学級の特別科目配置を防ぐ
        logger.info("【フェーズ6: 通常科目の配置】")
        
        # 空きスロットを収集
        empty_slots = []
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day=day, period=period)
                
                # テスト期間はスキップ
                if (day, period) in self.test_periods:
                    continue
                
                for class_ref in school.get_all_classes():
                    if not schedule.get_assignment(time_slot, class_ref):
                        # 6限の交流学級には特別科目を配置しない
                        if period == 6 and class_ref.class_number in [6, 7]:
                            continue
                        empty_slots.append((time_slot, class_ref))
        
        logger.info(f"{len(empty_slots)}個の空きスロットを検出")
        
        # バックトラッキングで配置
        placed = self._backtrack_placement(schedule, school, empty_slots, 0)
        
        self.stats['placed_assignments'] += placed
        logger.info(f"通常科目配置: {placed}スロット")
    
    def _backtrack_placement(self, schedule: Schedule, school: School,
                            empty_slots: List[Tuple[TimeSlot, ClassRef]], index: int) -> int:
        """バックトラッキングによる配置"""
        if index >= len(empty_slots):
            return 0
        
        time_slot, class_ref = empty_slots[index]
        
        # 配置可能な科目を取得
        candidates = self._get_placement_candidates(schedule, school, class_ref, time_slot)
        
        # ランダムに並べ替え
        random.shuffle(candidates)
        
        for subject, teacher in candidates:
            # 制約チェック
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
    
    # ヘルパーメソッド（V5から変更なし）
    def _get_class_ref(self, school: School, grade: int, class_num: int) -> Optional[ClassRef]:
        """クラス参照を取得"""
        for class_ref in school.get_all_classes():
            if class_ref.grade == grade and class_ref.class_number == class_num:
                return class_ref
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
    
    def _print_statistics(self, schedule: Schedule, school: School) -> None:
        """統計情報を出力"""
        logger.info("=== 生成統計 ===")
        logger.info(f"初期割り当て数: {self.stats['initial_assignments']}")
        logger.info(f"新規配置数: {self.stats['placed_assignments']}")
        logger.info(f"自立活動配置数: {self.stats['jiritsu_placed']}")
        logger.info(f"自立活動違反修正数: {self.stats['jiritsu_violations_fixed']}")
        logger.info(f"交流学級同期数: {self.stats['exchange_sync_count']}")
        logger.info(f"バックトラック回数: {self.stats['backtrack_count']}")
        
        # 最終的な割り当て数をカウント
        final_assignments = len(schedule.get_all_assignments())
        logger.info(f"最終割り当て数: {final_assignments}")
        
        # 教師重複数をカウント（テスト期間を除く）
        teacher_conflicts = 0
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                if (day, period) in self.test_periods:
                    continue
                
                time_slot = TimeSlot(day=day, period=period)
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
        
        logger.info(f"教師重複数: {teacher_conflicts} (テスト期間を除く)")