#!/usr/bin/env python3
"""体育館使用競合分析スクリプト"""

import csv
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass

@dataclass
class GymUsageInfo:
    """体育館使用情報"""
    time_slot: str
    day: str
    period: int
    classes: List[str]
    groups: List[Set[str]]
    group_count: int

class GymUsageAnalyzer:
    def __init__(self):
        # 交流ペアの定義
        self.exchange_pairs = {
            "1年6組": "1年1組",
            "1年7組": "1年2組",
            "2年6組": "2年3組",
            "2年7組": "2年2組",
            "3年6組": "3年3組",
            "3年7組": "3年2組"
        }
        
        # 5組合同のクラス
        self.grade5_classes = {"1年5組", "2年5組", "3年5組"}
        
    def load_timetable(self, filepath: str) -> Dict[str, Dict[Tuple[str, int], str]]:
        """時間割データを読み込む"""
        timetable = {}
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header1 = next(reader)  # 曜日
            header2 = next(reader)  # 時限
            
            for row in reader:
                if not row[0] or row[0] == "":
                    continue
                    
                class_name = row[0]
                timetable[class_name] = {}
                
                for i in range(1, len(row)):
                    if i - 1 < len(header1) - 1:
                        day = header1[i]
                        period = int(header2[i])
                        subject = row[i]
                        timetable[class_name][(day, period)] = subject
                        
        return timetable
    
    def identify_groups(self, pe_classes: List[str]) -> List[Set[str]]:
        """体育実施クラスをグループに分類"""
        groups = []
        processed = set()
        
        # 1. 5組合同をチェック
        grade5_in_pe = self.grade5_classes.intersection(set(pe_classes))
        if len(grade5_in_pe) == 3:  # 全ての5組が体育
            groups.append(self.grade5_classes)
            processed.update(self.grade5_classes)
        elif len(grade5_in_pe) > 0:  # 一部の5組だけが体育（これは問題）
            for cls in grade5_in_pe:
                groups.append({cls})
                processed.add(cls)
        
        # 2. 交流ペアをチェック
        for exchange, parent in self.exchange_pairs.items():
            if exchange in pe_classes and parent in pe_classes:
                if exchange not in processed and parent not in processed:
                    groups.append({exchange, parent})
                    processed.update({exchange, parent})
        
        # 3. 単独クラスを追加
        for cls in pe_classes:
            if cls not in processed:
                groups.append({cls})
                processed.add(cls)
        
        return groups
    
    def analyze_gym_usage(self, timetable: Dict[str, Dict[Tuple[str, int], str]]) -> List[GymUsageInfo]:
        """体育館使用状況を分析"""
        gym_usage = []
        
        # 全時間帯をチェック
        days = ["月", "火", "水", "木", "金"]
        periods = [1, 2, 3, 4, 5, 6]
        
        for day in days:
            for period in periods:
                # この時間帯に体育を行うクラスを収集
                pe_classes = []
                for class_name, schedule in timetable.items():
                    subject = schedule.get((day, period), "")
                    if subject == "保" or subject == "保健":
                        pe_classes.append(class_name)
                
                if pe_classes:
                    # グループを識別
                    groups = self.identify_groups(pe_classes)
                    
                    info = GymUsageInfo(
                        time_slot=f"{day}曜{period}限",
                        day=day,
                        period=period,
                        classes=pe_classes,
                        groups=groups,
                        group_count=len(groups)
                    )
                    gym_usage.append(info)
        
        return gym_usage
    
    def print_analysis(self, gym_usage: List[GymUsageInfo]):
        """分析結果を表示"""
        print("=== 体育館使用状況分析 ===\n")
        
        # 競合がある時間帯
        conflicts = [info for info in gym_usage if info.group_count >= 2]
        
        if conflicts:
            print("【競合が発生している時間帯】")
            for info in conflicts:
                print(f"\n{info.time_slot}:")
                print(f"  体育実施クラス: {', '.join(sorted(info.classes))}")
                print(f"  グループ数: {info.group_count}")
                print("  グループ詳細:")
                for i, group in enumerate(info.groups, 1):
                    group_type = self._get_group_type(group)
                    print(f"    グループ{i} ({group_type}): {', '.join(sorted(group))}")
        else:
            print("競合は発生していません。")
        
        # 統計情報
        print(f"\n【統計情報】")
        print(f"体育実施時間帯数: {len(gym_usage)}")
        print(f"競合発生時間帯数: {len(conflicts)}")
        
        # 全体育実施時間帯の詳細
        print("\n【全体育実施時間帯】")
        for info in gym_usage:
            print(f"\n{info.time_slot}:")
            print(f"  体育実施クラス: {', '.join(sorted(info.classes))}")
            print(f"  グループ数: {info.group_count}")
            print("  グループ詳細:")
            for i, group in enumerate(info.groups, 1):
                group_type = self._get_group_type(group)
                print(f"    グループ{i} ({group_type}): {', '.join(sorted(group))}")
            if info.group_count >= 2:
                print("  → 競合あり！")
        
        # 特に注意すべき時間帯の詳細
        print("\n【要確認時間帯の詳細】")
        check_slots = [("火", 2), ("水", 3), ("木", 1)]
        
        for day, period in check_slots:
            slot_info = next((info for info in gym_usage 
                            if info.day == day and info.period == period), None)
            if slot_info:
                print(f"\n{day}曜{period}限:")
                print(f"  体育実施クラス: {', '.join(sorted(slot_info.classes))}")
                print(f"  グループ数: {slot_info.group_count}")
                print("  グループ詳細:")
                for i, group in enumerate(slot_info.groups, 1):
                    group_type = self._get_group_type(group)
                    print(f"    グループ{i} ({group_type}): {', '.join(sorted(group))}")
                if slot_info.group_count >= 2:
                    print("  → 競合あり！")
            else:
                print(f"\n{day}曜{period}限: 体育なし")
    
    def _get_group_type(self, group: Set[str]) -> str:
        """グループの種類を判定"""
        if group == self.grade5_classes:
            return "5組合同"
        elif len(group) == 2:
            # 交流ペアかチェック
            for cls in group:
                if cls in self.exchange_pairs:
                    partner = self.exchange_pairs[cls]
                    if partner in group:
                        return "交流ペア"
        return "単独"

def main():
    analyzer = GymUsageAnalyzer()
    
    # 時間割データを読み込む
    timetable_path = "/Users/hayashimitsuhiro/Desktop/timetable_v5/data/output/output.csv"
    timetable = analyzer.load_timetable(timetable_path)
    
    # 体育館使用状況を分析
    gym_usage = analyzer.analyze_gym_usage(timetable)
    
    # 結果を表示
    analyzer.print_analysis(gym_usage)

if __name__ == "__main__":
    main()