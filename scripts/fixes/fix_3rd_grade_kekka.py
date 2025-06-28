#!/usr/bin/env python3
"""3年5組の月曜6限の「欠」を削除するスクリプト"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.application.services.data_loading_service import DataLoadingService
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.domain.value_objects.time_slot import TimeSlot, ClassReference

def main():
    # サービスの初期化
    data_loading_service = DataLoadingService()
    data_dir = Path("data")
    
    # 学校データ読み込み
    school, use_enhanced_features = data_loading_service.load_school_data(data_dir)
    
    # 最新の時間割を読み込み
    csv_repo = CSVScheduleRepository()
    schedule = csv_repo.load_desired_schedule("data/output/output.csv", school)
    
    print("=== 3年5組 月曜6限の「欠」を削除 ===\n")
    
    # 3年5組の月曜6限をチェック
    time_slot = TimeSlot("月", 6)
    class_ref = ClassReference(3, 5)
    
    assignment = schedule.get_assignment(time_slot, class_ref)
    if assignment and assignment.subject.name == "欠":
        print(f"{class_ref.full_name} {time_slot}: 「欠」を削除します")
        
        # 割り当てを削除
        schedule.remove_assignment(time_slot, class_ref)
        
        # 1年5組と2年5組も同様に削除（5組は同期が必要）
        for grade in [1, 2]:
            sync_class = ClassReference(grade, 5)
            sync_assignment = schedule.get_assignment(time_slot, sync_class)
            if sync_assignment and sync_assignment.subject.name == "欠":
                schedule.remove_assignment(time_slot, sync_class)
                print(f"  {sync_class.full_name}も同期して削除")
        
        # 保存
        print("\n時間割を保存中...")
        csv_repo.save_schedule(schedule, "output.csv")
        print("完了！")
    else:
        print(f"{class_ref.full_name} {time_slot}: 「欠」ではありません")

if __name__ == "__main__":
    main()