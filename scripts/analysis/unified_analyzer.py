#!/usr/bin/env python3
"""統合分析ツール - 全ての分析機能を1つのスクリプトに統合"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.config.path_config import path_config
from src.domain.value_objects.time_slot import TimeSlot, ClassReference

logger = logging.getLogger(__name__)


class UnifiedAnalyzer:
    """全ての分析機能を統合したクラス"""
    
    def __init__(self):
        self.schedule_repo = CSVScheduleRepository()
        self.school_repo = CSVSchoolRepository(path_config.base_config_dir)
        self.schedule = None
        self.school = None
    
    def load_data(self, schedule_file: str = "output.csv"):
        """スケジュールと学校データを読み込む"""
        try:
            # 学校データを読み込み
            self.school = self.school_repo.load_school_data()
            
            # スケジュールを読み込み
            output_path = path_config.get_output_path(schedule_file)
            self.schedule = self.schedule_repo.load(str(output_path), self.school)
            
            logger.info(f"データを読み込みました: {output_path}")
            return True
        except Exception as e:
            logger.error(f"データ読み込みエラー: {e}")
            return False
    
    def analyze_all(self) -> Dict[str, List[str]]:
        """全ての制約違反を分析"""
        results = {
            "teacher_conflicts": self._analyze_teacher_conflicts(),
            "daily_duplicates": self._analyze_daily_duplicates(),
            "gym_usage": self._analyze_gym_usage(),
            "exchange_sync": self._analyze_exchange_sync(),
            "jiritsu_violations": self._analyze_jiritsu_violations()
        }
        return results
    
    def _analyze_teacher_conflicts(self) -> List[str]:
        """教師の重複を分析"""
        violations = []
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                teacher_assignments = {}
                
                for class_ref in self.school.get_all_classes():
                    assignment = self.schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        teacher_name = assignment.teacher.name
                        if teacher_name not in teacher_assignments:
                            teacher_assignments[teacher_name] = []
                        teacher_assignments[teacher_name].append(class_ref)
                
                # 重複をチェック
                for teacher, classes in teacher_assignments.items():
                    # 5組の合同授業は除外
                    grade5_classes = [c for c in classes if c.class_number == 5]
                    non_grade5_classes = [c for c in classes if c.class_number != 5]
                    
                    if len(non_grade5_classes) > 1 or (grade5_classes and non_grade5_classes):
                        violations.append(
                            f"{day}{period}限: {teacher}が複数クラスを担当 - "
                            f"{', '.join(str(c) for c in classes)}"
                        )
        
        return violations
    
    def _analyze_daily_duplicates(self) -> List[str]:
        """日内重複を分析"""
        violations = []
        
        for class_ref in self.school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                subjects_in_day = {}
                
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = self.schedule.get_assignment(time_slot, class_ref)
                    
                    if assignment:
                        subject = assignment.subject.name
                        if subject not in ["欠", "YT", "道", "学", "総", "学総", "行"]:
                            if subject not in subjects_in_day:
                                subjects_in_day[subject] = []
                            subjects_in_day[subject].append(period)
                
                # 重複をチェック
                for subject, periods in subjects_in_day.items():
                    if len(periods) > 1:
                        violations.append(
                            f"{class_ref} {day}: {subject}が複数回配置 - "
                            f"{', '.join(f'{p}限' for p in periods)}"
                        )
        
        return violations
    
    def _analyze_gym_usage(self) -> List[str]:
        """体育館使用状況を分析"""
        violations = []
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                gym_classes = []
                
                for class_ref in self.school.get_all_classes():
                    assignment = self.schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name == "保":
                        gym_classes.append(class_ref)
                
                # 体育館使用のルールをチェック
                if len(gym_classes) > 1:
                    # 5組の合同授業は1つとしてカウント
                    grade5_count = len([c for c in gym_classes if c.class_number == 5])
                    if grade5_count > 0:
                        non_grade5 = [c for c in gym_classes if c.class_number != 5]
                        if non_grade5:
                            violations.append(
                                f"{day}{period}限: 体育館使用違反 - "
                                f"{', '.join(str(c) for c in gym_classes)}"
                            )
                    else:
                        # 親学級と交流学級のペアは許可
                        exchange_pairs = [
                            (ClassReference(1, 1), ClassReference(1, 6)),
                            (ClassReference(1, 2), ClassReference(1, 7)),
                            (ClassReference(2, 3), ClassReference(2, 6)),
                            (ClassReference(2, 2), ClassReference(2, 7)),
                            (ClassReference(3, 3), ClassReference(3, 6)),
                            (ClassReference(3, 2), ClassReference(3, 7))
                        ]
                        
                        valid_pair = False
                        for parent, exchange in exchange_pairs:
                            if parent in gym_classes and exchange in gym_classes:
                                if len(gym_classes) == 2:
                                    valid_pair = True
                                    break
                        
                        if not valid_pair:
                            violations.append(
                                f"{day}{period}限: 体育館使用違反 - "
                                f"{', '.join(str(c) for c in gym_classes)}"
                            )
        
        return violations
    
    def _analyze_exchange_sync(self) -> List[str]:
        """交流学級同期を分析"""
        violations = []
        
        exchange_pairs = [
            (ClassReference(1, 1), ClassReference(1, 6)),
            (ClassReference(1, 2), ClassReference(1, 7)),
            (ClassReference(2, 3), ClassReference(2, 6)),
            (ClassReference(2, 2), ClassReference(2, 7)),
            (ClassReference(3, 3), ClassReference(3, 6)),
            (ClassReference(3, 2), ClassReference(3, 7))
        ]
        
        for parent_class, exchange_class in exchange_pairs:
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    parent_assignment = self.schedule.get_assignment(time_slot, parent_class)
                    exchange_assignment = self.schedule.get_assignment(time_slot, exchange_class)
                    
                    if exchange_assignment and exchange_assignment.subject.name not in ["自立", "日生", "作業"]:
                        if not parent_assignment or parent_assignment.subject != exchange_assignment.subject:
                            violations.append(
                                f"{day}{period}限: {exchange_class}と{parent_class}の同期違反 - "
                                f"{exchange_assignment.subject.name if exchange_assignment else '空き'} != "
                                f"{parent_assignment.subject.name if parent_assignment else '空き'}"
                            )
        
        return violations
    
    def _analyze_jiritsu_violations(self) -> List[str]:
        """自立活動の配置違反を分析"""
        violations = []
        
        exchange_pairs = [
            (ClassReference(1, 1), ClassReference(1, 6)),
            (ClassReference(1, 2), ClassReference(1, 7)),
            (ClassReference(2, 3), ClassReference(2, 6)),
            (ClassReference(2, 2), ClassReference(2, 7)),
            (ClassReference(3, 3), ClassReference(3, 6)),
            (ClassReference(3, 2), ClassReference(3, 7))
        ]
        
        for parent_class, exchange_class in exchange_pairs:
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    parent_assignment = self.schedule.get_assignment(time_slot, parent_class)
                    exchange_assignment = self.schedule.get_assignment(time_slot, exchange_class)
                    
                    if exchange_assignment and exchange_assignment.subject.name == "自立":
                        if not parent_assignment or parent_assignment.subject.name not in ["数", "英"]:
                            violations.append(
                                f"{day}{period}限: {exchange_class}の自立活動違反 - "
                                f"{parent_class}が{parent_assignment.subject.name if parent_assignment else '空き'}（数/英である必要）"
                            )
                        
                        if period == 6:
                            violations.append(
                                f"{day}{period}限: {exchange_class}の自立活動は6限に配置不可"
                            )
        
        return violations
    
    def print_analysis_results(self, results: Dict[str, List[str]]):
        """分析結果を出力"""
        total_violations = 0
        
        print("\n" + "="*60)
        print("統合分析結果")
        print("="*60)
        
        for violation_type, violations in results.items():
            if violations:
                print(f"\n【{violation_type}】 ({len(violations)}件)")
                for violation in violations[:10]:  # 最初の10件を表示
                    print(f"  - {violation}")
                if len(violations) > 10:
                    print(f"  ... 他 {len(violations) - 10} 件")
                total_violations += len(violations)
        
        print(f"\n総違反数: {total_violations}件")
        print("="*60)
    
    def analyze(self, analysis_type: str = "all", fix: bool = False):
        """指定された分析を実行"""
        if not self.load_data():
            return
        
        if analysis_type == "all":
            results = self.analyze_all()
            self.print_analysis_results(results)
        elif analysis_type == "teacher":
            violations = self._analyze_teacher_conflicts()
            print(f"\n教師重複違反: {len(violations)}件")
            for v in violations:
                print(f"  - {v}")
        elif analysis_type == "gym":
            violations = self._analyze_gym_usage()
            print(f"\n体育館使用違反: {len(violations)}件")
            for v in violations:
                print(f"  - {v}")
        elif analysis_type == "daily":
            violations = self._analyze_daily_duplicates()
            print(f"\n日内重複違反: {len(violations)}件")
            for v in violations:
                print(f"  - {v}")
        elif analysis_type == "exchange":
            violations = self._analyze_exchange_sync()
            print(f"\n交流学級同期違反: {len(violations)}件")
            for v in violations:
                print(f"  - {v}")
        
        if fix:
            print("\n[注意] 自動修正機能は現在実装中です。")


def main():
    parser = argparse.ArgumentParser(description='統合分析ツール')
    parser.add_argument('--type', choices=['all', 'teacher', 'gym', 'daily', 'exchange'],
                        default='all', help='分析タイプ')
    parser.add_argument('--fix', action='store_true', help='自動修正を実行（未実装）')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細ログを表示')
    
    args = parser.parse_args()
    
    # ログレベルの設定
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)
    
    analyzer = UnifiedAnalyzer()
    analyzer.analyze(args.type, args.fix)


if __name__ == "__main__":
    main()