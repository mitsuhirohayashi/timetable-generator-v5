#!/usr/bin/env python3
"""交流学級同期問題の詳細調査スクリプト"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.config.path_config import PathConfig
from src.domain.value_objects.time_slot import TimeSlot, ClassReference

def main():
    """メイン処理"""
    # パスの設定
    path_config = PathConfig()
    output_path = path_config.get_output_path('output.csv')
    
    # CSVを読み込む
    csv_repo = CSVScheduleRepository()
    schedule = csv_repo.load('output.csv')
    
    print("=== 交流学級同期問題の調査 ===")
    print()
    
    # 3年6組と3年3組の全スケジュールを表示
    class_3_3 = ClassReference(3, 3)
    class_3_6 = ClassReference(3, 6)
    
    print("3年3組（親学級）と3年6組（交流学級）のスケジュール比較:")
    print("-" * 80)
    print(f"{'曜日':<4} {'時限':<4} {'3年3組':<20} {'3年6組':<20} {'同期状態':<10}")
    print("-" * 80)
    
    sync_violations = []
    daily_duplicates = {}
    
    for day in ["月", "火", "水", "木", "金"]:
        # 3年3組の日内重複チェック用
        day_subjects_3_3 = []
        
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            # 3年3組の授業
            assignment_3_3 = schedule.get_assignment(time_slot, class_3_3)
            subject_3_3 = assignment_3_3.subject.name if assignment_3_3 else "（空き）"
            teacher_3_3 = assignment_3_3.teacher.name if assignment_3_3 else ""
            
            # 3年6組の授業
            assignment_3_6 = schedule.get_assignment(time_slot, class_3_6)
            subject_3_6 = assignment_3_6.subject.name if assignment_3_6 else "（空き）"
            teacher_3_6 = assignment_3_6.teacher.name if assignment_3_6 else ""
            
            # 日内重複チェック（3年3組）
            if assignment_3_3:
                day_subjects_3_3.append((period, subject_3_3))
            
            # 同期チェック
            sync_status = "OK"
            if subject_3_6 == "自立":
                # 自立活動の場合、親学級は数学か英語である必要がある
                if subject_3_3 not in ["数", "英"]:
                    sync_status = "❌自立違反"
                    sync_violations.append((time_slot, subject_3_3, subject_3_6))
            elif subject_3_3 != subject_3_6:
                # 自立活動以外は同じ科目である必要がある
                if not (subject_3_3 == "（空き）" and subject_3_6 == "（空き）"):
                    sync_status = "❌同期違反"
                    sync_violations.append((time_slot, subject_3_3, subject_3_6))
            
            # 表示
            display_3_3 = f"{subject_3_3}"
            if teacher_3_3:
                display_3_3 += f"({teacher_3_3})"
            
            display_3_6 = f"{subject_3_6}"
            if teacher_3_6:
                display_3_6 += f"({teacher_3_6})"
            
            print(f"{day:<4} {period:<4} {display_3_3:<20} {display_3_6:<20} {sync_status:<10}")
        
        # 日内重複チェック
        subject_counts = {}
        for period, subject in day_subjects_3_3:
            if subject not in ["欠", "YT", "学", "総", "道", "学総", "行"]:  # 固定科目を除外
                subject_counts[subject] = subject_counts.get(subject, 0) + 1
        
        for subject, count in subject_counts.items():
            if count > 1:
                if day not in daily_duplicates:
                    daily_duplicates[day] = []
                daily_duplicates[day].append((subject, count))
        
        print()
    
    print("\n=== 問題のまとめ ===")
    
    if sync_violations:
        print(f"\n交流学級同期違反: {len(sync_violations)}件")
        for time_slot, parent_subject, exchange_subject in sync_violations:
            print(f"  - {time_slot}: 3年3組={parent_subject}, 3年6組={exchange_subject}")
    
    if daily_duplicates:
        print(f"\n日内重複違反（3年3組）:")
        for day, duplicates in daily_duplicates.items():
            for subject, count in duplicates:
                print(f"  - {day}曜日: {subject}が{count}回")
    
    # 根本原因の推定
    print("\n=== 根本原因の分析 ===")
    print("1. ExchangeClassServiceの問題:")
    print("   - validate_exchange_sync()メソッドが自立活動以外の同期をチェックしていない")
    print("   - 通常授業（保健体育など）の同期が保証されていない")
    print("\n2. DailyDuplicateConstraintの問題:")
    print("   - 主要教科（英語含む）に対して1日2回まで許可している")
    print("   - CLAUDE.mdの「1日1コマ制限」ルールと矛盾")
    print("\n3. 生成アルゴリズムの問題:")
    print("   - 交流学級への配置時に親学級との同期を考慮していない可能性")
    print("   - 空きスロット埋めで同期が崩れている可能性")

if __name__ == "__main__":
    main()