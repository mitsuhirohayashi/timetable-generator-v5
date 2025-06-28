"""
柔軟な標準時数保証システム

祝日・修学旅行・テスト期間などで完全な時数が満たせない場合でも、
標準時数の比率を維持しながら最適な時間割を生成するシステム。
"""
import logging
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from collections import defaultdict
import heapq
import re
from math import floor, ceil

from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School, Teacher, Subject
from ....domain.value_objects.time_slot import TimeSlot, ClassReference
from ....domain.value_objects.assignment import Assignment


@dataclass
class SpecialDay:
    """特別な日（祝日、修学旅行、テスト等）の情報"""
    day: str  # 曜日
    periods: List[int]  # 影響を受ける時限
    reason: str  # 理由（振休、外勤、テストなど）
    affected_teachers: List[str] = field(default_factory=list)  # 影響を受ける教師
    affected_classes: List[ClassReference] = field(default_factory=list)  # 影響を受けるクラス


@dataclass
class FlexibleSubjectRequirement:
    """柔軟な科目必要時数情報"""
    subject: Subject
    standard_hours: float  # 標準時数（週あたり）
    minimum_hours: float  # 最低限必要な時数
    ideal_hours: float  # 理想的な時数
    assigned_hours: int = 0  # 実際に配置された時数
    priority: float = 0.0  # 配置優先度
    ratio: float = 0.0  # 全体に対する比率
    
    @property
    def completion_rate(self) -> float:
        """標準時数に対する完了率"""
        if self.standard_hours == 0:
            return 1.0
        return self.assigned_hours / self.standard_hours
    
    @property
    def satisfaction_level(self) -> str:
        """満足度レベル"""
        if self.assigned_hours >= self.ideal_hours:
            return "理想的"
        elif self.assigned_hours >= self.standard_hours:
            return "標準"
        elif self.assigned_hours >= self.minimum_hours:
            return "最低限"
        else:
            return "不足"


@dataclass
class FlexibleClassPlan:
    """クラスごとの柔軟な配置計画"""
    class_ref: ClassReference
    requirements: Dict[str, FlexibleSubjectRequirement] = field(default_factory=dict)
    available_slots: List[TimeSlot] = field(default_factory=list)
    total_available_slots: int = 0
    special_days: List[SpecialDay] = field(default_factory=list)
    
    @property
    def total_standard_hours(self) -> float:
        """標準時数の合計"""
        return sum(req.standard_hours for req in self.requirements.values())
    
    @property
    def total_assigned_hours(self) -> int:
        """配置済み時数の合計"""
        return sum(req.assigned_hours for req in self.requirements.values())
    
    def calculate_proportional_hours(self):
        """利用可能スロット数に基づいて比例配分"""
        if self.total_standard_hours == 0:
            return
        
        # 各科目の比率を計算
        for req in self.requirements.values():
            req.ratio = req.standard_hours / self.total_standard_hours
        
        # 利用可能スロット数に基づいて理想時数を計算
        for req in self.requirements.values():
            # 理想的な時数（端数を含む）
            ideal_float = self.total_available_slots * req.ratio
            
            # 最低限の時数（切り捨て）
            req.minimum_hours = floor(ideal_float * 0.8)  # 80%を最低ライン
            
            # 理想的な時数（四捨五入）
            req.ideal_hours = round(ideal_float)


@dataclass
class PlacementResult:
    """配置結果の詳細情報"""
    class_ref: ClassReference
    subject_allocations: Dict[str, Dict[str, Any]]  # 科目別の配分情報
    total_slots: int
    used_slots: int
    satisfaction_rate: float
    warnings: List[str] = field(default_factory=list)


