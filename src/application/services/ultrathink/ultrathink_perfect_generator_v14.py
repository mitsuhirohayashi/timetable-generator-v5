#!/usr/bin/env python3
"""
Ultrathink Perfect Generator V14（改善版教師中心スケジューリング）
V13の問題を修正し、真の教師重複ゼロを目指す

V13からの改善点：
1. テスト期間でも教師重複を防止
2. バックトラッキングを全配置に適用
3. 空きスロット埋めで日内重複チェック
4. 自立活動の親学級チェック強化
"""

from typing import List, Optional, Dict, Set, Tuple, Any, NamedTuple
import logging
from copy import deepcopy
from collections import defaultdict, deque
import random
from ....shared.utils.csv_operations import CSVOperations
from pathlib import Path
from dataclasses import dataclass, field

from ....domain.entities import School, Schedule
from ....domain.constraints.base import Constraint
from ....domain.value_objects.time_slot import TimeSlot, Subject, Teacher, ClassReference as ClassRef
from ....domain.value_objects.assignment import Assignment
from ....infrastructure.di_container import get_path_configuration
from ....domain.services.synchronizers.grade5_synchronizer_refactored import RefactoredGrade5Synchronizer

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
    is_test_period: bool = False  # テスト期間フラグを追加


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


@dataclass
class AssignmentCandidate:
    """配置候補"""
    time_slot: TimeSlot
    class_ref: ClassRef
    subject: str
    teacher: str
    score: float = 0.0  # 配置の良さのスコア


