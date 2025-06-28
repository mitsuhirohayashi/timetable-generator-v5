"""
フェーズ5: ハイブリッドアプローチV2（超最適化版）

改善点：
1. 5組の特別処理を最初に実行
2. 教師の配置可能性を事前計算
3. より賢い配置戦略
4. 制約違反の予防的回避
"""
import logging
import random
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

from ...entities.schedule import Schedule
from ...entities.school import School, Teacher, Subject
from ...value_objects.time_slot import TimeSlot, ClassReference
from ...value_objects.assignment import Assignment
from ..constraint_validator import ConstraintValidator
from ..exchange_class_synchronizer import ExchangeClassSynchronizer
from ..grade5_synchronizer_refactored import RefactoredGrade5Synchronizer
from .test_period_protector import TestPeriodProtector


@dataclass
class OptimizationResult:
    """最適化結果"""
    schedule: Schedule
    violations: int
    teacher_conflicts: int
    statistics: Dict
    improvements: List[str] = field(default_factory=list)


class HybridScheduleGeneratorV2:
    """改良版ハイブリッド時間割生成器"""
    
    def __init__(self, enable_logging: bool = True):
        self.logger = logging.getLogger(__name__)
        if not enable_logging:
            self.logger.setLevel(logging.WARNING)
        
        # 制約検証器
        self.constraint_validator = ConstraintValidator()
        
        # 同期サービス
        self.grade5_synchronizer = RefactoredGrade5Synchronizer(self.constraint_validator)
        self.exchange_synchronizer = ExchangeClassSynchronizer()
        
        # テスト期間保護サービス
        self.test_period_protector = TestPeriodProtector()
        
        # テスト期間の定義（互換性のため残す）
        self.test_periods = {
            ("月", 1), ("月", 2), ("月", 3),
            ("火", 1), ("火", 2), ("火", 3),
            ("水", 1), ("水", 2)
        }
        
        # 固定教師の定義
        self.fixed_teachers = {
            "欠", "欠課先生", "YT担当", "YT担当先生", 
            "道担当", "道担当先生", "学担当", "学担当先生", 
            "総担当", "総担当先生", "学総担当", "学総担当先生", 
            "行担当", "行担当先生", "技家担当", "技家担当先生"
        }
        
        # 5組クラス
        self.grade5_classes = {
            ClassReference(1, 5), 
            ClassReference(2, 5), 
            ClassReference(3, 5)
        }
        
        # 交流学級と親学級のマッピング
        self.exchange_class_mapping = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2)
        }
    
    def generate(
        self,
        school: School,
        initial_schedule: Optional[Schedule] = None,
        target_violations: int = 0,
        time_limit: int = 300,
        followup_data: Optional[Dict[str, List[str]]] = None
    ) -> OptimizationResult:
        """スケジュールを生成"""
        start_time = datetime.now()
        
        self.logger.info("=== ハイブリッドV2時間割生成開始 ===")
        
        # テスト期間保護の初期化
        if followup_data:
            self.test_period_protector.load_followup_data(followup_data)
            # test_periodsも更新
            self.test_periods = self.test_period_protector.test_periods.copy()
        
        # 初期スケジュールの準備
        if initial_schedule:
            schedule = self._copy_schedule(initial_schedule)
            # テスト期間の割り当てを保存
            self.test_period_protector.load_initial_schedule(initial_schedule)
        else:
            schedule = Schedule()
        
        # フェーズ1: 事前分析と準備
        self.logger.info("フェーズ1: 事前分析と準備")
        teacher_availability = self._analyze_teacher_availability(school, schedule)
        subject_requirements = self._analyze_subject_requirements(school, schedule)
        
        # フェーズ2: 5組の完全同期配置
        self.logger.info("フェーズ2: 5組の同期配置")
        self._place_grade5_synchronized(schedule, school, teacher_availability)
        
        # フェーズ3: 交流学級の自立活動配置
        self.logger.info("フェーズ3: 交流学級の自立活動配置")
        self._place_exchange_jiritsu(schedule, school, teacher_availability)
        
        # フェーズ4: 残りの科目を賢く配置
        self.logger.info("フェーズ4: 残りの科目を賢く配置")
        self._place_remaining_smart(schedule, school, teacher_availability, subject_requirements)
        
        # フェーズ5: 最適化と修正
        self.logger.info("フェーズ5: 最適化と修正")
        best_schedule = self._optimize_schedule(schedule, school, target_violations, time_limit, start_time)
        
        # フェーズ6: テスト期間保護の適用
        self.logger.info("フェーズ6: テスト期間保護の適用")
        if self.test_period_protector.test_periods:
            changes = self.test_period_protector.protect_test_periods(best_schedule, school)
            if changes > 0:
                self.logger.info(f"テスト期間保護により{changes}個の割り当てを修正しました")
        
        # 結果の評価
        violations = self._count_violations(best_schedule, school)
        teacher_conflicts = self._count_teacher_conflicts(best_schedule, school)
        
        # 統計情報の収集
        statistics = {
            'total_assignments': len(best_schedule.get_all_assignments()),
            'violations': violations,
            'teacher_conflicts': teacher_conflicts,
            'elapsed_time': (datetime.now() - start_time).total_seconds(),
            'empty_slots': self._count_empty_slots(best_schedule, school)
        }
        
        result = OptimizationResult(
            schedule=best_schedule,
            violations=violations,
            teacher_conflicts=teacher_conflicts,
            statistics=statistics
        )
        
        self._print_summary(result)
        
        return result
    
    def _analyze_teacher_availability(self, school: School, schedule: Schedule) -> Dict:
        """教師の利用可能性を分析"""
        availability = defaultdict(lambda: defaultdict(list))
        
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 各教師の利用可能性をチェック
                for teacher in school.get_all_teachers():
                    if school.is_teacher_unavailable(day, period, teacher):
                        continue
                    
                    # 既存の割り当てをチェック
                    is_available = True
                    for class_ref in school.get_all_classes():
                        assignment = schedule.get_assignment(time_slot, class_ref)
                        if assignment and assignment.teacher and assignment.teacher.name == teacher.name:
                            is_available = False
                            break
                    
                    if is_available:
                        availability[teacher.name][f"{day}_{period}"].append(time_slot)
        
        return availability
    
    def _analyze_subject_requirements(self, school: School, schedule: Schedule) -> Dict:
        """科目の必要時数を分析"""
        requirements = defaultdict(lambda: defaultdict(int))
        
        for class_ref in school.get_all_classes():
            # 標準時数を取得
            for subject, hours in school.get_all_standard_hours(class_ref).items():
                requirements[class_ref][subject.name] = int(hours)
            
            # 既存の配置を差し引く
            for time_slot, assignment in schedule.get_all_assignments():
                if assignment.class_ref == class_ref:
                    subject_name = assignment.subject.name
                    if subject_name in requirements[class_ref]:
                        requirements[class_ref][subject_name] -= 1
        
        return requirements
    
    def _place_grade5_synchronized(self, schedule: Schedule, school: School, teacher_availability: Dict):
        """5組を同期して配置"""
        # 5組共通の科目と教師のマッピング
        grade5_subjects = {
            "国": "寺田",
            "社": "蒲地", 
            "数": "梶永",
            "理": "智田",
            "音": "塚本",
            "美": "金子み",
            "保": "野口",
            "技": "林",
            "家": "金子み",
            "英": "林田",
            "道": "金子み",
            "学": "金子み",
            "総": "金子み",
            "自立": "金子み",
            "日生": "金子み",
            "作業": "金子み",
            "YT": "金子み",
            "学総": "金子み"
        }
        
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 全5組が空いているか確認
                all_empty = True
                for class_ref in self.grade5_classes:
                    if schedule.get_assignment(time_slot, class_ref):
                        all_empty = False
                        break
                
                if not all_empty:
                    continue
                
                # 配置可能な科目を探す
                for subject_name, teacher_name in grade5_subjects.items():
                    # 教師が利用可能か確認
                    if f"{day}_{period}" not in teacher_availability.get(teacher_name, {}):
                        continue
                    
                    # 全5組に必要時数が残っているか確認
                    can_place = True
                    for class_ref in self.grade5_classes:
                        # 標準時数の確認（簡易版）
                        if subject_name in ["欠", "YT", "道", "学", "総", "学総"]:
                            # 固定科目は特定の時間のみ
                            if not self._is_fixed_subject_slot(subject_name, day, period):
                                can_place = False
                                break
                    
                    if not can_place:
                        continue
                    
                    # 5組全てに配置
                    subject = Subject(subject_name)
                    teacher = Teacher(teacher_name)
                    
                    placed_all = True
                    for class_ref in self.grade5_classes:
                        assignment = Assignment(class_ref, subject, teacher)
                        try:
                            schedule.assign(time_slot, assignment)
                        except:
                            placed_all = False
                            break
                    
                    if placed_all:
                        # 教師の利用可能性を更新
                        if teacher_name in teacher_availability:
                            for ts in list(teacher_availability[teacher_name].get(f"{day}_{period}", [])):
                                teacher_availability[teacher_name][f"{day}_{period}"].remove(ts)
                        break
    
    def _place_exchange_jiritsu(self, schedule: Schedule, school: School, teacher_availability: Dict):
        """交流学級の自立活動を配置"""
        for exchange_class, parent_class in self.exchange_class_mapping.items():
            # 自立活動の教師を取得
            jiritsu_teacher = self._get_jiritsu_teacher(exchange_class)
            if not jiritsu_teacher:
                continue
            
            days = ["月", "火", "水", "木", "金"]
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    # 既に配置済みならスキップ
                    if schedule.get_assignment(time_slot, exchange_class):
                        continue
                    
                    # 親学級の科目を確認
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    if not parent_assignment or parent_assignment.subject.name not in ["数", "英"]:
                        continue
                    
                    # 教師が利用可能か確認
                    if f"{day}_{period}" not in teacher_availability.get(jiritsu_teacher, {}):
                        continue
                    
                    # 自立活動を配置
                    subject = Subject("自立")
                    teacher = Teacher(jiritsu_teacher)
                    assignment = Assignment(exchange_class, subject, teacher)
                    
                    try:
                        schedule.assign(time_slot, assignment)
                        # 教師の利用可能性を更新
                        if jiritsu_teacher in teacher_availability:
                            for ts in list(teacher_availability[jiritsu_teacher].get(f"{day}_{period}", [])):
                                teacher_availability[jiritsu_teacher][f"{day}_{period}"].remove(ts)
                    except:
                        pass
    
    def _place_remaining_smart(self, schedule: Schedule, school: School, 
                               teacher_availability: Dict, subject_requirements: Dict):
        """残りの科目を賢く配置"""
        # 優先度順に配置
        priority_subjects = ["数", "英", "国", "理", "社"]  # 主要5教科を優先
        
        for class_ref in school.get_all_classes():
            if class_ref in self.grade5_classes:
                continue  # 5組は既に処理済み
            
            # 優先科目から配置
            for subject_name in priority_subjects:
                required = subject_requirements[class_ref].get(subject_name, 0)
                if required <= 0:
                    continue
                
                # この科目の教師を取得
                subject = Subject(subject_name)
                assigned_teacher = school.get_assigned_teacher(subject, class_ref)
                if not assigned_teacher:
                    continue
                
                # 配置可能なスロットを探す
                placed_count = 0
                days = ["月", "火", "水", "木", "金"]
                for day in days:
                    if placed_count >= required:
                        break
                    
                    for period in range(1, 7):
                        if placed_count >= required:
                            break
                        
                        time_slot = TimeSlot(day, period)
                        
                        # 既に配置済みならスキップ
                        if schedule.get_assignment(time_slot, class_ref):
                            continue
                        
                        # テスト期間中はスキップ
                        if self.test_period_protector.is_test_period(time_slot):
                            continue
                        
                        # 同じ日に同じ科目があるかチェック
                        has_duplicate = False
                        for p in range(1, 7):
                            ts = TimeSlot(day, p)
                            asn = schedule.get_assignment(ts, class_ref)
                            if asn and asn.subject.name == subject_name:
                                has_duplicate = True
                                break
                        
                        if has_duplicate:
                            continue
                        
                        # 教師が利用可能か確認
                        if f"{day}_{period}" not in teacher_availability.get(assigned_teacher.name, {}):
                            continue
                        
                        # 配置を試みる
                        assignment = Assignment(class_ref, subject, assigned_teacher)
                        try:
                            schedule.assign(time_slot, assignment)
                            placed_count += 1
                            
                            # 教師の利用可能性を更新
                            if assigned_teacher.name in teacher_availability:
                                for ts in list(teacher_availability[assigned_teacher.name].get(f"{day}_{period}", [])):
                                    teacher_availability[assigned_teacher.name][f"{day}_{period}"].remove(ts)
                        except:
                            pass
    
    def _optimize_schedule(self, schedule: Schedule, school: School, 
                          target_violations: int, time_limit: int, start_time: datetime) -> Schedule:
        """スケジュールを最適化"""
        best_schedule = self._copy_schedule(schedule)
        best_violations = self._count_violations(best_schedule, school)
        
        iteration = 0
        max_iterations = 100
        
        while iteration < max_iterations:
            iteration += 1
            
            # 時間制限チェック
            if (datetime.now() - start_time).total_seconds() > time_limit:
                break
            
            # 現在の違反数
            current_violations = self._count_violations(schedule, school)
            if current_violations <= target_violations:
                return schedule
            
            # ランダムな交換を試みる
            improved = False
            for _ in range(20):  # 20回試行
                swap_result = self._try_random_swap(schedule, school)
                if swap_result:
                    new_violations = self._count_violations(schedule, school)
                    if new_violations < current_violations:
                        improved = True
                        if new_violations < best_violations:
                            best_schedule = self._copy_schedule(schedule)
                            best_violations = new_violations
                        break
            
            if not improved:
                # 改善できない場合は最良のスケジュールに戻る
                schedule = self._copy_schedule(best_schedule)
        
        return best_schedule
    
    def _try_random_swap(self, schedule: Schedule, school: School) -> bool:
        """ランダムな交換を試みる"""
        classes = [c for c in school.get_all_classes() if c not in self.grade5_classes]
        if len(classes) < 2:
            return False
        
        # ランダムに2つのスロットを選択
        class1 = random.choice(classes)
        class2 = random.choice(classes)
        
        days = ["月", "火", "水", "木", "金"]
        day1 = random.choice(days)
        day2 = random.choice(days)
        period1 = random.randint(1, 6)
        period2 = random.randint(1, 6)
        
        time_slot1 = TimeSlot(day1, period1)
        time_slot2 = TimeSlot(day2, period2)
        
        # 同じスロットなら失敗
        if class1 == class2 and time_slot1 == time_slot2:
            return False
        
        # 割り当てを取得
        assignment1 = schedule.get_assignment(time_slot1, class1)
        assignment2 = schedule.get_assignment(time_slot2, class2)
        
        # どちらかがロックされていたら失敗
        if schedule.is_locked(time_slot1, class1) or schedule.is_locked(time_slot2, class2):
            return False
        
        # 交換を試みる
        try:
            # 既存の割り当てを削除
            if assignment1:
                schedule.remove_assignment(time_slot1, class1)
            if assignment2:
                schedule.remove_assignment(time_slot2, class2)
            
            # 交換して配置
            if assignment2:
                schedule.assign(time_slot1, Assignment(class1, assignment2.subject, assignment2.teacher))
            if assignment1:
                schedule.assign(time_slot2, Assignment(class2, assignment1.subject, assignment1.teacher))
            
            return True
        except:
            # 失敗したら元に戻す
            if assignment1:
                schedule.assign(time_slot1, assignment1)
            if assignment2:
                schedule.assign(time_slot2, assignment2)
            return False
    
    def _get_jiritsu_teacher(self, exchange_class: ClassReference) -> Optional[str]:
        """交流学級の自立活動担当教師を取得"""
        # 簡易実装
        jiritsu_teachers = {
            (1, 6): "財津",
            (1, 7): "智田",
            (2, 6): "財津",
            (2, 7): "智田",
            (3, 6): "財津",
            (3, 7): "智田"
        }
        return jiritsu_teachers.get((exchange_class.grade, exchange_class.class_number))
    
    def _is_fixed_subject_slot(self, subject_name: str, day: str, period: int) -> bool:
        """固定科目の時間かどうか判定"""
        if subject_name == "欠":
            return (day == "月" and period == 6) or (day == "金" and period == 6)
        elif subject_name == "YT":
            return day == "木" and period == 6
        elif subject_name == "道":
            return day == "木" and period == 4
        elif subject_name == "総":
            return day == "金" and period == 4
        elif subject_name == "学総":
            return day == "水" and period == 5
        return False
    
    def _copy_schedule(self, original: Schedule) -> Schedule:
        """スケジュールのコピーを作成"""
        copy = Schedule()
        for time_slot, assignment in original.get_all_assignments():
            copy.assign(time_slot, assignment)
            if original.is_locked(time_slot, assignment.class_ref):
                copy.lock_cell(time_slot, assignment.class_ref)
        return copy
    
    def _count_violations(self, schedule: Schedule, school: School) -> int:
        """違反数をカウント"""
        violations = self.constraint_validator.validate_all_constraints(schedule, school)
        return len(violations)
    
    def _count_teacher_conflicts(self, schedule: Schedule, school: School) -> int:
        """教師重複をカウント"""
        conflicts = 0
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # テスト期間はスキップ
                if (day, period) in self.test_periods:
                    continue
                
                # 教師ごとにクラスを収集
                teacher_classes = defaultdict(list)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        teacher_name = assignment.teacher.name
                        
                        # 固定教師はスキップ
                        if teacher_name in self.fixed_teachers:
                            continue
                        
                        teacher_classes[teacher_name].append(class_ref)
                
                # 重複をカウント
                for teacher_name, classes in teacher_classes.items():
                    # 5組の合同授業は除外
                    grade5_count = sum(1 for c in classes if c in self.grade5_classes)
                    if grade5_count == len(classes) and grade5_count > 1:
                        continue  # 5組のみの重複は正常
                    
                    if len(classes) > 1:
                        conflicts += 1
        
        return conflicts
    
    def _count_empty_slots(self, schedule: Schedule, school: School) -> int:
        """空きスロット数をカウント"""
        empty = 0
        days = ["月", "火", "水", "木", "金"]
        
        for class_ref in school.get_all_classes():
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    if not schedule.get_assignment(time_slot, class_ref):
                        empty += 1
        
        return empty
    
    def _print_summary(self, result: OptimizationResult):
        """結果サマリーを出力"""
        self.logger.info("\n=== ハイブリッドV2生成結果 ===")
        self.logger.info(f"総割り当て数: {result.statistics['total_assignments']}")
        self.logger.info(f"制約違反数: {result.violations}")
        self.logger.info(f"教師重複数: {result.teacher_conflicts}")
        self.logger.info(f"空きスロット数: {result.statistics['empty_slots']}")
        self.logger.info(f"実行時間: {result.statistics['elapsed_time']:.1f}秒")
        
        if result.improvements:
            self.logger.info("\n改善点:")
            for improvement in result.improvements:
                self.logger.info(f"  - {improvement}")