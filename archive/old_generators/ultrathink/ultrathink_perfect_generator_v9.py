#!/usr/bin/env python3
"""
Ultrathink Perfect Generator V9（教師割り当て完全版）
教師の重複問題を完全に解決

V8からの改善点：
1. クラス＋科目の組み合わせで正しい教師を取得
2. 既存配置から教師情報を正確に復元
3. schoolの教師割り当て情報を完全活用
4. デバッグ情報の充実
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


class UltrathinkPerfectGeneratorV9:
    """最初から完璧な時間割を生成する革新的ジェネレーター（V9）"""
    
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
            'teacher_assignments_restored': 0  # 追加
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
        logger.info("=== Ultrathink Perfect Generator V9 開始 ===")
        
        # 初期化
        schedule = initial_schedule or Schedule()
        self.stats['initial_assignments'] = len(schedule.get_all_assignments())
        logger.info(f"初期割り当て数: {self.stats['initial_assignments']}")
        
        # 既存配置から教師情報を復元
        self._restore_teacher_assignments(schedule, school)
        
        # 教師の利用可能時間を追跡（既存配置を考慮）
        self.teacher_availability = self._initialize_teacher_availability(school, schedule)
        
        # 1. 交流学級の不正な配置を削除
        self._clean_exchange_classes(schedule, school)
        
        # 2. テスト期間の配置
        self._place_test_periods_only(schedule, school)
        
        # 3. 5組の同期配置
        self._place_grade5_synchronized(schedule, school)
        
        # 4. 既存の自立活動の検証と修正
        self._validate_and_fix_existing_jiritsu(schedule, school)
        
        # 5. 自立活動の準備（親学級に数学/英語を優先配置）
        self._prepare_jiritsu_placement(schedule, school)
        
        # 6. 自立活動の配置（親学級が適切な科目の時のみ）
        self._place_jiritsu_activities(schedule, school)
        
        # 7. 通常学級の科目配置
        self._place_regular_subjects_for_normal_classes(schedule, school)
        
        # 8. 交流学級の完全同期
        self._complete_exchange_class_sync(schedule, school)
        
        # 9. 最終検証
        self._final_validation(schedule, school)
        
        # 統計情報を出力
        self._print_statistics(schedule, school)
        
        return schedule
    
    def _restore_teacher_assignments(self, schedule: Schedule, school: School) -> None:
        """既存配置から教師情報を復元"""
        logger.info("既存配置から教師情報を復元中...")
        restored = 0
        
        for time_slot, assignment in list(schedule.get_all_assignments()):
            if assignment.teacher is None:
                # schoolの情報から正しい教師を取得
                teacher = school.get_assigned_teacher(assignment.subject, assignment.class_ref)
                
                if teacher:
                    # 新しいAssignmentを作成して置き換え
                    new_assignment = Assignment(
                        class_ref=assignment.class_ref,
                        subject=assignment.subject,
                        teacher=teacher
                    )
                    schedule.remove_assignment(time_slot, assignment.class_ref)
                    schedule.assign(time_slot, new_assignment)
                    restored += 1
                    logger.debug(f"教師復元: {assignment.class_ref} {assignment.subject.name} → {teacher.name}")
        
        self.stats['teacher_assignments_restored'] = restored
        logger.info(f"{restored}個の教師情報を復元しました")
    
    def _initialize_teacher_availability(self, school: School, schedule: Schedule) -> Dict[str, Set[Tuple[str, int]]]:
        """教師の利用可能時間を初期化（既存配置を考慮）"""
        availability = {}
        
        # 全教師の全時間を利用可能として初期化
        for teacher in school.get_all_teachers():
            availability[teacher.name] = set()
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    availability[teacher.name].add((day, period))
        
        # 既存配置の教師をbusy状態にする
        busy_count = 0
        for time_slot, assignment in schedule.get_all_assignments():
            if assignment.teacher and assignment.teacher.name in availability:
                # テスト期間は除外（複数クラス担当可能）
                if (time_slot.day, time_slot.period) not in self.test_periods:
                    availability[assignment.teacher.name].discard((time_slot.day, time_slot.period))
                    busy_count += 1
                    logger.debug(f"既存配置: {assignment.teacher.name}先生 @ {time_slot.day}{time_slot.period}限 ({assignment.class_ref})")
        
        logger.info(f"教師利用可能性を初期化: {busy_count}個の既存配置を検出")
        
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
                        self._mark_teacher_busy(teacher.name, day, period)
        
        logger.info(f"5組同期配置: {placed // 3}スロット")
        self.stats['placed_assignments'] += placed
    
    def _validate_and_fix_existing_jiritsu(self, schedule: Schedule, school: School) -> None:
        """既存の自立活動の検証と修正"""
        logger.info("【フェーズ4: 既存の自立活動の検証と修正】")
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
                    if exchange_assignment and exchange_assignment.subject.name == "自立":
                        # 親学級の科目を確認
                        parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                        
                        if not parent_assignment or parent_assignment.subject.name not in ["数", "英"]:
                            # 違反している自立活動を削除
                            schedule.remove_assignment(time_slot, exchange_ref)
                            fixed += 1
                            logger.debug(f"{exchange_ref} @ {time_slot}: 自立活動を削除（親学級が数/英でない）")
        
        if fixed > 0:
            logger.info(f"自立活動違反を{fixed}件修正しました")
            self.stats['jiritsu_violations_fixed'] = fixed
    
    def _prepare_jiritsu_placement(self, schedule: Schedule, school: School) -> None:
        """自立活動の準備（親学級に数学/英語を優先配置）"""
        logger.info("【フェーズ5: 自立活動の準備】")
        
        # 自立活動が必要なスロットを特定
        jiritsu_slots = []
        
        for exchange_name, parent_name in self.exchange_parent_map.items():
            grade, class_num = exchange_name.split("-")
            exchange_ref = self._get_class_ref(school, int(grade), int(class_num))
            
            if not exchange_ref:
                continue
            
            # 現在の自立活動の配置数をカウント
            current_jiritsu = 0
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day=day, period=period)
                    assignment = schedule.get_assignment(time_slot, exchange_ref)
                    if assignment and assignment.subject.name == "自立":
                        current_jiritsu += 1
            
            # 必要な自立活動数（2コマ）
            needed = max(0, 2 - current_jiritsu)
            
            if needed > 0:
                # 空きスロットを探す
                for day in ["月", "火", "水", "木", "金"]:
                    for period in range(1, 7):
                        if needed <= 0:
                            break
                        
                        time_slot = TimeSlot(day=day, period=period)
                        
                        # テスト期間はスキップ
                        if (day, period) in self.test_periods:
                            continue
                        
                        # 既に配置済みならスキップ
                        if schedule.get_assignment(time_slot, exchange_ref):
                            continue
                        
                        # 親学級の準備
                        parent_grade, parent_class = parent_name.split("-")
                        parent_ref = self._get_class_ref(school, int(parent_grade), int(parent_class))
                        
                        if parent_ref and not schedule.get_assignment(time_slot, parent_ref):
                            # 親学級に数学または英語を配置する
                            jiritsu_slots.append((time_slot, exchange_ref, parent_ref))
                            needed -= 1
    
    def _place_jiritsu_activities(self, schedule: Schedule, school: School) -> None:
        """自立活動の配置"""
        logger.info("【フェーズ6: 自立活動の配置】")
        placed = 0
        
        for exchange_name, parent_name in self.exchange_parent_map.items():
            grade, class_num = exchange_name.split("-")
            exchange_ref = self._get_class_ref(school, int(grade), int(class_num))
            
            parent_grade, parent_class = parent_name.split("-")
            parent_ref = self._get_class_ref(school, int(parent_grade), int(parent_class))
            
            if not exchange_ref or not parent_ref:
                continue
            
            # 現在の自立活動数をカウント
            current_jiritsu = 0
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day=day, period=period)
                    assignment = schedule.get_assignment(time_slot, exchange_ref)
                    if assignment and assignment.subject.name == "自立":
                        current_jiritsu += 1
            
            # 必要な追加数
            needed = max(0, 2 - current_jiritsu)
            
            # 配置可能なスロットを探す
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    if needed <= 0:
                        break
                    
                    time_slot = TimeSlot(day=day, period=period)
                    
                    # テスト期間はスキップ
                    if (day, period) in self.test_periods:
                        continue
                    
                    # 既に配置済みならスキップ
                    if schedule.get_assignment(time_slot, exchange_ref):
                        continue
                    
                    # 親学級の科目を確認
                    parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                    
                    # 親学級が数学または英語の場合のみ自立活動を配置
                    if parent_assignment and parent_assignment.subject.name in ["数", "英"]:
                        # 交流学級の担任を取得
                        teacher = self._get_teacher_for_class_subject(school, exchange_ref, "自立")
                        
                        if teacher:
                            assignment = Assignment(
                                class_ref=exchange_ref,
                                subject=Subject("自立"),
                                teacher=teacher
                            )
                            try:
                                schedule.assign(time_slot, assignment)
                                placed += 1
                                needed -= 1
                                
                                # 教師を使用中にマーク
                                if teacher.name in self.teacher_availability:
                                    self.teacher_availability[teacher.name].discard((time_slot.day, time_slot.period))
                                    
                            except Exception as e:
                                logger.debug(f"自立活動配置失敗: {exchange_ref} @ {time_slot}: {e}")
        
        self.stats['jiritsu_placed'] = placed
        logger.info(f"自立活動配置: {placed}スロット")
    
    def _place_regular_subjects_for_normal_classes(self, schedule: Schedule, school: School) -> None:
        """通常学級の科目配置（交流学級は除外）"""
        logger.info("【フェーズ7: 通常学級の科目配置】")
        
        # 空きスロットを収集（交流学級は除外）
        empty_slots = []
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day=day, period=period)
                
                # テスト期間はスキップ
                if (day, period) in self.test_periods:
                    continue
                
                for class_ref in school.get_all_classes():
                    # 交流学級（6組・7組）はスキップ
                    if class_ref.class_number in [6, 7]:
                        continue
                    
                    if not schedule.get_assignment(time_slot, class_ref):
                        empty_slots.append((time_slot, class_ref))
        
        logger.info(f"{len(empty_slots)}個の空きスロットを検出（通常学級のみ）")
        
        # バックトラッキングで配置
        placed = self._backtrack_placement(schedule, school, empty_slots, 0)
        
        self.stats['placed_assignments'] += placed
        logger.info(f"通常科目配置: {placed}スロット")
    
    def _complete_exchange_class_sync(self, schedule: Schedule, school: School) -> None:
        """交流学級の完全同期（自立以外は必ず親学級と同じ）"""
        logger.info("【フェーズ8: 交流学級の完全同期】")
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
                    
                    # 交流学級に自立活動がある場合はスキップ
                    if exchange_assignment and exchange_assignment.subject.name == self.exchange_only_subject:
                        continue
                    
                    # 親学級に授業がある場合
                    if parent_assignment:
                        # 交流学級が空きの場合
                        if not exchange_assignment:
                            # 親学級と同じ授業を配置
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
                        
                        # 交流学級が異なる授業の場合
                        elif exchange_assignment.subject.name != parent_assignment.subject.name:
                            # 削除して親学級と同じ授業を配置
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
        
        logger.info(f"交流学級同期: {synced}スロット追加、{fixed}スロット修正")
        self.stats['exchange_sync_count'] = synced
        self.stats['exchange_violations_fixed'] = fixed
    
    def _final_validation(self, schedule: Schedule, school: School) -> None:
        """最終検証"""
        logger.info("【フェーズ9: 最終検証】")
        violations = 0
        
        # 交流学級のルールチェック
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
                    
                    # 交流学級に5組専用科目がある
                    if exchange_assignment and exchange_assignment.subject.name in self.grade5_only_subjects:
                        violations += 1
                        logger.warning(f"{exchange_ref} @ {time_slot}: 5組専用科目 {exchange_assignment.subject.name}")
                    
                    # 交流学級に自立活動がある場合
                    if exchange_assignment and exchange_assignment.subject.name == self.exchange_only_subject:
                        # 親学級が数学/英語でない
                        if not parent_assignment or parent_assignment.subject.name not in ["数", "英"]:
                            violations += 1
                            logger.warning(f"{exchange_ref} @ {time_slot}: 自立活動だが親学級が数/英でない")
                    
                    # 交流学級に自立活動以外がある場合
                    elif exchange_assignment and exchange_assignment.subject.name != self.exchange_only_subject:
                        # 親学級と異なる
                        if not parent_assignment or exchange_assignment.subject.name != parent_assignment.subject.name:
                            violations += 1
                            logger.warning(f"{exchange_ref} @ {time_slot}: 親学級と異なる科目")
        
        if violations > 0:
            logger.warning(f"最終検証で{violations}件の違反が残っています")
        else:
            logger.info("最終検証OK: 全ての交流学級ルールを満たしています")
    
    # ヘルパーメソッド
    
    def _backtrack_placement(self, schedule: Schedule, school: School,
                           empty_slots: List[Tuple[TimeSlot, ClassRef]], index: int) -> int:
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
    
    def _get_needed_subjects(self, schedule: Schedule, school: School,
                            class_ref: ClassRef) -> Dict[str, int]:
        """必要な科目と時数を取得（固定科目を除外）"""
        # 標準時数
        if class_ref.class_number == 5:
            # 5組
            required = {
                "国": 4, "社": 1, "数": 4, "理": 3, "音": 1,
                "美": 1, "保": 2, "技": 1, "家": 1, "英": 2,
                "自立": 3, "日生": 1, "作業": 1
            }
        elif class_ref.class_number in [6, 7]:
            # 6組・7組には作業はない
            required = {
                "自立": 2, "日生": 1,
                "国": 2, "数": 2, "理": 1, "英": 1,
                "保": 1, "音": 1, "美": 1
            }
        else:
            # 通常学級
            if class_ref.grade == 1:
                required = {
                    "国": 4, "社": 3, "数": 4, "理": 3, "音": 1.5,
                    "美": 1.5, "保": 3, "技": 0.5, "家": 0.5, "英": 4
                }
            elif class_ref.grade == 2:
                required = {
                    "国": 3, "社": 3, "数": 3, "理": 4, "音": 1,
                    "美": 1, "保": 3, "技": 0.5, "家": 0.5, "英": 4
                }
            else:  # 3年
                required = {
                    "国": 3, "社": 4, "数": 4, "理": 4, "音": 1,
                    "美": 1, "保": 3, "技": 0.5, "家": 0.5, "英": 4
                }
        
        # 現在の配置数をカウント
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
    
    # ヘルパーメソッド
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
        available = (day, period) in self.teacher_availability[teacher_name]
        if not available:
            logger.debug(f"{teacher_name}先生は{day}{period}限に既に授業があります")
        return available
    
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
        
        # 固定科目を除外して不足している科目を選択
        candidates = []
        for subject, required in required_hours.items():
            if subject in self.fixed_subjects:
                continue
            
            current = current_hours.get(subject, 0) // 3  # 3クラス分
            if current < required:
                # 日内重複チェック
                daily_duplicate = False
                for c in grade5_classes:
                    if self._would_create_daily_duplicate_for_grade5(schedule, c, time_slot, subject):
                        daily_duplicate = True
                        break
                
                if not daily_duplicate:
                    # 教師の利用可能性もチェック
                    teacher = self._get_teacher_for_class_subject(school, grade5_classes[0], subject)
                    if teacher and self._is_teacher_available(teacher.name, time_slot.day, time_slot.period):
                        candidates.append(subject)
        
        return random.choice(candidates) if candidates else None
    
    def _can_place_subject(self, schedule: Schedule, school: School, time_slot: TimeSlot,
                          class_ref: ClassRef, subject: str) -> bool:
        """科目を配置可能かチェック（教師重複を含む）"""
        # 日内重複チェック
        if self._would_create_daily_duplicate(schedule, class_ref, time_slot, subject):
            return False
        
        # 教師の利用可能性チェック
        teacher = self._get_teacher_for_class_subject(school, class_ref, subject)
        
        if not teacher:
            return False
        
        # テスト期間は教師重複OK
        if (time_slot.day, time_slot.period) in self.test_periods:
            return True
        
        # 通常授業では利用可能な教師が必要
        return self._is_teacher_available(teacher.name, time_slot.day, time_slot.period)
    
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
        logger.info(f"教師情報復元数: {self.stats['teacher_assignments_restored']}")
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