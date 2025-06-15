#!/usr/bin/env python3
"""日内重複の発生段階を特定するスクリプト"""

import sys
import logging
from pathlib import Path

# プロジェクトのルートディレクトリをPYTHONPATHに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.infrastructure.parsers.csv_schedule_parser import CSVScheduleParser
from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from src.infrastructure.config.path_manager import PathManager


def check_daily_duplicates(schedule, protected_subjects=None):
    """スケジュール内の日内重複をチェック"""
    if protected_subjects is None:
        protected_subjects = {'YT', '道', '学', '欠', '道徳', '学活', '学総', '総合', '行'}
    
    duplicates = []
    all_classes = set()
    
    # すべてのクラスを収集
    for _, assignment in schedule.get_all_assignments():
        all_classes.add(assignment.class_ref)
    
    # 各クラスごとに日内重複をチェック
    for class_ref in sorted(all_classes):
        for day in ["月", "火", "水", "木", "金"]:
            # その日の全教科を収集
            subjects_in_day = {}
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject.name not in protected_subjects:
                    subject_name = assignment.subject.name
                    if subject_name not in subjects_in_day:
                        subjects_in_day[subject_name] = []
                    subjects_in_day[subject_name].append(period)
            
            # 重複チェック
            for subject, periods in subjects_in_day.items():
                if len(periods) > 1:
                    duplicates.append({
                        'class': class_ref,
                        'day': day,
                        'subject': subject,
                        'periods': periods
                    })
    
    return duplicates


def analyze_schedule_at_stage(schedule_path, stage_name):
    """特定段階のスケジュールを分析"""
    print(f"\n=== {stage_name} ===")
    
    # スケジュールを読み込み
    parser = CSVScheduleParser()
    schedule = parser.parse(schedule_path)
    
    if not schedule:
        print(f"エラー: {schedule_path} を読み込めませんでした")
        return []
    
    # 日内重複をチェック
    duplicates = check_daily_duplicates(schedule)
    
    if duplicates:
        print(f"日内重複が {len(duplicates)} 件見つかりました:")
        for dup in duplicates:
            periods_str = ", ".join([f"{p}限" for p in dup['periods']])
            print(f"  - {dup['class']}の{dup['day']}曜日: {dup['subject']}が{periods_str}に重複")
    else:
        print("日内重複はありません")
    
    return duplicates


def main():
    """メイン処理"""
    logging.basicConfig(level=logging.INFO)
    
    # パス管理
    path_manager = PathManager()
    
    print("日内重複の発生段階を特定しています...")
    
    # 各段階のスケジュールをチェック
    stages = [
        ("最終出力（output.csv）", path_manager.output_dir / "output.csv"),
    ]
    
    all_duplicates = {}
    for stage_name, file_path in stages:
        if file_path.exists():
            duplicates = analyze_schedule_at_stage(file_path, stage_name)
            all_duplicates[stage_name] = duplicates
        else:
            print(f"\n{stage_name}: ファイルが存在しません ({file_path})")
    
    # 発生段階の特定
    print("\n=== 分析結果 ===")
    
    # output.csvの分析
    if "最終出力（output.csv）" in all_duplicates:
        output_dups = set()
        
        for dup in all_duplicates["最終出力（output.csv）"]:
            key = (dup['class'], dup['day'], dup['subject'])
            output_dups.add(key)
        
        # 存在する重複
        if output_dups:
            print("\n生成された時間割に存在する重複:")
            for class_ref, day, subject in output_dups:
                print(f"  - {class_ref}の{day}曜日: {subject}")
        else:
            print("\n生成された時間割に重複はありません")


if __name__ == "__main__":
    main()