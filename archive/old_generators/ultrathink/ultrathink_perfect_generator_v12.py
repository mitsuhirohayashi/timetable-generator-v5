#!/usr/bin/env python3
"""
Ultrathink Perfect Generator V12（完全版）
教師重複の完全解消と空きスロットの確実な埋め込み

V11からの改善点：
1. 教師利用可能性の管理を完全に修正
2. 空きスロットの確実な埋め込み
3. デバッグ情報の強化
4. エラーハンドリングの改善
"""

from typing import List, Optional, Dict, Set, Tuple, Any
import logging
from copy import deepcopy
from collections import defaultdict
import random
import csv
from pathlib import Path

from ....domain.entities import School, Schedule
from ....domain.constraints.base import Constraint
from ....domain.value_objects.time_slot import TimeSlot, Subject, Teacher, ClassReference as ClassRef
from ....domain.value_objects.assignment import Assignment
from ....infrastructure.config.path_config import path_config

logger = logging.getLogger(__name__)


class UltrathinkPerfectGeneratorV12:
    """最初から完璧な時間割を生成する革新的ジェネレーター（V12）"""
    
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
            'existing_teacher_assignments': 0,
            'empty_slots_filled': 0
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
        
        # 教師マッピングキャッシュ
        self._teacher_mapping_cache = None
    
    def _load_teacher_mapping(self) -> Dict[Tuple[str, int, int], str]:
        """教師マッピングをCSVから直接読み込み"""
        if self._teacher_mapping_cache is not None:
            return self._teacher_mapping_cache
            
        mapping_file = path_config.get_config_path("teacher_subject_mapping.csv")
        mapping = {}
        
        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['教員名'] and row['教科'] and row['学年'] and row['組']:
                        grade = int(row['学年'])
                        class_num = int(row['組'])
                        subject = row['教科']
                        teacher = row['教員名']
                        mapping[(subject, grade, class_num)] = teacher
                        logger.debug(f"教師マッピング読み込み: {subject} {grade}-{class_num} → {teacher}")
        except Exception as e:
            logger.error(f"教師マッピング読み込みエラー: {e}")
        
        self._teacher_mapping_cache = mapping
        logger.info(f"教師マッピング読み込み完了: {len(mapping)}件")
        return mapping
    
    def generate(self, school: School, constraints: List[Constraint],
                 initial_schedule: Optional[Schedule] = None) -> Schedule:
        """完璧な時間割を生成"""
        logger.info("=== Ultrathink Perfect Generator V12 開始 ===")
        
        # 初期化
        schedule = initial_schedule or Schedule()
        self.stats['initial_assignments'] = len(schedule.get_all_assignments())
        logger.info(f"初期割り当て数: {self.stats['initial_assignments']}")
        
        # 教師マッピングを読み込み
        self.teacher_mapping = self._load_teacher_mapping()
        
        # 教師の利用可能時間を初期化（改善版）
        self.teacher_availability = self._initialize_teacher_availability_v12(school, schedule)
        
        # 1. 交流学級の不正な配置を削除
        self._clean_exchange_classes(schedule, school)
        
        # 2. テスト期間の配置
        self._place_test_periods_only(schedule, school)
        
        # 3. 5組の同期配置
        self._place_grade5_synchronized(schedule, school)
        
        # 4. 自立活動の配置と検証
        self._place_and_validate_jiritsu(schedule, school)
        
        # 5. 残りの科目を配置
        self._place_remaining_subjects(schedule, school, constraints)
        
        # 6. 交流学級の最終同期
        self._final_exchange_sync(schedule, school)
        
        # 7. 空きスロットを埋める（新規追加）
        self._fill_empty_slots(schedule, school)
        
        # 8. 最終的な教師重複チェックと修正
        self._fix_teacher_duplicates(schedule, school)
        
        # 統計情報をログ出力
        self._log_statistics()
        
        return schedule
    
    def _initialize_teacher_availability_v12(self, school: School, schedule: Schedule) -> Dict[str, Set[Tuple[str, int]]]:
        """教師の利用可能時間を初期化（V12改善版）"""
        logger.info("=== 教師利用可能時間の初期化（V12） ===")
        
        # 全教師のbusyな時間帯を記録（busyな時間のみを記録）
        teacher_busy_slots = defaultdict(set)
        
        # 既存配置から教師情報を復元
        teacher_count = 0
        for time_slot, assignment in schedule.get_all_assignments():
            # テスト期間は教師重複OKなのでスキップ
            if (time_slot.day, time_slot.period) in self.test_periods:
                continue
            
            # 欠課はスキップ
            if assignment.subject.name == "欠":
                continue
            
            # 教師を取得（3段階のフォールバック）
            teacher_name = None
            
            # 1. assignmentに教師が設定されている場合
            if assignment.teacher:
                teacher_name = assignment.teacher.name
            
            # 2. schoolから取得
            if not teacher_name:
                teacher = school.get_assigned_teacher(assignment.subject, assignment.class_ref)
                if teacher:
                    teacher_name = teacher.name
            
            # 3. 教師マッピングから直接取得
            if not teacher_name and hasattr(assignment.class_ref, 'grade') and hasattr(assignment.class_ref, 'class_number'):
                key = (assignment.subject.name, assignment.class_ref.grade, assignment.class_ref.class_number)
                teacher_name = self.teacher_mapping.get(key)
            
            # 教師が見つかった場合はbusyにマーク
            if teacher_name:
                teacher_busy_slots[teacher_name].add((time_slot.day, time_slot.period))
                teacher_count += 1
                logger.debug(f"教師割り当て検出: {teacher_name} @ {time_slot} ({assignment.class_ref} {assignment.subject.name})")
        
        self.stats['existing_teacher_assignments'] = teacher_count
        logger.info(f"既存教師割り当て検出数: {teacher_count}")
        
        # デバッグ: 各教師の埋まっているコマ数を表示
        for teacher_name, busy_slots in sorted(teacher_busy_slots.items()):
            if len(busy_slots) > 0:
                logger.debug(f"{teacher_name}: {len(busy_slots)}コマ埋まっている")
        
        return dict(teacher_busy_slots)
    
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
    
    def _place_and_validate_jiritsu(self, schedule: Schedule, school: School) -> None:
        """自立活動の配置と検証（既存の検証と新規配置を統合）"""
        logger.info("【フェーズ4: 自立活動の配置と検証】")
        
        # まず既存の自立活動を検証
        violations_fixed = 0
        placed = 0
        
        for exchange_name, parent_name in self.exchange_parent_map.items():
            grade, class_num = exchange_name.split("-")
            exchange_ref = self._get_class_ref(school, int(grade), int(class_num))
            parent_grade, parent_num = parent_name.split("-")
            parent_ref = self._get_class_ref(school, int(parent_grade), int(parent_num))
            
            if not exchange_ref or not parent_ref:
                continue
            
            # 既存の自立活動を検証
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
        
        logger.info(f"自立活動違反を{violations_fixed}件修正、新規{placed}スロット配置")
    
    def _place_remaining_subjects(self, schedule: Schedule, school: School, constraints: List[Constraint]) -> None:
        """残りの科目を配置（通常授業）"""
        logger.info("【フェーズ5: 残りの科目を配置】")
        
        # 配置対象のクラスと時間枠を収集
        empty_slots = []
        for class_ref in school.get_all_classes():
            # 5組・6組・7組は特別処理
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
    
    def _final_exchange_sync(self, schedule: Schedule, school: School) -> None:
        """交流学級の最終同期"""
        logger.info("【フェーズ6: 交流学級の最終同期】")
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
    
    def _fill_empty_slots(self, schedule: Schedule, school: School) -> None:
        """空きスロットを確実に埋める（V12新規追加）"""
        logger.info("【フェーズ7: 空きスロットを埋める】")
        filled = 0
        
        # 全クラスの空きスロットを収集
        empty_slots = []
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day=day, period=period)
                    
                    if not schedule.get_assignment(time_slot, class_ref):
                        empty_slots.append((time_slot, class_ref))
        
        logger.info(f"空きスロット数: {len(empty_slots)}")
        
        # 各空きスロットを埋める
        for time_slot, class_ref in empty_slots:
            # 必要な科目を取得
            needed_subjects = self._get_needed_subjects(schedule, school, class_ref)
            
            # 優先度順にソート（必要時数が多い順）
            sorted_subjects = sorted(needed_subjects.items(), key=lambda x: x[1], reverse=True)
            
            # 配置を試みる
            placed = False
            for subject, needed_hours in sorted_subjects:
                if needed_hours <= 0:
                    continue
                
                # 日内重複チェック
                if self._would_create_daily_duplicate(schedule, class_ref, time_slot, subject):
                    continue
                
                # 教師を取得
                teacher = self._get_teacher_for_class_subject(school, class_ref, subject)
                if not teacher:
                    logger.debug(f"{class_ref}の{subject}の教師が見つかりません")
                    continue
                
                # 教師の利用可能性チェック
                if not self._is_teacher_available(teacher.name, time_slot.day, time_slot.period):
                    logger.debug(f"{teacher.name}先生は{time_slot}に利用不可")
                    continue
                
                # 配置
                assignment = Assignment(
                    class_ref=class_ref,
                    subject=Subject(subject),
                    teacher=teacher
                )
                
                try:
                    schedule.assign(time_slot, assignment)
                    self._mark_teacher_busy(teacher.name, time_slot.day, time_slot.period)
                    filled += 1
                    placed = True
                    logger.debug(f"{class_ref} @ {time_slot}: {subject}({teacher.name})を配置")
                    break
                except Exception as e:
                    logger.debug(f"配置失敗: {e}")
                    continue
            
            if not placed:
                logger.warning(f"空きスロットを埋められません: {class_ref} @ {time_slot}")
        
        self.stats['empty_slots_filled'] = filled
        logger.info(f"空きスロットを{filled}個埋めました")
    
    def _fix_teacher_duplicates(self, schedule: Schedule, school: School) -> None:
        """最終的な教師重複のチェックと修正（V12新規追加）"""
        logger.info("【フェーズ8: 教師重複の最終チェック】")
        
        # 各時間帯の教師配置をチェック
        duplicates_fixed = 0
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day=day, period=period)
                
                # テスト期間はスキップ
                if (day, period) in self.test_periods:
                    continue
                
                # この時間の教師配置を収集
                teacher_assignments = defaultdict(list)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        teacher_assignments[assignment.teacher.name].append(class_ref)
                
                # 重複をチェック
                for teacher_name, classes in teacher_assignments.items():
                    if len(classes) > 1:
                        # 特殊な教師は除外（欠課、YT担当、学総担当など）
                        if teacher_name in ["欠課先生", "YT担当先生", "学総担当先生", "道徳担当先生", "総合担当先生"]:
                            continue
                        
                        # 5組の合同授業は除外
                        grade5_count = sum(1 for c in classes if c.class_number == 5)
                        if grade5_count == len(classes) and grade5_count > 0:
                            continue
                        
                        logger.warning(f"{time_slot}: {teacher_name}先生が重複 - {[str(c) for c in classes]}")
                        
                        # 2番目以降のクラスを削除（空きスロットにする）
                        for i, class_ref in enumerate(classes):
                            if i > 0:  # 最初のクラス以外
                                # ロックされていない場合のみ削除
                                if not schedule.is_locked(time_slot, class_ref):
                                    schedule.remove_assignment(time_slot, class_ref)
                                    duplicates_fixed += 1
                                    logger.info(f"  {class_ref}の配置を削除")
                                else:
                                    logger.info(f"  {class_ref}はロックされているため削除できません")
        
        if duplicates_fixed > 0:
            logger.info(f"{duplicates_fixed}個の教師重複を修正（空きスロット化）")
            # 空きスロットを再度埋める
            self._fill_empty_slots(schedule, school)
    
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
            
            # このクラス・科目の正しい教師を取得（改善版）
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
        """クラスと科目の組み合わせから正しい教師を取得（V12改善版）"""
        subject_obj = Subject(subject)
        
        # 1. schoolから割り当てられた教師を取得
        teacher = school.get_assigned_teacher(subject_obj, class_ref)
        
        if teacher:
            logger.debug(f"{class_ref} {subject} → {teacher.name}先生 (schoolから)")
            return teacher
        
        # 2. 教師マッピングから直接取得
        if hasattr(class_ref, 'grade') and hasattr(class_ref, 'class_number'):
            key = (subject, class_ref.grade, class_ref.class_number)
            teacher_name = self.teacher_mapping.get(key)
            if teacher_name:
                logger.debug(f"{class_ref} {subject} → {teacher_name}先生 (マッピングから)")
                return Teacher(teacher_name)
        
        logger.warning(f"{class_ref} {subject}の担当教師が見つかりません")
        return None
    
    def _is_teacher_available(self, teacher_name: str, day: str, period: int) -> bool:
        """教師が利用可能かチェック"""
        if teacher_name not in self.teacher_availability:
            # このデータ構造では、記録がない＝利用可能
            return True
        
        # busyな時間帯に含まれていなければ利用可能
        available = (day, period) not in self.teacher_availability[teacher_name]
        
        if not available:
            logger.debug(f"{teacher_name}先生は{day}{period}限に利用不可")
        
        return available
    
    def _mark_teacher_busy(self, teacher_name: str, day: str, period: int) -> None:
        """教師を利用不可にマーク"""
        if teacher_name not in self.teacher_availability:
            self.teacher_availability[teacher_name] = set()
        self.teacher_availability[teacher_name].add((day, period))
    
    def _mark_teacher_available(self, teacher_name: str, day: str, period: int) -> None:
        """教師を利用可能にマーク"""
        if teacher_name in self.teacher_availability:
            self.teacher_availability[teacher_name].discard((day, period))
    
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
                "自立": 2,
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
    
    def _log_statistics(self) -> None:
        """統計情報をログ出力"""
        logger.info("=== 生成統計 ===")
        logger.info(f"初期割り当て数: {self.stats['initial_assignments']}")
        logger.info(f"既存教師割り当て検出数: {self.stats['existing_teacher_assignments']}")
        logger.info(f"新規配置数: {self.stats['placed_assignments']}")
        logger.info(f"自立活動配置数: {self.stats['jiritsu_placed']}")
        logger.info(f"自立活動違反修正数: {self.stats['jiritsu_violations_fixed']}")
        logger.info(f"交流学級同期数: {self.stats['exchange_sync_count']}")
        logger.info(f"交流学級違反修正数: {self.stats['exchange_violations_fixed']}")
        logger.info(f"教師重複回避数: {self.stats['teacher_conflicts_avoided']}")
        logger.info(f"空きスロット埋め数: {self.stats['empty_slots_filled']}")
        logger.info(f"バックトラック回数: {self.stats['backtrack_count']}")
        logger.info(f"教師重複検出数: {self.stats['teacher_duplicates_found']}")
        logger.info("=== 統計終了 ===")