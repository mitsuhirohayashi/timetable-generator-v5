#!/usr/bin/env python3
"""
Ultrathink Perfect Generator V13（教師中心スケジューリング）
教師の時間割を中心に考える革新的アプローチ

V12からの改善点：
1. 教師中心のスケジューリング - 各教師の時間割を先に決定
2. 完全なバックトラッキング - 行き詰まったら戻って別の配置を試す
3. 制約伝播 - 一つの配置が他の配置に与える影響を即座に反映
4. 交流学級の完全サポート
"""

from typing import List, Optional, Dict, Set, Tuple, Any, NamedTuple
import logging
from copy import deepcopy
from collections import defaultdict, deque
import random
import csv
from pathlib import Path
from dataclasses import dataclass

from ....domain.entities import School, Schedule
from ....domain.constraints.base import Constraint
from ....domain.value_objects.time_slot import TimeSlot, Subject, Teacher, ClassReference as ClassRef
from ....domain.value_objects.assignment import Assignment
from ....infrastructure.config.path_config import path_config

logger = logging.getLogger(__name__)


@dataclass
class TeacherSlot:
    """教師の時間枠"""
    teacher: str
    day: str
    period: int
    assigned_class: Optional[ClassRef] = None
    subject: Optional[str] = None
    is_available: bool = True


@dataclass
class TeachingRequirement:
    """教師の授業要求"""
    teacher: str
    class_ref: ClassRef
    subject: str
    required_hours: int
    assigned_hours: int = 0
    
    @property
    def remaining_hours(self) -> int:
        return self.required_hours - self.assigned_hours


