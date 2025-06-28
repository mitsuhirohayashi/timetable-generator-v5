#!/usr/bin/env python3
"""親学級と交流学級の同期を修正するスクリプト"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.application.services.data_loading_service import DataLoadingService
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from src.domain.services.exchange_class_service import ExchangeClassService

def main():
    # サービスの初期化
    data_loading_service = DataLoadingService()
    data_dir = Path("data")
    
    # 学校データ読み込み
    school, use_enhanced_features = data_loading_service.load_school_data(data_dir)
    
    # 最新の時間割を読み込み
    csv_repo = CSVScheduleRepository()
    schedule = csv_repo.load_desired_schedule("data/output/output.csv", school)
    
    # ExchangeClassServiceの初期化
    exchange_service = ExchangeClassService()
    
    print("=== 親学級と交流学級の同期を修正 ===\n")
    
    # 問題のあるスロットをチェック
    days = ["月", "火", "水"]
    fixes_made = 0
    
    for day in days:
        time_slot = TimeSlot(day, 6)
        
        # 3年3組（親学級）と3年6組（交流学級）をチェック
        parent_class = ClassReference(3, 3)
        exchange_class = ClassReference(3, 6)
        
        parent_assignment = schedule.get_assignment(time_slot, parent_class)
        exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
        
        if exchange_assignment and not parent_assignment:
            # 交流学級に割り当てがあるが親学級が空の場合
            if exchange_assignment.subject.name not in ["自立", "日生", "作業"]:
                print(f"{time_slot}: {exchange_class.full_name}に{exchange_assignment.subject.name}があるが、{parent_class.full_name}が空です")
                
                # 交流学級の割り当てを削除（空きスロットフィラーで後で埋める）
                schedule.remove_assignment(time_slot, exchange_class)
                print(f"  → {exchange_class.full_name}の割り当てを削除しました")
                fixes_made += 1
        
        # 3年2組（親学級）と3年7組（交流学級）も同様にチェック
        parent_class2 = ClassReference(3, 2)
        exchange_class2 = ClassReference(3, 7)
        
        parent_assignment2 = schedule.get_assignment(time_slot, parent_class2)
        exchange_assignment2 = schedule.get_assignment(time_slot, exchange_class2)
        
        if exchange_assignment2 and not exchange_assignment2.subject.name in ["自立", "日生", "作業"]:
            # 交流学級が通常教科の場合、親学級と同期する必要がある
            if parent_assignment2 and exchange_assignment2.subject.name != parent_assignment2.subject.name:
                print(f"{time_slot}: {parent_class2.full_name}と{exchange_class2.full_name}が同期していません")
                print(f"  親学級: {parent_assignment2.subject.name}")
                print(f"  交流学級: {exchange_assignment2.subject.name}")
                # この場合は手動で修正が必要
    
    if fixes_made > 0:
        # 保存
        print(f"\n{fixes_made}箇所を修正しました。時間割を保存中...")
        csv_repo.save_schedule(schedule, "output.csv")
        print("完了！")
    else:
        print("修正が必要な箇所はありませんでした。")

if __name__ == "__main__":
    main()