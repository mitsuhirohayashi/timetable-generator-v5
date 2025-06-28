#!/usr/bin/env python3
"""体育館使用の詳細分析スクリプト"""
import sys
from pathlib import Path

# timetable_v5ディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.infrastructure.config.path_config import path_config
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot

def main():
    """メイン処理"""
    print("=== 体育館使用の詳細分析 ===\n")
    
    # リポジトリ初期化
    schedule_repo = CSVScheduleRepository(path_config.data_dir)
    school_repo = CSVSchoolRepository(path_config.data_dir)
    
    # 学校データ読み込み
    school = school_repo.load_school_data("config/base_timetable.csv")
    
    # 時間割読み込み
    schedule = schedule_repo.load_desired_schedule(
        str(path_config.default_output_csv),
        school
    )
    
    # 正常パターンの定義
    grade5_group = ["1年5組", "2年5組", "3年5組"]
    exchange_pairs = [
        ("1年1組", "1年6組"), ("1年2組", "1年7組"),
        ("2年3組", "2年6組"), ("2年2組", "2年7組"),
        ("3年3組", "3年6組"), ("3年2組", "3年7組")
    ]
    
    for day in ["月", "火", "水", "木", "金"]:
        print(f"\n【{day}曜日】")
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            pe_classes = []
            
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject == "保":
                    pe_classes.append(class_ref)
            
            if pe_classes:
                print(f"{period}校時: {', '.join(pe_classes)}")
                
                # 違反チェック
                if len(pe_classes) > 1:
                    # 5組合同授業チェック
                    if set(pe_classes) == set(grade5_group):
                        print("  → 正常（5組合同授業）")
                        continue
                    
                    # 交流学級ペアチェック
                    is_valid_pair = False
                    for parent, exchange in exchange_pairs:
                        if set(pe_classes) == {parent, exchange}:
                            print(f"  → 正常（{parent}と{exchange}の交流学級ペア）")
                            is_valid_pair = True
                            break
                    
                    if not is_valid_pair:
                        print(f"  → ⚠️ 違反（同時に{len(pe_classes)}クラスが体育）")


if __name__ == "__main__":
    main()