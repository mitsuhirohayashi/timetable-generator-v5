#!/usr/bin/env python3
"""交流学級制約が誤って適用されていないか調査"""
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
    
    print("=== 交流学級の判定を確認 ===\n")
    
    # 3年生のクラスをチェック
    third_grade_classes = [
        ClassReference(3, 1),
        ClassReference(3, 2),
        ClassReference(3, 3),
        ClassReference(3, 5),
        ClassReference(3, 6),
        ClassReference(3, 7)
    ]
    
    for class_ref in third_grade_classes:
        is_exchange = exchange_service.is_exchange_class(class_ref)
        is_parent = exchange_service.is_parent_class(class_ref)
        
        print(f"{class_ref.full_name}:")
        print(f"  交流学級？: {is_exchange}")
        print(f"  親学級？: {is_parent}")
        
        if is_exchange:
            parent = exchange_service.get_parent_class(class_ref)
            print(f"  親学級: {parent.full_name if parent else 'なし'}")
        
        if is_parent:
            exchange = exchange_service.get_exchange_class(class_ref)
            print(f"  交流学級: {exchange.full_name if exchange else 'なし'}")
        
        print()

if __name__ == "__main__":
    main()