class FlexibleStandardHoursGuaranteeSystem:
    """柔軟な標準時数保証システム"""
    
    def __init__(self, enable_logging: bool = True):
        self.logger = logging.getLogger(__name__)
        if not enable_logging:
            self.logger.setLevel(logging.WARNING)
        
        # 固定科目の定義
        self.fixed_subjects = {"欠", "YT", "道", "学", "総", "学総", "行", "技家"}
        
        # 主要5教科の定義
        self.core_subjects = {"国", "数", "英", "理", "社"}
        
        # 優先度の重み
        self.priority_weights = {
            'core_subject': 1.5,      # 主要5教科の重み
            'standard_ratio': 1.0,    # 標準比率の重み
            'deficit': 2.0,           # 不足度の重み
            'balance': 0.5            # バランスの重み
        }
    
    def guarantee_flexible_hours(
        self,
        schedule: Schedule,
        school: School,
        followup_data: Optional[Dict[str, Any]] = None,
        constraint_validator: Any = None
    ) -> Dict[str, Any]:
        """柔軟な標準時数保証を実行"""
        
        self.logger.info("=== 柔軟な標準時数保証システム開始 ===")
        
        # 1. Follow-upデータから特別な日を分析
        special_days = self._analyze_special_days(followup_data) if followup_data else []
        
        # 2. クラスごとの配置計画を作成
        plans = self._create_flexible_plans(schedule, school, special_days)
        
        # 3. 比例配分を計算
        self._calculate_proportional_allocation(plans)
        
        # 4. 優先度を計算
        self._calculate_flexible_priorities(plans)
        
        # 5. 配置を実行
        results = self._execute_flexible_placement(plans, schedule, school, constraint_validator)
        
        # 6. 結果を評価・可視化
        final_results = self._evaluate_and_visualize(results, plans)
        
        return final_results
    
    def _analyze_special_days(self, followup_data: Dict[str, Any]) -> List[SpecialDay]:
        """Follow-upデータから特別な日を分析"""
        special_days = []
        
        day_mapping = {
            "月曜日": "月", "火曜日": "火", "水曜日": "水",
            "木曜日": "木", "金曜日": "金"
        }
        
        for day_jp, day_short in day_mapping.items():
            if day_jp in followup_data:
                day_info = followup_data[day_jp]
                
                # テスト期間の検出
                test_pattern = r'(\d+)・(\d+)・(\d+)校時はテスト'
                test_match = re.search(test_pattern, str(day_info))
                if test_match:
                    periods = [int(test_match.group(i)) for i in range(1, 4)]
                    special_days.append(SpecialDay(
                        day=day_short,
                        periods=periods,
                        reason="テスト期間"
                    ))
                
                # 教師の不在情報を検出
                absence_patterns = [
                    r'(.+?)は振休で.*不在',
                    r'(.+?)は.*外勤.*不在',
                    r'(.+?)は.*出張.*不在',
                    r'(.+?)は.*年休.*不在'
                ]
                
                for pattern in absence_patterns:
                    matches = re.findall(pattern, str(day_info))
                    for teacher_name in matches:
                        # 時限を特定
                        period_pattern = r'(\d+)・(\d+)時間目'
                        period_match = re.search(period_pattern, str(day_info))
                        if period_match:
                            periods = [int(period_match.group(1)), int(period_match.group(2))]
                        else:
                            periods = list(range(1, 7))  # 終日不在
                        
                        special_days.append(SpecialDay(
                            day=day_short,
                            periods=periods,
                            reason="教師不在",
                            affected_teachers=[teacher_name.strip()]
                        ))
        
        return special_days
    
    def _create_flexible_plans(
        self,
        schedule: Schedule,
        school: School,
        special_days: List[SpecialDay]
    ) -> Dict[ClassReference, FlexibleClassPlan]:
        """柔軟な配置計画を作成"""
        plans = {}
        
        for class_ref in school.get_all_classes():
            plan = FlexibleClassPlan(class_ref=class_ref)
            
            # 標準時数を取得
            standard_hours = school.get_all_standard_hours(class_ref)
            
            # 現在の配置状況を分析
            current_hours = self._count_current_hours(schedule, class_ref)
            
            # 柔軟な要求を作成
            for subject, hours in standard_hours.items():
                if subject.name in self.fixed_subjects:
                    continue
                
                req = FlexibleSubjectRequirement(
                    subject=subject,
                    standard_hours=float(hours),
                    minimum_hours=0,  # 後で計算
                    ideal_hours=0,    # 後で計算
                    assigned_hours=current_hours.get(subject.name, 0)
                )
                
                plan.requirements[subject.name] = req
            
            # 利用可能なスロットを計算
            plan.available_slots = self._find_flexible_available_slots(
                schedule, class_ref, special_days
            )
            plan.total_available_slots = len(plan.available_slots)
            plan.special_days = [sd for sd in special_days if self._affects_class(sd, class_ref)]
            
            plans[class_ref] = plan
        
        return plans
    
    def _count_current_hours(
        self,
        schedule: Schedule,
        class_ref: ClassReference
    ) -> Dict[str, int]:
        """現在の配置時数をカウント"""
        hours = defaultdict(int)
        
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject.name not in self.fixed_subjects:
                    hours[assignment.subject.name] += 1
        
        return dict(hours)
    
    def _find_flexible_available_slots(
        self,
        schedule: Schedule,
        class_ref: ClassReference,
        special_days: List[SpecialDay]
    ) -> List[TimeSlot]:
        """利用可能なスロットを柔軟に探す"""
        available = []
        
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 固定時間（月曜6限など）はスキップ
                if self._is_fixed_slot(day, period):
                    continue
                
                # 特別な日の影響をチェック
                if self._is_affected_by_special_day(time_slot, class_ref, special_days):
                    continue
                
                # 既に配置済みかチェック
                assignment = schedule.get_assignment(time_slot, class_ref)
                if not assignment:
                    available.append(time_slot)
                elif (assignment.subject.name not in self.fixed_subjects 
                      and not schedule.is_locked(time_slot, class_ref)):
                    # 固定科目でなく、ロックされていなければ置換可能
                    available.append(time_slot)
        
        return available
    
    def _is_fixed_slot(self, day: str, period: int) -> bool:
        """固定スロットかどうか判定"""
        # 月曜6限は全クラス欠課
        if day == "月" and period == 6:
            return True
        # その他の固定時間もここで定義
        return False
    
    def _is_affected_by_special_day(
        self,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        special_days: List[SpecialDay]
    ) -> bool:
        """特別な日の影響を受けるか判定"""
        for special_day in special_days:
            if (special_day.day == time_slot.day and 
                time_slot.period in special_day.periods):
                # テスト期間は全クラスに影響
                if special_day.reason == "テスト期間":
                    return True
                # クラス固有の影響をチェック
                if class_ref in special_day.affected_classes:
                    return True
        return False
    
    def _affects_class(self, special_day: SpecialDay, class_ref: ClassReference) -> bool:
        """特別な日がクラスに影響するか判定"""
        # テスト期間は全クラスに影響
        if special_day.reason == "テスト期間":
            return True
        # その他の条件を追加可能
        return class_ref in special_day.affected_classes
    
    def _calculate_proportional_allocation(self, plans: Dict[ClassReference, FlexibleClassPlan]):
        """比例配分を計算"""
        for plan in plans.values():
            plan.calculate_proportional_hours()
            
            # 主要5教科の最低時数を保証
            for subject_name, req in plan.requirements.items():
                if subject_name in self.core_subjects:
                    # 主要5教科は最低でも週2コマ以上
                    req.minimum_hours = max(req.minimum_hours, 2)
            
            # 端数処理の最適化
            self._optimize_rounding(plan)
    
    def _optimize_rounding(self, plan: FlexibleClassPlan):
        """端数処理を最適化"""
        # 理想時数の合計と利用可能スロット数の差を計算
        total_ideal = sum(req.ideal_hours for req in plan.requirements.values())
        diff = plan.total_available_slots - total_ideal
        
        if diff > 0:
            # スロットが余る場合、優先度の高い科目に追加
            sorted_reqs = sorted(
                plan.requirements.values(),
                key=lambda r: (r.subject.name in self.core_subjects, r.ratio),
                reverse=True
            )
            for i in range(diff):
                req = sorted_reqs[i % len(sorted_reqs)]
                req.ideal_hours += 1
        elif diff < 0:
            # スロットが不足する場合、優先度の低い科目から削減
            sorted_reqs = sorted(
                plan.requirements.values(),
                key=lambda r: (r.subject.name in self.core_subjects, r.ratio)
            )
            for i in range(-diff):
                req = sorted_reqs[i % len(sorted_reqs)]
                if req.ideal_hours > req.minimum_hours:
                    req.ideal_hours -= 1
    
    def _calculate_flexible_priorities(self, plans: Dict[ClassReference, FlexibleClassPlan]):
        """柔軟な優先度を計算"""
        for plan in plans.values():
            for req in plan.requirements.values():
                # 基本優先度：標準時数に対する比率
                base_priority = req.ratio * self.priority_weights['standard_ratio']
                
                # 主要5教科ボーナス
                if req.subject.name in self.core_subjects:
                    base_priority *= self.priority_weights['core_subject']
                
                # 不足度による優先度
                deficit = max(0, req.minimum_hours - req.assigned_hours)
                deficit_priority = deficit * self.priority_weights['deficit']
                
                # バランスを考慮
                if req.assigned_hours < req.ideal_hours * 0.5:
                    balance_priority = self.priority_weights['balance']
                else:
                    balance_priority = 0
                
                req.priority = base_priority + deficit_priority + balance_priority
    
    def _execute_flexible_placement(
        self,
        plans: Dict[ClassReference, FlexibleClassPlan],
        schedule: Schedule,
        school: School,
        constraint_validator: Any
    ) -> List[PlacementResult]:
        """柔軟な配置を実行"""
        results = []
        
        for class_ref, plan in plans.items():
            result = PlacementResult(
                class_ref=class_ref,
                subject_allocations={},
                total_slots=plan.total_available_slots,
                used_slots=0,
                satisfaction_rate=0.0
            )
            
            # 優先度順に科目を配置
            sorted_reqs = sorted(
                plan.requirements.items(),
                key=lambda x: x[1].priority,
                reverse=True
            )
            
            placed_slots = []
            
            for subject_name, req in sorted_reqs:
                teacher = school.get_assigned_teacher(req.subject, class_ref)
                if not teacher:
                    result.warnings.append(f"{subject_name}の担当教師が未設定")
                    continue
                
                # 目標時数まで配置を試みる
                target_hours = min(req.ideal_hours, len(plan.available_slots) - len(placed_slots))
                placed_count = 0
                
                for time_slot in plan.available_slots:
                    if time_slot in placed_slots:
                        continue
                    
                    if placed_count >= target_hours:
                        break
                    
                    # 配置を試みる
                    if self._try_flexible_placement(
                        time_slot, class_ref, req.subject, teacher,
                        schedule, school, constraint_validator
                    ):
                        placed_slots.append(time_slot)
                        placed_count += 1
                        req.assigned_hours += 1
                
                # 結果を記録
                result.subject_allocations[subject_name] = {
                    'standard': req.standard_hours,
                    'minimum': req.minimum_hours,
                    'ideal': req.ideal_hours,
                    'assigned': req.assigned_hours,
                    'satisfaction': req.satisfaction_level,
                    'completion_rate': req.completion_rate
                }
                
                result.used_slots += req.assigned_hours
            
            # 満足度を計算
            total_ideal = sum(req.ideal_hours for req in plan.requirements.values())
            if total_ideal > 0:
                result.satisfaction_rate = result.used_slots / total_ideal
            
            results.append(result)
        
        return results
    
    def _try_flexible_placement(
        self,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        subject: Subject,
        teacher: Teacher,
        schedule: Schedule,
        school: School,
        constraint_validator: Any
    ) -> bool:
        """柔軟な配置を試みる"""
        # 既存の配置を保存
        existing = schedule.get_assignment(time_slot, class_ref)
        
        # 新しい配置を作成
        new_assignment = Assignment(class_ref, subject, teacher)
        
        try:
            # 既存の配置を削除
            if existing:
                schedule.remove_assignment(time_slot, class_ref)
            
            # 新しい配置を追加
            schedule.assign(time_slot, new_assignment)
            
            # 基本的な制約チェック
            if self._has_basic_violations(schedule, school, time_slot, new_assignment):
                raise ValueError("Basic constraint violation")
            
            return True
            
        except Exception:
            # 失敗時は元に戻す
            try:
                schedule.remove_assignment(time_slot, class_ref)
            except:
                pass
            
            if existing:
                try:
                    schedule.assign(time_slot, existing)
                except:
                    pass
            
            return False
    
    def _has_basic_violations(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        assignment: Assignment
    ) -> bool:
        """基本的な制約違反をチェック"""
        # 教師の重複チェック（5組の合同授業を除く）
        teacher_count = 0
        for class_ref in school.get_all_classes():
            asn = schedule.get_assignment(time_slot, class_ref)
            if asn and asn.teacher and asn.teacher.name == assignment.teacher.name:
                teacher_count += 1
        
        if teacher_count > 1:
            # 5組の合同授業は例外
            grade5_classes = {ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)}
            all_grade5 = all(
                schedule.get_assignment(time_slot, cr) and 
                schedule.get_assignment(time_slot, cr).teacher.name == assignment.teacher.name
                for cr in grade5_classes
            )
            if not all_grade5:
                return True
        
        # 同じ日に同じ科目が既にあるかチェック
        for period in range(1, 7):
            if period == time_slot.period:
                continue
            ts = TimeSlot(time_slot.day, period)
            asn = schedule.get_assignment(ts, assignment.class_ref)
            if asn and asn.subject.name == assignment.subject.name:
                return True
        
        return False
    
    def _evaluate_and_visualize(
        self,
        results: List[PlacementResult],
        plans: Dict[ClassReference, FlexibleClassPlan]
    ) -> Dict[str, Any]:
        """結果を評価し可視化"""
        final_results = {
            'summary': {
                'total_classes': len(results),
                'average_satisfaction': 0.0,
                'fully_satisfied_classes': 0,
                'warnings_count': 0
            },
            'by_class': {},
            'by_subject': defaultdict(lambda: {
                'total_standard': 0,
                'total_assigned': 0,
                'average_completion': 0.0
            }),
            'special_circumstances': [],
            'visualization': self._create_visualization(results, plans)
        }
        
        total_satisfaction = 0
        
        for result in results:
            # クラスごとの結果
            class_name = str(result.class_ref)
            final_results['by_class'][class_name] = {
                'total_slots': result.total_slots,
                'used_slots': result.used_slots,
                'satisfaction_rate': result.satisfaction_rate,
                'subjects': result.subject_allocations,
                'warnings': result.warnings
            }
            
            total_satisfaction += result.satisfaction_rate
            
            if result.satisfaction_rate >= 0.95:
                final_results['summary']['fully_satisfied_classes'] += 1
            
            final_results['summary']['warnings_count'] += len(result.warnings)
            
            # 科目ごとの集計
            for subject_name, allocation in result.subject_allocations.items():
                final_results['by_subject'][subject_name]['total_standard'] += allocation['standard']
                final_results['by_subject'][subject_name]['total_assigned'] += allocation['assigned']
        
        # 平均満足度
        final_results['summary']['average_satisfaction'] = (
            total_satisfaction / len(results) if results else 0
        )
        
        # 科目ごとの平均完了率を計算
        for subject_data in final_results['by_subject'].values():
            if subject_data['total_standard'] > 0:
                subject_data['average_completion'] = (
                    subject_data['total_assigned'] / subject_data['total_standard']
                )
        
        # 特別な状況の記録
        for class_ref, plan in plans.items():
            if plan.special_days:
                final_results['special_circumstances'].append({
                    'class': str(class_ref),
                    'affected_days': len(plan.special_days),
                    'lost_slots': 30 - plan.total_available_slots  # 週30コマ想定
                })
        
        self._log_results(final_results)
        
        return final_results
    
    def _create_visualization(
        self,
        results: List[PlacementResult],
        plans: Dict[ClassReference, FlexibleClassPlan]
    ) -> Dict[str, Any]:
        """配分結果の可視化データを作成"""
        viz_data = {
            'allocation_chart': [],
            'satisfaction_heatmap': [],
            'subject_distribution': {}
        }
        
        # 配分チャート用データ
        for result in results:
            class_data = {
                'class': str(result.class_ref),
                'allocations': []
            }
            
            for subject_name, allocation in result.subject_allocations.items():
                class_data['allocations'].append({
                    'subject': subject_name,
                    'standard': allocation['standard'],
                    'assigned': allocation['assigned'],
                    'ideal': allocation['ideal']
                })
            
            viz_data['allocation_chart'].append(class_data)
        
        # 満足度ヒートマップ
        for result in results:
            for subject_name, allocation in result.subject_allocations.items():
                viz_data['satisfaction_heatmap'].append({
                    'class': str(result.class_ref),
                    'subject': subject_name,
                    'satisfaction': allocation['completion_rate']
                })
        
        # 科目別分布
        subject_totals = defaultdict(lambda: {'assigned': 0, 'standard': 0})
        for result in results:
            for subject_name, allocation in result.subject_allocations.items():
                subject_totals[subject_name]['assigned'] += allocation['assigned']
                subject_totals[subject_name]['standard'] += allocation['standard']
        
        for subject_name, totals in subject_totals.items():
            viz_data['subject_distribution'][subject_name] = {
                'percentage': (totals['assigned'] / totals['standard'] * 100 
                              if totals['standard'] > 0 else 0)
            }
        
        return viz_data
    
    def _log_results(self, results: Dict[str, Any]):
        """結果をログ出力"""
        self.logger.info("\n=== 柔軟な標準時数保証システム結果 ===")
        self.logger.info(f"平均満足度: {results['summary']['average_satisfaction']*100:.1f}%")
        self.logger.info(f"完全充足クラス: {results['summary']['fully_satisfied_classes']}/{results['summary']['total_classes']}")
        
        if results['special_circumstances']:
            self.logger.info("\n特別な状況の影響:")
            for circ in results['special_circumstances']:
                self.logger.info(f"  {circ['class']}: {circ['lost_slots']}コマ減少")
        
        self.logger.info("\n科目別達成率:")
        sorted_subjects = sorted(
            results['by_subject'].items(),
            key=lambda x: x[1]['average_completion']
        )
        for subject_name, data in sorted_subjects[:10]:
            self.logger.info(
                f"  {subject_name}: {data['average_completion']*100:.1f}% "
                f"({data['total_assigned']}/{int(data['total_standard'])})"
            )
        
        if results['summary']['warnings_count'] > 0:
            self.logger.warning(f"\n警告: {results['summary']['warnings_count']}件")


def create_flexible_system(enable_logging: bool = True) -> FlexibleStandardHoursGuaranteeSystem:
    """柔軟な標準時数保証システムのインスタンスを作成"""
    return FlexibleStandardHoursGuaranteeSystem(enable_logging=enable_logging)