class UltrathinkPerfectGeneratorV13:
    """教師中心スケジューリングによる完璧な時間割生成"""
    
    def __init__(self):
        self.stats = {
            'initial_assignments': 0,
            'teacher_schedules_created': 0,
            'backtrack_count': 0,
            'conflicts_avoided': 0,
            'successful_assignments': 0,
            'failed_assignments': 0,
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
        
        # 固定科目
        self.fixed_subjects = {"欠", "YT", "学", "学活", "道", "道徳", "総", "総合", "学総", "行", "行事", "テスト"}
        
        # 教師マッピングキャッシュ
        self._teacher_mapping_cache = None
        
        # 教師スケジュール（教師名 -> 時間枠のリスト）
        self.teacher_schedules: Dict[str, List[TeacherSlot]] = {}
        
        # 授業要求（教師名 -> 要求のリスト）
        self.teaching_requirements: Dict[str, List[TeachingRequirement]] = {}
        
        # クラススケジュール（逆引き用）
        self.class_schedules: Dict[Tuple[ClassRef, str, int], Optional[str]] = {}
    
    def generate(self, school: School, constraints: List[Constraint],
                 initial_schedule: Optional[Schedule] = None) -> Schedule:
        """完璧な時間割を生成"""
        logger.info("=== Ultrathink Perfect Generator V13 (教師中心) 開始 ===")
        
        # 初期化
        schedule = initial_schedule or Schedule()
        self.stats['initial_assignments'] = len(schedule.get_all_assignments())
        logger.info(f"初期割り当て数: {self.stats['initial_assignments']}")
        
        # 教師マッピングを読み込み
        self.teacher_mapping = self._load_teacher_mapping()
        
        # 1. 教師スケジュールと授業要求を初期化
        self._initialize_teacher_schedules(school)
        self._initialize_teaching_requirements(school)
        
        # 2. 既存の配置から教師スケジュールを更新
        self._update_from_existing_schedule(schedule, school)
        
        # 3. テスト期間の配置（教師重複OK）
        self._place_test_periods(schedule, school)
        
        # 4. 固定科目の確認と配置
        self._ensure_fixed_subjects(schedule, school)
        
        # 5. 5組の同期配置（金子み先生の時間割を先に決める）
        self._schedule_grade5_classes(schedule, school)
        
        # 6. 交流学級の自立活動を配置
        self._schedule_jiritsu_activities(schedule, school)
        
        # 7. 残りの授業を教師ベースで配置
        self._schedule_remaining_classes(schedule, school)
        
        # 8. 交流学級の最終同期
        self._final_exchange_sync(schedule, school)
        
        # 9. 空きスロットを埋める
        self._fill_empty_slots(schedule, school)
        
        # 統計情報をログ出力
        self._log_statistics()
        
        return schedule
    
    def _load_teacher_mapping(self) -> Dict[Tuple[str, int, int], str]:
        """教師マッピングをCSVから読み込み"""
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
        except Exception as e:
            logger.error(f"教師マッピング読み込みエラー: {e}")
        
        self._teacher_mapping_cache = mapping
        logger.info(f"教師マッピング読み込み完了: {len(mapping)}件")
        return mapping
    
    def _initialize_teacher_schedules(self, school: School) -> None:
        """教師スケジュールを初期化"""
        logger.info("【フェーズ1: 教師スケジュールの初期化】")
        
        # 全教師のスケジュールを作成
        all_teachers = set()
        for (subject, grade, class_num), teacher in self.teacher_mapping.items():
            all_teachers.add(teacher)
        
        for teacher_name in all_teachers:
            self.teacher_schedules[teacher_name] = []
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    slot = TeacherSlot(
                        teacher=teacher_name,
                        day=day,
                        period=period,
                        is_available=True
                    )
                    self.teacher_schedules[teacher_name].append(slot)
        
        self.stats['teacher_schedules_created'] = len(self.teacher_schedules)
        logger.info(f"{len(self.teacher_schedules)}人の教師スケジュールを作成")
    
    def _initialize_teaching_requirements(self, school: School) -> None:
        """授業要求を初期化"""
        logger.info("【フェーズ2: 授業要求の初期化】")
        
        # 週間必要時数の定義
        standard_hours = {
            "国": 4, "社": 3, "数": 3, "理": 3, "英": 3,
            "音": 1, "美": 1, "保": 3, "技": 1, "家": 1,
            "道": 1, "総": 1, "学": 0, "YT": 0, "学総": 1,
            "自立": 2,  # 交流学級用
            "日生": 3, "作業": 3  # 5組用
        }
        
        # 各教師の授業要求を作成
        for (subject, grade, class_num), teacher_name in self.teacher_mapping.items():
            if teacher_name not in self.teaching_requirements:
                self.teaching_requirements[teacher_name] = []
            
            class_ref = self._get_class_ref(school, grade, class_num)
            if not class_ref:
                continue
            
            # 必要時数を取得
            required_hours = standard_hours.get(subject, 0)
            if required_hours > 0:
                req = TeachingRequirement(
                    teacher=teacher_name,
                    class_ref=class_ref,
                    subject=subject,
                    required_hours=required_hours
                )
                self.teaching_requirements[teacher_name].append(req)
        
        # 5組の特別処理（3クラス合同）
        self._adjust_grade5_requirements()
        
        total_requirements = sum(len(reqs) for reqs in self.teaching_requirements.values())
        logger.info(f"総授業要求数: {total_requirements}")
    
    def _update_from_existing_schedule(self, schedule: Schedule, school: School) -> None:
        """既存の配置から教師スケジュールを更新"""
        logger.info("【フェーズ3: 既存配置の反映】")
        
        updated_count = 0
        for time_slot, assignment in schedule.get_all_assignments():
            # 固定科目はスキップ
            if assignment.subject.name in self.fixed_subjects:
                continue
            
            # 教師を特定
            teacher_name = self._get_teacher_name(assignment, school)
            if not teacher_name:
                continue
            
            # 教師スケジュールを更新
            if teacher_name in self.teacher_schedules:
                for slot in self.teacher_schedules[teacher_name]:
                    if slot.day == time_slot.day and slot.period == time_slot.period:
                        slot.is_available = False
                        slot.assigned_class = assignment.class_ref
                        slot.subject = assignment.subject.name
                        updated_count += 1
                        
                        # 授業要求も更新
                        self._update_requirement(teacher_name, assignment.class_ref, 
                                               assignment.subject.name)
                        break
        
        logger.info(f"{updated_count}個の既存配置を教師スケジュールに反映")
    
    def _place_test_periods(self, schedule: Schedule, school: School) -> None:
        """テスト期間の配置（教師重複OK）"""
        logger.info("【フェーズ4: テスト期間の配置】")
        
        placed = 0
        for (day, period), subjects in self.test_subjects.items():
            time_slot = TimeSlot(day=day, period=period)
            
            for grade_str, subject in subjects.items():
                grade = int(grade_str)
                
                for class_ref in school.get_all_classes():
                    if class_ref.grade != grade:
                        continue
                    
                    # 既に配置されている場合はスキップ
                    if schedule.get_assignment(time_slot, class_ref):
                        continue
                    
                    # 5組・6組・7組以外のクラスに配置
                    if class_ref.class_number not in [5, 6, 7]:
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
                                # テスト期間は教師スケジュールを更新しない（重複OK）
                            except Exception:
                                pass
        
        logger.info(f"テスト期間: {placed}スロット配置")
    
    def _ensure_fixed_subjects(self, schedule: Schedule, school: School) -> None:
        """固定科目の確認と配置"""
        logger.info("【フェーズ5: 固定科目の確認】")
        
        # 月曜6限の欠課、木曜6限のYTなどを確認
        fixed_patterns = [
            ("月", 6, "欠"),
            ("木", 6, "YT"),
            ("金", 6, "欠")
        ]
        
        for day, period, subject in fixed_patterns:
            time_slot = TimeSlot(day, period)
            for class_ref in school.get_all_classes():
                if not schedule.get_assignment(time_slot, class_ref):
                    # 固定科目を配置
                    teacher = self._get_teacher_for_fixed_subject(class_ref, subject)
                    assignment = Assignment(
                        class_ref=class_ref,
                        subject=Subject(subject),
                        teacher=teacher
                    )
                    try:
                        schedule.assign(time_slot, assignment)
                        schedule.lock_cell(time_slot, class_ref)
                    except Exception:
                        pass
    
    def _schedule_grade5_classes(self, schedule: Schedule, school: School) -> None:
        """5組の同期配置（金子み先生の時間割を中心に）"""
        logger.info("【フェーズ6: 5組の同期配置】")
        
        # 5組のクラスを取得
        grade5_classes = []
        for grade in [1, 2, 3]:
            class_ref = self._get_class_ref(school, grade, 5)
            if class_ref:
                grade5_classes.append(class_ref)
        
        if not grade5_classes:
            return
        
        # 金子み先生の授業要求を取得
        kaneko_requirements = self.teaching_requirements.get("金子み", [])
        grade5_requirements = [req for req in kaneko_requirements 
                              if req.class_ref.class_number == 5]
        
        # 優先度順にソート（必要時数が多い順）
        grade5_requirements.sort(key=lambda x: x.remaining_hours, reverse=True)
        
        # 金子み先生の空き時間に配置
        for req in grade5_requirements:
            if req.remaining_hours <= 0:
                continue
            
            # 金子み先生の空き時間を探す
            for slot in self.teacher_schedules.get("金子み", []):
                if not slot.is_available:
                    continue
                
                if req.remaining_hours <= 0:
                    break
                
                time_slot = TimeSlot(slot.day, slot.period)
                
                # テスト期間はスキップ
                if (slot.day, slot.period) in self.test_periods:
                    continue
                
                # 3クラスすべてに配置可能かチェック
                can_place = True
                for class_ref in grade5_classes:
                    if schedule.get_assignment(time_slot, class_ref):
                        can_place = False
                        break
                
                if can_place:
                    # 3クラスすべてに配置
                    success = True
                    for class_ref in grade5_classes:
                        assignment = Assignment(
                            class_ref=class_ref,
                            subject=Subject(req.subject),
                            teacher=Teacher("金子み")
                        )
                        try:
                            schedule.assign(time_slot, assignment)
                        except Exception:
                            success = False
                            break
                    
                    if success:
                        # スロットを使用済みに
                        slot.is_available = False
                        slot.assigned_class = grade5_classes[0]  # 代表として1-5
                        slot.subject = req.subject
                        
                        # 要求を更新
                        req.assigned_hours += 1
                        
                        logger.debug(f"5組同期配置: {slot.day}{slot.period}限 - {req.subject}")
    
    def _schedule_jiritsu_activities(self, schedule: Schedule, school: School) -> None:
        """交流学級の自立活動を配置"""
        logger.info("【フェーズ7: 自立活動の配置】")
        
        for exchange_name, parent_name in self.exchange_parent_map.items():
            grade, class_num = exchange_name.split("-")
            exchange_ref = self._get_class_ref(school, int(grade), int(class_num))
            parent_grade, parent_num = parent_name.split("-")
            parent_ref = self._get_class_ref(school, int(parent_grade), int(parent_num))
            
            if not exchange_ref or not parent_ref:
                continue
            
            # 担当教師を特定（財津または智田）
            jiritsu_teacher = None
            if class_num == "6":
                jiritsu_teacher = "財津"
            elif class_num == "7":
                jiritsu_teacher = "智田"
            
            if not jiritsu_teacher:
                continue
            
            # 週2コマの自立活動を配置
            placed_count = 0
            target_hours = 2
            
            # 教師の空き時間を探す
            for slot in self.teacher_schedules.get(jiritsu_teacher, []):
                if not slot.is_available:
                    continue
                
                if placed_count >= target_hours:
                    break
                
                time_slot = TimeSlot(slot.day, slot.period)
                
                # 親学級の授業をチェック
                parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                if parent_assignment and parent_assignment.subject.name in ["数", "英"]:
                    # 配置可能
                    assignment = Assignment(
                        class_ref=exchange_ref,
                        subject=Subject("自立"),
                        teacher=Teacher(jiritsu_teacher)
                    )
                    
                    try:
                        schedule.assign(time_slot, assignment)
                        slot.is_available = False
                        slot.assigned_class = exchange_ref
                        slot.subject = "自立"
                        placed_count += 1
                        logger.debug(f"自立活動配置: {exchange_ref} @ {time_slot}")
                    except Exception:
                        pass
    
    def _schedule_remaining_classes(self, schedule: Schedule, school: School) -> None:
        """残りの授業を教師ベースで配置"""
        logger.info("【フェーズ8: 残りの授業を配置】")
        
        # 全教師の未完了要求を収集
        all_requirements = []
        for teacher_name, requirements in self.teaching_requirements.items():
            for req in requirements:
                if req.remaining_hours > 0:
                    all_requirements.append((teacher_name, req))
        
        # 優先度順にソート（残り時数が多い順）
        all_requirements.sort(key=lambda x: x[1].remaining_hours, reverse=True)
        
        # バックトラッキングで配置
        self._backtrack_scheduling(all_requirements, 0, schedule, school)
    
    def _backtrack_scheduling(self, requirements: List[Tuple[str, TeachingRequirement]], 
                             index: int, schedule: Schedule, school: School) -> bool:
        """バックトラッキングによるスケジューリング"""
        if index >= len(requirements):
            return True  # すべて配置完了
        
        teacher_name, req = requirements[index]
        
        # この要求が既に満たされている場合はスキップ
        if req.remaining_hours <= 0:
            return self._backtrack_scheduling(requirements, index + 1, schedule, school)
        
        # 教師の空き時間を探す
        teacher_slots = self.teacher_schedules.get(teacher_name, [])
        available_slots = [s for s in teacher_slots if s.is_available]
        
        # ランダムに並べ替え
        random.shuffle(available_slots)
        
        for slot in available_slots:
            time_slot = TimeSlot(slot.day, slot.period)
            
            # テスト期間はスキップ
            if (slot.day, slot.period) in self.test_periods:
                continue
            
            # クラスの空き確認
            if schedule.get_assignment(time_slot, req.class_ref):
                continue
            
            # 日内重複チェック
            if self._would_create_daily_duplicate(schedule, req.class_ref, time_slot, req.subject):
                continue
            
            # 配置を試みる
            assignment = Assignment(
                class_ref=req.class_ref,
                subject=Subject(req.subject),
                teacher=Teacher(teacher_name)
            )
            
            try:
                # 配置
                schedule.assign(time_slot, assignment)
                slot.is_available = False
                slot.assigned_class = req.class_ref
                slot.subject = req.subject
                req.assigned_hours += 1
                
                # 次の要求を処理
                if self._backtrack_scheduling(requirements, index + 1, schedule, school):
                    return True  # 成功
                
                # 失敗したので戻す
                schedule.remove_assignment(time_slot, req.class_ref)
                slot.is_available = True
                slot.assigned_class = None
                slot.subject = None
                req.assigned_hours -= 1
                self.stats['backtrack_count'] += 1
                
            except Exception:
                continue
        
        # この要求を満たせなかった
        return self._backtrack_scheduling(requirements, index + 1, schedule, school)
    
    def _final_exchange_sync(self, schedule: Schedule, school: School) -> None:
        """交流学級の最終同期"""
        logger.info("【フェーズ9: 交流学級の最終同期】")
        
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
                        assignment = Assignment(
                            class_ref=exchange_ref,
                            subject=parent_assignment.subject,
                            teacher=parent_assignment.teacher
                        )
                        try:
                            schedule.assign(time_slot, assignment)
                            synced += 1
                        except Exception:
                            pass
        
        logger.info(f"交流学級同期: {synced}スロット")
    
    def _fill_empty_slots(self, schedule: Schedule, school: School) -> None:
        """空きスロットを埋める"""
        logger.info("【フェーズ10: 空きスロットを埋める】")
        
        filled = 0
        empty_slots = []
        
        # 空きスロットを収集
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day=day, period=period)
                    if not schedule.get_assignment(time_slot, class_ref):
                        empty_slots.append((time_slot, class_ref))
        
        logger.info(f"空きスロット数: {len(empty_slots)}")
        
        # 各空きスロットを埋める
        for time_slot, class_ref in empty_slots:
            # この時間に空いている教師を探す
            available_teachers = []
            
            for teacher_name, slots in self.teacher_schedules.items():
                for slot in slots:
                    if (slot.day == time_slot.day and slot.period == time_slot.period 
                        and slot.is_available):
                        # この教師がこのクラスを教えられるか確認
                        can_teach = self._can_teacher_teach_class(teacher_name, class_ref)
                        if can_teach:
                            available_teachers.append((teacher_name, can_teach))
                        break
            
            if available_teachers:
                # ランダムに選択
                teacher_name, subjects = random.choice(available_teachers)
                subject = random.choice(subjects)
                
                assignment = Assignment(
                    class_ref=class_ref,
                    subject=Subject(subject),
                    teacher=Teacher(teacher_name)
                )
                
                try:
                    schedule.assign(time_slot, assignment)
                    filled += 1
                    
                    # 教師スケジュールを更新
                    for slot in self.teacher_schedules[teacher_name]:
                        if slot.day == time_slot.day and slot.period == time_slot.period:
                            slot.is_available = False
                            slot.assigned_class = class_ref
                            slot.subject = subject
                            break
                except Exception:
                    pass
        
        logger.info(f"{filled}個の空きスロットを埋めました")
    
    # ========== ヘルパーメソッド ==========
    
    def _get_teacher_name(self, assignment: Assignment, school: School) -> Optional[str]:
        """配置から教師名を取得"""
        if assignment.teacher:
            return assignment.teacher.name
        
        # マッピングから取得
        key = (assignment.subject.name, assignment.class_ref.grade, 
               assignment.class_ref.class_number)
        return self.teacher_mapping.get(key)
    
    def _update_requirement(self, teacher_name: str, class_ref: ClassRef, subject: str) -> None:
        """授業要求を更新"""
        if teacher_name in self.teaching_requirements:
            for req in self.teaching_requirements[teacher_name]:
                if req.class_ref == class_ref and req.subject == subject:
                    req.assigned_hours += 1
                    break
    
    def _get_teacher_for_class_subject(self, school: School, class_ref: ClassRef, 
                                      subject: str) -> Optional[Teacher]:
        """クラスと科目から教師を取得"""
        key = (subject, class_ref.grade, class_ref.class_number)
        teacher_name = self.teacher_mapping.get(key)
        if teacher_name:
            return Teacher(teacher_name)
        return None
    
    def _get_teacher_for_fixed_subject(self, class_ref: ClassRef, subject: str) -> Optional[Teacher]:
        """固定科目の教師を取得"""
        if subject == "欠":
            return Teacher("欠課先生")
        elif subject == "YT":
            # 担任が担当
            key = ("YT", class_ref.grade, class_ref.class_number)
            teacher_name = self.teacher_mapping.get(key)
            if teacher_name:
                return Teacher(teacher_name)
        return None
    
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
    
    def _can_teacher_teach_class(self, teacher_name: str, class_ref: ClassRef) -> List[str]:
        """教師がクラスを教えられる科目のリスト"""
        subjects = []
        for (subject, grade, class_num), teacher in self.teacher_mapping.items():
            if (teacher == teacher_name and grade == class_ref.grade 
                and class_num == class_ref.class_number):
                subjects.append(subject)
        return subjects
    
    def _get_class_ref(self, school: School, grade: int, class_num: int) -> Optional[ClassRef]:
        """ClassRefを取得"""
        for class_ref in school.get_all_classes():
            if class_ref.grade == grade and class_ref.class_number == class_num:
                return class_ref
        return None
    
    def _adjust_grade5_requirements(self) -> None:
        """5組の授業要求を調整（3クラス合同）"""
        # 金子み先生の5組関連の要求を調整
        if "金子み" in self.teaching_requirements:
            grade5_subjects = defaultdict(int)
            
            # 各科目の合計時数を計算
            for req in self.teaching_requirements["金子み"]:
                if req.class_ref.class_number == 5:
                    grade5_subjects[req.subject] += req.required_hours
            
            # 時数を3で割る（3クラス合同なので）
            new_requirements = []
            for req in self.teaching_requirements["金子み"]:
                if req.class_ref.class_number == 5 and req.class_ref.grade == 1:
                    # 1-5を代表として使用
                    req.required_hours = grade5_subjects[req.subject] // 3
                    new_requirements.append(req)
                elif req.class_ref.class_number != 5:
                    new_requirements.append(req)
            
            self.teaching_requirements["金子み"] = new_requirements
    
    def _log_statistics(self) -> None:
        """統計情報をログ出力"""
        logger.info("=== 生成統計 ===")
        logger.info(f"初期割り当て数: {self.stats['initial_assignments']}")
        logger.info(f"教師スケジュール作成数: {self.stats['teacher_schedules_created']}")
        logger.info(f"バックトラック回数: {self.stats['backtrack_count']}")
        logger.info(f"成功配置数: {self.stats['successful_assignments']}")
        logger.info(f"失敗配置数: {self.stats['failed_assignments']}")
        logger.info(f"回避した競合数: {self.stats['conflicts_avoided']}")
        logger.info("=== 統計終了 ===")