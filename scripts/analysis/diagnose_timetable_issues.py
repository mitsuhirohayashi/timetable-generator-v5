#!/usr/bin/env python3
"""時間割生成システムの問題診断ツール

現在のシステムの主要な問題を診断し、改善のための詳細情報を提供します。
"""
import os
import sys
import logging
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Set

# プロジェクトルートをPythonパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowupParser
from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from src.domain.utils.schedule_utils import ScheduleUtils


class TimetableDiagnosticTool:
    """時間割診断ツール"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.repository = CSVScheduleRepository()
        self.absence_loader = TeacherAbsenceLoader(os.path.join(project_root, "data/input/Follow-up.csv"))
        self.followup_parser = EnhancedFollowupParser()
        
        # 5組クラスのリスト
        self.grade5_classes = set()
        for class_str in ScheduleUtils.get_grade5_classes():
            if "年" in class_str and "組" in class_str:
                grade = int(class_str[0])
                class_num = int(class_str[2])
                self.grade5_classes.add(ClassReference(grade, class_num))
    
    def run_diagnostics(self):
        """診断を実行"""
        print("\n" + "="*60)
        print("時間割生成システム診断レポート")
        print("="*60)
        
        # データ読み込み
        school = self.repository.load_school_data()
        schedule = self.repository.load_schedule("output.csv")
        
        # 1. 5組同期問題の診断
        print("\n### 1. 5組同期問題の診断 ###")
        self.diagnose_grade5_sync(schedule, school)
        
        # 2. 教師重複問題の診断
        print("\n### 2. 教師重複問題の診断 ###")
        self.diagnose_teacher_conflicts(schedule, school)
        
        # 3. 制約間の競合分析
        print("\n### 3. 制約間の競合分析 ###")
        self.analyze_constraint_conflicts(schedule, school)
        
        # 4. 生成プロセスの問題点
        print("\n### 4. 生成プロセスの問題点 ###")
        self.analyze_generation_process()
        
        # 5. 改善提案
        print("\n### 5. 改善提案 ###")
        self.suggest_improvements()
    
    def diagnose_grade5_sync(self, schedule: Schedule, school: School):
        """5組同期問題の詳細診断"""
        violations = []
        sync_opportunities = []
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 5組の配置を取得
                grade5_assignments = {}
                for class_ref in self.grade5_classes:
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        grade5_assignments[class_ref] = assignment.subject.name
                    else:
                        grade5_assignments[class_ref] = "空き"
                
                # 同期チェック
                subjects = list(grade5_assignments.values())
                if len(set(subjects)) > 1:
                    violations.append({
                        'time_slot': time_slot,
                        'assignments': grade5_assignments,
                        'unique_subjects': len(set(subjects))
                    })
                    
                    # 同期可能性の分析
                    subject_counts = Counter(subjects)
                    most_common = subject_counts.most_common(1)[0]
                    if most_common[1] >= 2:
                        sync_opportunities.append({
                            'time_slot': time_slot,
                            'dominant_subject': most_common[0],
                            'count': most_common[1],
                            'total': len(self.grade5_classes)
                        })
        
        print(f"5組同期違反: {len(violations)}件")
        print(f"同期可能な時間枠: {len(sync_opportunities)}件")
        
        # 詳細分析
        if violations:
            print("\n違反の詳細（上位5件）:")
            for v in violations[:5]:
                print(f"  {v['time_slot']}: {v['assignments']}")
        
        if sync_opportunities:
            print("\n同期改善の機会:")
            for opp in sync_opportunities[:5]:
                print(f"  {opp['time_slot']}: {opp['dominant_subject']}で{opp['count']}/{opp['total']}クラス一致")
        
        # 根本原因の分析
        print("\n根本原因の分析:")
        print("- 5組同期処理のタイミングが遅い（個別配置後に同期を試みている）")
        print("- 教師制約との競合（同じ教師が複数の5組クラスを担当できない場合）")
        print("- 標準時数制約との競合（各クラスで必要な時数が異なる場合）")
    
    def diagnose_teacher_conflicts(self, schedule: Schedule, school: School):
        """教師重複問題の詳細診断"""
        conflicts = []
        teacher_load = defaultdict(lambda: defaultdict(int))
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 教師ごとにクラスを収集
                teacher_classes = defaultdict(list)
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        teacher_classes[assignment.teacher.name].append(class_ref)
                        teacher_load[assignment.teacher.name][time_slot] += 1
                
                # 重複チェック
                for teacher, classes in teacher_classes.items():
                    if len(classes) > 1:
                        # 5組の合同授業かチェック
                        grade5_count = sum(1 for c in classes if c in self.grade5_classes)
                        if grade5_count < len(classes):
                            conflicts.append({
                                'time_slot': time_slot,
                                'teacher': teacher,
                                'classes': classes,
                                'is_mixed': grade5_count > 0 and grade5_count < len(classes)
                            })
        
        print(f"教師重複違反: {len(conflicts)}件")
        
        # 重複パターンの分析
        mixed_conflicts = [c for c in conflicts if c['is_mixed']]
        pure_conflicts = [c for c in conflicts if not c['is_mixed']]
        
        print(f"- 5組と通常クラスの混在: {len(mixed_conflicts)}件")
        print(f"- 通常クラスのみの重複: {len(pure_conflicts)}件")
        
        # 最も負荷の高い教師
        print("\n負荷の高い教師（上位5名）:")
        teacher_total_load = {t: sum(v for v in slots.values()) for t, slots in teacher_load.items()}
        for teacher, load in sorted(teacher_total_load.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {teacher}: 週{load}コマ")
            # 重複時間帯
            conflict_slots = [c['time_slot'] for c in conflicts if c['teacher'] == teacher]
            if conflict_slots:
                print(f"    重複時間帯: {', '.join(str(s) for s in conflict_slots[:3])}")
    
    def analyze_constraint_conflicts(self, schedule: Schedule, school: School):
        """制約間の競合を分析"""
        print("\n制約競合のパターン:")
        
        # 1. 5組同期 vs 教師可用性
        print("\n1. 5組同期 vs 教師可用性:")
        grade5_teacher_conflicts = 0
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 5組で異なる教科を持つ場合
                subjects = set()
                teachers = set()
                for class_ref in self.grade5_classes:
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        subjects.add(assignment.subject.name)
                        if assignment.teacher:
                            teachers.add(assignment.teacher.name)
                
                if len(subjects) > 1 and len(teachers) == len(subjects):
                    grade5_teacher_conflicts += 1
        
        print(f"  5組で異なる教科かつ異なる教師: {grade5_teacher_conflicts}件")
        print("  → 教師制約により5組同期が困難になっている可能性")
        
        # 2. 固定科目 vs 標準時数
        print("\n2. 固定科目 vs 標準時数:")
        fixed_subject_slots = 0
        total_slots = 0
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    total_slots += 1
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and ScheduleUtils.is_fixed_subject(assignment.subject.name):
                        fixed_subject_slots += 1
        
        fixed_ratio = fixed_subject_slots / total_slots * 100
        print(f"  固定科目の占有率: {fixed_ratio:.1f}%")
        if fixed_ratio > 30:
            print("  → 固定科目が多すぎて、通常教科の配置が困難")
        
        # 3. 日内重複制約 vs 標準時数
        print("\n3. 日内重複制約 vs 標準時数:")
        high_frequency_subjects = ["国", "数", "英", "算"]
        for subject in high_frequency_subjects:
            required_total = 0
            max_possible = 0
            for class_ref in school.get_all_classes():
                try:
                    subject_obj = next(s for s in school.subjects if s.name == subject)
                    required = school.get_standard_hours(class_ref, subject_obj)
                    required_total += required
                    max_possible += 5  # 週5日、1日1コマまで
                except:
                    pass
            
            if required_total > 0:
                ratio = required_total / max_possible * 100
                print(f"  {subject}: 必要{required_total}コマ / 最大{max_possible}コマ ({ratio:.1f}%)")
    
    def analyze_generation_process(self):
        """生成プロセスの問題点を分析"""
        print("\n生成プロセスの問題点:")
        
        print("\n1. 処理順序の問題:")
        print("  - 個別クラスの配置 → 5組同期 → 制約違反発生")
        print("  - 改善案: 5組を先に一括配置してから、他クラスを配置")
        
        print("\n2. バックトラックの不足:")
        print("  - 現在: 配置失敗時に代替案を探さない")
        print("  - 改善案: 制約違反時に前の配置を取り消して再試行")
        
        print("\n3. 優先度管理:")
        print("  - 現在: すべての制約を同等に扱う")
        print("  - 改善案: CRITICAL制約を最優先、段階的に緩和")
        
        print("\n4. 最適化不足:")
        print("  - 現在: 局所的な配置のみ")
        print("  - 改善案: 全体最適化アルゴリズムの導入")
    
    def suggest_improvements(self):
        """改善提案"""
        print("\n改善提案:")
        
        print("\n【優先度1: 5組同期の改善】")
        print("1. 5組専用の配置フェーズを作成")
        print("   - 他のクラスより先に5組3クラスを一括配置")
        print("   - 同一教師による合同授業を前提とした配置")
        print("2. 5組教師プールの作成")
        print("   - 5組専任教師のリストを管理")
        print("   - 教師の可用性を事前チェック")
        
        print("\n【優先度2: 制約処理の改善】")
        print("1. 制約充足アルゴリズムの強化")
        print("   - AC-3アルゴリズムによる制約伝播")
        print("   - 最小残余値ヒューリスティック")
        print("2. 段階的制約緩和")
        print("   - CRITICAL → HIGH → MEDIUM → LOW")
        print("   - 各段階での成功率を記録")
        
        print("\n【優先度3: 生成戦略の改善】")
        print("1. マルチフェーズ生成")
        print("   - Phase1: 固定科目とテスト期間")
        print("   - Phase2: 5組合同授業")
        print("   - Phase3: 交流学級の自立活動")
        print("   - Phase4: 通常授業")
        print("   - Phase5: 空きコマ埋め")
        print("2. インクリメンタル最適化")
        print("   - 部分的な再配置による改善")
        print("   - 違反数の段階的削減")


def main():
    """メイン処理"""
    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    tool = TimetableDiagnosticTool()
    tool.run_diagnostics()
    
    print("\n" + "="*60)
    print("診断完了")
    print("="*60)


if __name__ == "__main__":
    main()