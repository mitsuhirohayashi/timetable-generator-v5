#!/usr/bin/env python3
"""3年6組の自立活動配置可能性の分析"""

import sys
from pathlib import Path

# プロジェクトのルートディレクトリをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.parsers.natural_followup_parser import NaturalFollowUpParser

def analyze_jiritsu_opportunities():
    """3年6組の自立活動配置可能なスロットを分析"""
    # CSVリポジトリを初期化
    csv_repo = CSVScheduleRepository()
    schedule = csv_repo.load("data/output/output.csv")
    
    # テスト期間情報を読み込む
    parser = NaturalFollowUpParser(Path("data/input"))
    result = parser.parse_file("Follow-up.csv")
    test_periods = set()
    
    if result.get("test_periods"):
        for test_period in result["test_periods"]:
            day = test_period.day
            for period in test_period.periods:
                test_periods.add((day, period))
    
    print("=== 3年6組の自立活動配置可能スロット分析 ===")
    print(f"テスト期間: {sorted(test_periods)}\n")
    
    # 3年6組と3年3組のクラス参照
    class_3_6 = ClassReference(3, 6)
    class_3_3 = ClassReference(3, 3)
    
    opportunities = []
    
    # 全時間帯をチェック
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            is_test_period = (day, period) in test_periods
            
            # 3年3組と3年6組の割り当てを取得
            assignment_3_3 = schedule.get_assignment(time_slot, class_3_3)
            assignment_3_6 = schedule.get_assignment(time_slot, class_3_6)
            
            # 3年3組が数学または英語を持っている場合
            if assignment_3_3 and assignment_3_3.subject.name in ["数", "英"]:
                # 3年6組の状態を確認
                status = "配置可能"
                reason = ""
                
                if is_test_period:
                    # テスト期間中は通常の自立活動ルール適用
                    status = "テスト期間"
                    reason = "テスト期間中は特別ルール免除"
                elif assignment_3_6:
                    status = "不可"
                    reason = f"3-6は{assignment_3_6.subject.name}で既に埋まっている"
                elif time_slot.day == "月" and time_slot.period == 6:
                    status = "不可"
                    reason = "月曜6限は欠"
                elif (time_slot.day in ["火", "水", "金"] and time_slot.period == 6):
                    status = "不可"
                    reason = "YT固定"
                
                opportunities.append({
                    'time_slot': time_slot,
                    'parent_subject': assignment_3_3.subject.name,
                    'parent_teacher': assignment_3_3.teacher.name,
                    'status': status,
                    'reason': reason,
                    'current_3_6': assignment_3_6.subject.name if assignment_3_6 else "空き"
                })
    
    # 結果を表示
    print("【3-3が数学または英語を持っているスロット】")
    print("-" * 80)
    print(f"{'時間':8} {'3-3教科':8} {'3-3教師':12} {'3-6現在':8} {'状態':8} {'理由'}")
    print("-" * 80)
    
    available_count = 0
    for opp in opportunities:
        if opp['status'] == "配置可能":
            available_count += 1
            print(f"★ ", end="")
        else:
            print(f"  ", end="")
        
        print(f"{opp['time_slot']} {opp['parent_subject']:8} {opp['parent_teacher']:12} "
              f"{opp['current_3_6']:8} {opp['status']:8} {opp['reason']}")
    
    print("-" * 80)
    print(f"\n配置可能なスロット: {available_count}個")
    print(f"3年6組は週2コマの自立活動が必要")
    
    if available_count < 2:
        print(f"\n⚠️  配置可能スロットが不足しています（{available_count}/2）")
        print("原因: 3年3組が数学・英語を持つ時間に3年6組が既に他の授業で埋まっている")

if __name__ == "__main__":
    analyze_jiritsu_opportunities()