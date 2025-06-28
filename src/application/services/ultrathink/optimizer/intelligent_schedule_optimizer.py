"""インテリジェント時間割最適化サービス

制約違反を検出し、最適な交換・移動により自動的に解決します。
"""
import logging
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict, deque
import heapq
import math
import random

from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School, Teacher, Subject
from .....domain.value_objects.time_slot import TimeSlot
from .....domain.value_objects.time_slot import ClassReference
from .....domain.value_objects.assignment import Assignment

from .data_models import Violation, SwapCandidate, SwapChain
from .violation_graph import ViolationGraph
from .detectors import (
    TeacherConflictDetector,
    DailyDuplicateDetector,
    JiritsuViolationDetector,
    GymConflictDetector
)
from .fixers import (
    TeacherConflictFixer,
    DailyDuplicateFixer,
    JiritsuConstraintFixer,
    GymConflictFixer
)
from .scoring import SlotScorer, SwapScorer
from .learning import PatternLearner


class IntelligentScheduleOptimizer:
    """インテリジェント時間割最適化サービス"""
    
    def __init__(self):
        """初期化"""
        self.logger = logging.getLogger(__name__)
        
        # 違反の重み
        self.violation_weights = {
            'teacher_conflict': 1.0,      # 最重要
            'jiritsu_constraint': 0.9,    # 自立活動制約
            'exchange_sync': 0.8,         # 交流学級同期
            'daily_duplicate': 0.7,       # 日内重複
            'gym_conflict': 0.6,          # 体育館競合
            'consecutive_periods': 0.4,   # 連続コマ
            'workload_balance': 0.3,      # 負荷バランス
        }
        
        # 最適化パラメータ
        self.max_swap_chain_length = 5
        self.max_candidates_per_violation = 50
        self.temperature = 1.0  # シミュレーテッドアニーリング用
        self.cooling_rate = 0.95
        
        # 学習データ（成功した修正パターン）
        self.successful_patterns: List[Dict] = []
        
        # 5組関連
        self.grade5_refs = {
            ClassReference(1, 5), 
            ClassReference(2, 5), 
            ClassReference(3, 5)
        }
        
        # テスト期間
        self.test_periods = {
            ("月", 1), ("月", 2), ("月", 3),
            ("火", 1), ("火", 2), ("火", 3),
            ("水", 1), ("水", 2)
        }
        
        # 検出器を初期化
        self._init_detectors()
        
        # 修正器を初期化
        self._init_fixers()
        
        # スコア計算器を初期化
        self.slot_scorer = SlotScorer()
        self.swap_scorer = SwapScorer(self.slot_scorer)
        
        # 学習器を初期化
        self.pattern_learner = PatternLearner()
    
    def _init_detectors(self):
        """検出器を初期化"""
        self.teacher_conflict_detector = TeacherConflictDetector(
            self.test_periods, self.grade5_refs, 
            self.violation_weights['teacher_conflict']
        )
        self.daily_duplicate_detector = DailyDuplicateDetector(
            self.violation_weights['daily_duplicate']
        )
        self.jiritsu_violation_detector = JiritsuViolationDetector(
            self.violation_weights['jiritsu_constraint']
        )
        self.gym_conflict_detector = GymConflictDetector(
            self.test_periods, self.grade5_refs, 
            self.violation_weights['gym_conflict']
        )
    
    def _init_fixers(self):
        """修正器を初期化"""
        self.teacher_conflict_fixer = TeacherConflictFixer(self.grade5_refs)
        self.daily_duplicate_fixer = DailyDuplicateFixer()
        self.jiritsu_constraint_fixer = JiritsuConstraintFixer()
        self.gym_conflict_fixer = GymConflictFixer(self.grade5_refs)
    
    def optimize(self, schedule: Schedule, school: School, max_iterations: int = 100) -> Dict:
        """時間割を最適化
        
        Args:
            schedule: 現在のスケジュール
            school: 学校情報
            max_iterations: 最大反復回数
            
        Returns:
            最適化結果の統計情報
        """
        self.logger.info("インテリジェント最適化を開始")
        
        stats = {
            'initial_violations': 0,
            'final_violations': 0,
            'iterations': 0,
            'successful_swaps': 0,
            'failed_attempts': 0,
            'violation_breakdown': defaultdict(int)
        }
        
        for iteration in range(max_iterations):
            violations = self._detect_all_violations(schedule, school)
            stats['iterations'] = iteration + 1
            
            if iteration == 0:
                stats['initial_violations'] = len(violations)
                for v in violations:
                    stats['violation_breakdown'][v.type] += 1
            
            if not violations:
                self.logger.info(f"全ての違反を解決しました（{iteration}回目）")
                break
            
            # 違反グラフを構築
            graph = self._build_violation_graph(violations)
            
            # 修正対象を選択
            target = self._select_target_violation(violations)
            if not target:
                break
            
            # 最適な交換連鎖を探索
            chain = self._find_optimal_swap_chain(target, schedule, school, graph)
            
            if chain and chain.total_improvement > 0:
                # 交換を実行
                self._execute_swap_chain(schedule, chain)
                stats['successful_swaps'] += len(chain.swaps)
                
                # 成功パターンを学習
                self._learn_from_success(target, chain)
            else:
                stats['failed_attempts'] += 1
                
                # 温度を下げる（シミュレーテッドアニーリング）
                self.temperature *= self.cooling_rate
        
        # 最終状態
        final_violations = self._detect_all_violations(schedule, school)
        stats['final_violations'] = len(final_violations)
        
        self._print_optimization_summary(stats)
        
        return stats
    
    def _build_violation_graph(self, violations: List[Violation]) -> ViolationGraph:
        """違反の依存関係グラフを構築"""
        graph = ViolationGraph()
        
        # 違反を追加
        vid_map = {}
        for v in violations:
            vid = graph.add_violation(v)
            vid_map[v] = vid
        
        # 依存関係を分析
        for v1 in violations:
            for v2 in violations:
                if v1 == v2:
                    continue
                
                # 同じ教師の違反は依存関係あり
                if v1.teacher and v1.teacher == v2.teacher:
                    graph.add_dependency(vid_map[v1], vid_map[v2])
                
                # 同じクラスの違反も依存関係あり
                common_classes = set(v1.class_refs) & set(v2.class_refs)
                if common_classes:
                    graph.add_dependency(vid_map[v1], vid_map[v2])
        
        return graph
    
    def _detect_all_violations(self, schedule: Schedule, school: School) -> List[Violation]:
        """全ての違反を検出"""
        violations = []
        
        # 各種違反を検出
        violations.extend(self.teacher_conflict_detector.detect(schedule, school))
        violations.extend(self.daily_duplicate_detector.detect(schedule, school))
        violations.extend(self.jiritsu_violation_detector.detect(schedule, school))
        violations.extend(self.gym_conflict_detector.detect(schedule, school))
        
        return violations
    
    def _select_target_violation(self, violations: List[Violation]) -> Optional[Violation]:
        """修正対象の違反を選択"""
        if not violations:
            return None
        
        # 深刻度と学習パターンから優先度を計算
        priorities = []
        for v in violations:
            priority = v.severity
            
            # 過去に成功した修正パターンがあれば優先度を上げる
            for pattern in self.successful_patterns:
                if pattern['violation_type'] == v.type:
                    priority *= 1.2
            
            priorities.append((priority, v))
        
        # 最高優先度の違反を選択
        priorities.sort(reverse=True, key=lambda x: x[0])
        return priorities[0][1]
    
    def _find_optimal_swap_chain(
        self,
        violation: Violation,
        schedule: Schedule,
        school: School,
        graph: ViolationGraph
    ) -> Optional[SwapChain]:
        """最適な交換連鎖を探索"""
        # 学習済みパターンから推奨を取得
        recommendations = self.pattern_learner.get_recommended_fixes(
            violation, max_recommendations=3
        )
        
        # 推奨パターンがあれば優先的に試す
        if recommendations:
            # TODO: 推奨パターンを実際の交換に変換
            pass
        
        # 違反タイプに応じた修正器を選択
        fixer = self._get_fixer_for_violation(violation)
        if not fixer:
            return None
        
        # 修正を試みる
        chain = fixer.fix(
            violation, schedule, school, 
            self.max_candidates_per_violation
        )
        
        return chain
    
    def _get_fixer_for_violation(self, violation: Violation):
        """違反タイプに応じた修正器を取得"""
        fixer_map = {
            'teacher_conflict': self.teacher_conflict_fixer,
            'daily_duplicate': self.daily_duplicate_fixer,
            'jiritsu_constraint': self.jiritsu_constraint_fixer,
            'gym_conflict': self.gym_conflict_fixer
        }
        return fixer_map.get(violation.type)
    
    def _execute_swap_chain(self, schedule: Schedule, chain: SwapChain):
        """交換連鎖を実行"""
        for swap in chain.swaps:
            # 元の割り当てを取得
            source_assignment = schedule.get_assignment(
                swap.source_slot, swap.source_class
            )
            target_assignment = schedule.get_assignment(
                swap.target_slot, swap.target_class
            )
            
            # 交換を実行
            if source_assignment and target_assignment:
                # 一時的に削除
                schedule.remove_assignment(swap.source_slot, swap.source_class)
                schedule.remove_assignment(swap.target_slot, swap.target_class)
                
                # 交換して再配置
                schedule.assign(
                    swap.source_slot, swap.source_class,
                    target_assignment.subject, target_assignment.teacher
                )
                schedule.assign(
                    swap.target_slot, swap.target_class,
                    source_assignment.subject, source_assignment.teacher
                )
            elif source_assignment and not target_assignment:
                # 移動のみ
                schedule.remove_assignment(swap.source_slot, swap.source_class)
                schedule.assign(
                    swap.target_slot, swap.target_class,
                    source_assignment.subject, source_assignment.teacher
                )
    
    def _learn_from_success(self, violation: Violation, chain: SwapChain):
        """成功パターンを学習"""
        self.pattern_learner.learn_from_success(violation, chain)
        
        # 内部の成功パターンリストにも追加
        self.successful_patterns.append({
            'violation_type': violation.type,
            'chain_length': len(chain.swaps),
            'improvement': chain.total_improvement
        })
    
    def _print_optimization_summary(self, stats: Dict):
        """最適化結果のサマリーを出力"""
        self.logger.info("=" * 50)
        self.logger.info("最適化完了")
        self.logger.info(f"初期違反数: {stats['initial_violations']}")
        self.logger.info(f"最終違反数: {stats['final_violations']}")
        self.logger.info(f"反復回数: {stats['iterations']}")
        self.logger.info(f"成功した交換: {stats['successful_swaps']}")
        self.logger.info(f"失敗した試行: {stats['failed_attempts']}")
        
        if stats['violation_breakdown']:
            self.logger.info("\n違反タイプ別の内訳:")
            for vtype, count in stats['violation_breakdown'].items():
                self.logger.info(f"  {vtype}: {count}")
        
        self.logger.info("=" * 50)
    
    def get_violation_report(self, schedule: Schedule, school: School) -> str:
        """違反レポートを生成"""
        violations = self._detect_all_violations(schedule, school)
        
        if not violations:
            return "制約違反はありません。"
        
        report = [f"検出された違反: {len(violations)}件\n"]
        
        # タイプ別に整理
        by_type = defaultdict(list)
        for v in violations:
            by_type[v.type].append(v)
        
        for vtype, vlist in by_type.items():
            report.append(f"\n{vtype} ({len(vlist)}件):")
            for v in vlist[:5]:  # 最初の5件のみ表示
                report.append(f"  - {v.description}")
            if len(vlist) > 5:
                report.append(f"  ... 他 {len(vlist) - 5} 件")
        
        return "\n".join(report)