class UltrathinkPerfectGeneratorV14:
    """改善版教師中心スケジューリングによる完璧な時間割生成"""
    
    def __init__(self):
        self.stats = {
            'initial_assignments': 0,
            'teacher_schedules_created': 0,
            'backtrack_count': 0,
            'conflicts_avoided': 0,
            'successful_assignments': 0,
            'failed_assignments': 0,
            'test_period_assignments': 0,
            'jiritsu_assignments': 0,
            'empty_slots_filled': 0,
            'grade5_sync_performed': 0,
        }
        
        # 5組同期サービスを初期化
        self.grade5_synchronizer = RefactoredGrade5Synchronizer()
        
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
        
        # 授業要求（教師名 -> 要求のリスト）
        self.teaching_requirements: Dict[str, List[TeachingRequirement]] = {}
        
        # 配置履歴（バックトラッキング用）
        self.assignment_history: List[Tuple[TimeSlot, ClassRef, Assignment]] = []
    
    def generate(self, school: School, constraints: List[Constraint],
                 initial_schedule: Optional[Schedule] = None) -> Schedule:
        """完璧な時間割を生成"""
        logger.info("=== Ultrathink Perfect Generator V14 (改善版教師中心) 開始 ===")
        
        # 初期化
        schedule = initial_schedule or Schedule()
        self.stats['initial_assignments'] = len(schedule.get_all_assignments())
        logger.info(f"初期割り当て数: {self.stats['initial_assignments']}")
        
        # 教師マッピングを読み込み
        self.teacher_mapping = self._load_teacher_mapping()
        
        # 1. 教師スケジュールと授業要求を初期化
        self._initialize_teacher_schedules(school, schedule)
        self._initialize_teaching_requirements(school)
        
        # 3. 教師不在情報を更新（Follow-up.csvから）
        self._update_teacher_absences(school)
        
        # 4. 固定科目の確認と配置
        self._ensure_fixed_subjects(schedule, school)
        
        # 5. 5組（特別支援学級）の合同授業同期
        self._synchronize_grade5_classes(schedule, school)
        
        # 6. すべての授業をバックトラッキングで配置
        # （テスト期間、5組、自立活動、通常授業を統一的に処理）
        self._place_all_classes_with_backtracking(schedule, school)
        
        # 7. 再度5組の同期を確認（配置後の調整）
        self._synchronize_grade5_classes(schedule, school)
        
        # 8. 交流学級の最終同期
        self._final_exchange_sync(schedule, school)
        
        # 統計情報をログ出力
        self._log_statistics()
        
        return schedule
    
    def _load_teacher_mapping(self) -> Dict[Tuple[str, int, int], str]:
        """教師マッピングをCSVから読み込み"""
        if self._teacher_mapping_cache is not None:
            return self._teacher_mapping_cache
            
        path_config = get_path_configuration()
        mapping_file = path_config.config_dir / "teacher_subject_mapping.csv"
        mapping = {}
        
        try:
            csv_ops = CSVOperations()
            rows = csv_ops.read_csv(mapping_file)
            
            # CSVOperationsがリストを返す場合、DataFrameに変換
            import pandas as pd
            if isinstance(rows, list):
                if not rows:
                    rows = pd.DataFrame()
                else:
                    # ヘッダーを考慮してDataFrameを作成
                    header = rows[0] if rows else []
                    data = rows[1:] if len(rows) > 1 else []
                    rows = pd.DataFrame(data, columns=header)

            if rows is not None and not rows.empty:
                for _, row in rows.iterrows():
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
    
    
    
    def _ensure_fixed_subjects(self, schedule: Schedule, school: School) -> None:
        """固定科目の確認と配置"""
        logger.info("【フェーズ4: 固定科目の確認】")
        
        # 月曜6限の欠課、木曜6限のYTなどを確認
        fixed_patterns = [
            ("月", 6, "欠"),
            ("木", 6, "YT"),
            ("金", 6, "欠")
        ]
        
        placed = 0
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
                        
                        # 教師が割り当てられた場合（「欠課先生」以外）、その教師をビジーとしてマーク
                        if teacher and teacher.name != "欠課先生":
                            self._mark_teacher_busy(teacher.name, time_slot, class_ref, subject)

                        # ロック前にチェック
                        if not schedule.is_locked(time_slot, class_ref):
                            schedule.lock_cell(time_slot, class_ref)
                        placed += 1
                    except Exception as e:
                        logger.debug(f"固定科目配置エラー: {time_slot} {class_ref} - {e}")
        
        logger.info(f"固定科目: {placed}スロット配置")
    
    def _place_all_classes_with_backtracking(self, schedule: Schedule, school: School) -> None:
        """すべての授業をバックトラッキングで配置"""
        logger.info("【フェーズ5: バックトラッキングによる統一配置】")
        
        # すべての配置候補を生成
        candidates = self._generate_all_candidates(school, schedule)
        
        # 優先度でソート（テスト期間、自立活動、5組、残り時数が多い順）
        candidates.sort(key=lambda c: self._get_candidate_priority(c), reverse=True)
        
        # バックトラッキングで配置
        success = self._backtrack_placement(candidates, 0, schedule, school)
        
        if not success:
            logger.warning("完全な配置ができませんでした。部分的な解を使用します。")
        
        # 空きスロットを埋める
        self._fill_remaining_empty_slots(schedule, school)
    
    def _generate_all_candidates(self, school: School, schedule: Schedule) -> List[AssignmentCandidate]:
        """すべての配置候補を生成"""
        candidates = []
        all_time_slots = [TimeSlot(day, period) for day in ["月", "火", "水", "木", "金"] for period in range(1, 7)]
        
        # 各教師の各授業要求について
        for teacher_name, requirements in self.teaching_requirements.items():
            for req in requirements:
                if req.remaining_hours <= 0:
                    continue
                
                # この授業を配置可能な時間枠を探す
                for time_slot in all_time_slots:
                    # Scheduleオブジェクトを使って教師が利用可能かチェック
                    if not schedule.is_teacher_available(time_slot, Teacher(teacher_name)):
                        continue
                    
                    # すでに配置されている場合はスキップ
                    if schedule.get_assignment(time_slot, req.class_ref):
                        continue
                    
                    # テスト期間の特別処理
                    is_test_period = (time_slot.day, time_slot.period) in self.test_periods
                    if is_test_period:
                        # テスト期間は指定された科目のみ
                        test_subject = self._get_test_subject(time_slot.day, time_slot.period, req.class_ref.grade)
                        if test_subject != req.subject:
                            continue
                    
                    # 候補を作成
                    candidate = AssignmentCandidate(
                        time_slot=time_slot,
                        class_ref=req.class_ref,
                        subject=req.subject,
                        teacher=teacher_name,
                        score=self._calculate_candidate_score(time_slot, req)
                    )
                    candidates.append(candidate)
        
        return candidates
    
    def _get_candidate_priority(self, candidate: AssignmentCandidate) -> float:
        """候補の優先度を計算"""
        priority = 0.0
        
        # テスト期間は最優先
        if (candidate.time_slot.day, candidate.time_slot.period) in self.test_periods:
            priority += 1000.0
        
        # 自立活動は高優先
        if candidate.subject == "自立":
            priority += 500.0
        
        # 5組の授業は高優先
        if candidate.class_ref.class_number == 5:
            priority += 300.0
        
        # 候補のスコアを加算
        priority += candidate.score
        
        return priority
    
    def _calculate_candidate_score(self, time_slot: TimeSlot, req: TeachingRequirement) -> float:
        """候補のスコアを計算（配置の良さ）"""
        score = 0.0
        
        # 残り時数が多いほど高スコア
        score += req.remaining_hours * 10
        
        # 主要科目は午前中が良い
        if req.subject in ["国", "数", "英", "理", "社"]:
            if time_slot.period <= 3:
                score += 5.0
        
        # 体育は2限目以降が良い
        if req.subject == "保":
            if time_slot.period >= 2:
                score += 3.0
        
        return score
    
    def _backtrack_placement(self, candidates: List[AssignmentCandidate], index: int,
                           schedule: Schedule, school: School) -> bool:
        """バックトラッキングによる配置"""
        if index >= len(candidates):
            return True  # すべて配置完了
        
        candidate = candidates[index]
        
        # この候補の教師がすでにこの時間に配置されているかチェック
        if not schedule.is_teacher_available(candidate.time_slot, Teacher(candidate.teacher)):
            return self._backtrack_placement(candidates, index + 1, schedule, school)
        
        # 日内重複チェック
        if self._would_create_daily_duplicate(schedule, candidate.class_ref, 
                                            candidate.time_slot, candidate.subject):
            return self._backtrack_placement(candidates, index + 1, schedule, school)
        
        # 交流学級の自立活動の場合、親学級をチェック
        if candidate.subject == "自立" and self._is_exchange_class(candidate.class_ref):
            if not self._check_jiritsu_condition(schedule, candidate.class_ref, candidate.time_slot):
                return self._backtrack_placement(candidates, index + 1, schedule, school)

        # Q&Aルールに違反しないかチェック
        from ....presentation.cli.qanda_integration import QandAIntegration
        qanda = QandAIntegration()
        if qanda.violates_qa_rules(candidate.teacher, candidate.time_slot, candidate.class_ref):
            logger.debug(f"Q&Aルール違反のためスキップ: {candidate.teacher} {candidate.time_slot}")
            return self._backtrack_placement(candidates, index + 1, schedule, school)

        

        # 配置を試みる
        assignment = Assignment(
            class_ref=candidate.class_ref,
            subject=Subject(candidate.subject),
            teacher=Teacher(candidate.teacher)
        )
        
        try:
            # 配置
            schedule.assign(candidate.time_slot, assignment)
            self.assignment_history.append((candidate.time_slot, candidate.class_ref, assignment))
            
            # 統計更新
            self.stats['successful_assignments'] += 1
            if (candidate.time_slot.day, candidate.time_slot.period) in self.test_periods:
                self.stats['test_period_assignments'] += 1
            if candidate.subject == "自立":
                self.stats['jiritsu_assignments'] += 1
            
            # 次の候補を処理
            if self._backtrack_placement(candidates, index + 1, schedule, school):
                return True  # 成功
            
            # 失敗したので戻す
            schedule.remove_assignment(candidate.time_slot, candidate.class_ref)
            self.assignment_history.pop()
            self.stats['backtrack_count'] += 1
            
        except Exception as e:
            logger.debug(f"配置失敗: {e}")
            self.stats['failed_assignments'] += 1
        
        # この候補をスキップして次を試す
        return self._backtrack_placement(candidates, index + 1, schedule, school)
    
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
                        # 交流学級の教師を取得
                        teacher_name = self._get_teacher_name(parent_assignment, school)
                        
                        # 教師がその時間に利用可能かチェック
                        if teacher_name and self._is_teacher_available(teacher_name, time_slot):
                            assignment = Assignment(
                                class_ref=exchange_ref,
                                subject=parent_assignment.subject,
                                teacher=Teacher(teacher_name)
                            )
                            try:
                                schedule.assign(time_slot, assignment)
                                # 教師スケジュールを更新
                                self._mark_teacher_busy(teacher_name, time_slot, exchange_ref, parent_assignment.subject.name)
                                synced += 1
                            except Exception as e:
                                logger.debug(f"交流学級同期エラー: {time_slot} {exchange_ref} - {e}")
        
        logger.info(f"交流学級同期: {synced}スロット")
    
    def _fill_remaining_empty_slots(self, schedule: Schedule, school: School) -> None:
        """残りの空きスロットを埋める"""
        logger.info("【フェーズ7: 空きスロットを埋める】")
        
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
            best_candidate = None
            best_score = -1
            
            # この時間に空いている教師を探す
            available_teachers = self._get_available_teachers_for_slot(schedule, time_slot)
            
            for teacher_name in available_teachers:
                # この教師がこのクラスを教えられるか確認
                subjects = self._can_teacher_teach_class(teacher_name, class_ref)
                if subjects:
                    # 最適な科目を選択（日内重複を避ける）
                    for subject in subjects:
                        if not self._would_create_daily_duplicate(schedule, class_ref, 
                                                                time_slot, subject):
                            score = self._calculate_fill_score(teacher_name, class_ref, 
                                                             subject, time_slot)
                            if score > best_score:
                                best_score = score
                                best_candidate = (teacher_name, subject)
            
            if best_candidate:
                teacher_name, subject = best_candidate
                assignment = Assignment(
                    class_ref=class_ref,
                    subject=Subject(subject),
                    teacher=Teacher(teacher_name)
                )
                
                try:
                    schedule.assign(time_slot, assignment)
                    filled += 1
                    self.stats['empty_slots_filled'] += 1
                    
                    # 教師スケジュールを更新
                    self._mark_teacher_busy(teacher_name, time_slot, class_ref, subject)
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
    
    def _revert_requirement(self, teacher_name: str, class_ref: ClassRef, subject: str) -> None:
        """授業要求を戻す"""
        if teacher_name in self.teaching_requirements:
            for req in self.teaching_requirements[teacher_name]:
                if req.class_ref == class_ref and req.subject == subject:
                    req.assigned_hours -= 1
                    break
    
    
    
    
    
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
    
    def _is_exchange_class(self, class_ref: ClassRef) -> bool:
        """交流学級かどうか判定"""
        return class_ref.class_number in [6, 7]
    
    def _check_jiritsu_condition(self, schedule: Schedule, exchange_ref: ClassRef, 
                               time_slot: TimeSlot) -> bool:
        """自立活動の条件をチェック（親学級が数学か英語）"""
        # 親学級を特定
        exchange_key = f"{exchange_ref.grade}-{exchange_ref.class_number}"
        parent_key = self.exchange_parent_map.get(exchange_key)
        if not parent_key:
            return False
        
        parent_grade, parent_num = parent_key.split("-")
        parent_ref = ClassRef(int(parent_grade), int(parent_num))
        
        # 親学級の授業をチェック
        parent_assignment = schedule.get_assignment(time_slot, parent_ref)
        if parent_assignment:
            return parent_assignment.subject.name in ["数", "英"]
        
        return False
    
    def _can_teacher_teach_class(self, teacher_name: str, class_ref: ClassRef) -> List[str]:
        """教師がクラスを教えられる科目のリスト"""
        subjects = []
        for (subject, grade, class_num), teacher in self.teacher_mapping.items():
            if (teacher == teacher_name and grade == class_ref.grade 
                and class_num == class_ref.class_number):
                subjects.append(subject)
        return subjects
    
    def _calculate_fill_score(self, teacher_name: str, class_ref: ClassRef, 
                            subject: str, time_slot: TimeSlot) -> float:
        """空きスロット埋めのスコアを計算"""
        score = 0.0
        
        # 授業要求の残り時数を考慮
        if teacher_name in self.teaching_requirements:
            for req in self.teaching_requirements[teacher_name]:
                if req.class_ref == class_ref and req.subject == subject:
                    score += req.remaining_hours * 10
                    break
        
        # 時間帯の適切さ
        if subject in ["国", "数", "英", "理", "社"]:
            if time_slot.period <= 3:
                score += 5.0
        
        return score
    
    def _get_class_ref(self, school: School, grade: int, class_num: int) -> Optional[ClassRef]:
        """ClassRefを取得"""
        for class_ref in school.get_all_classes():
            if class_ref.grade == grade and class_ref.class_number == class_num:
                return class_ref
        return None
    
    def _get_test_subject(self, day: str, period: int, grade: int) -> Optional[str]:
        """テスト期間の科目を取得"""
        subjects = self.test_subjects.get((day, period), {})
        return subjects.get(str(grade))
    
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
    
    
    
    def _synchronize_grade5_classes(self, schedule: Schedule, school: School) -> None:
        """５組（特別支援学級）の合同授業を同期"""
        logger.info("【フェーズ: 5組合同授業の同期】")
        
        # 配置前の同期
        sync_count = 0
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                if self.grade5_synchronizer.ensure_grade5_sync(schedule, school, time_slot):
                    sync_count += 1
        
        # 空きスロットも同期して埋める
        filled_count = self.grade5_synchronizer.fill_empty_slots_for_grade5(schedule, school)
        
        self.stats['grade5_sync_performed'] = sync_count + filled_count
        logger.info(f"5組同期: {sync_count}時限同期、{filled_count}時限埋め")
    
    def _log_statistics(self) -> None:
        """統計情報をログ出力"""
        logger.info("=== 生成統計 ===")
        logger.info(f"初期割り当て数: {self.stats['initial_assignments']}")
        logger.info(f"教師スケジュール作成数: {self.stats['teacher_schedules_created']}")
        logger.info(f"バックトラック回数: {self.stats['backtrack_count']}")
        logger.info(f"成功配置数: {self.stats['successful_assignments']}")
        logger.info(f"失敗配置数: {self.stats['failed_assignments']}")
        logger.info(f"テスト期間配置数: {self.stats['test_period_assignments']}")
        logger.info(f"自立活動配置数: {self.stats['jiritsu_assignments']}")
        logger.info(f"空きスロット埋め数: {self.stats['empty_slots_filled']}")
        logger.info(f"回避した競合数: {self.stats['conflicts_avoided']}")
        logger.info(f"5組同期実行数: {self.stats.get('grade5_sync_performed', 0)}")
        logger.info("=== 統計終了 ===")