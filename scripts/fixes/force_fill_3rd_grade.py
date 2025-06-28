#!/usr/bin/env python3
"""3年生の6限目を強制的に埋めるスクリプト"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.application.services.data_loading_service import DataLoadingService
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from src.domain.value_objects.assignment import Assignment
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
    
    print("=== 3年生の6限目を強制的に埋める ===\n")
    
    # 埋めるべきスロット
    slots_to_fill = [
        # 親学級と交流学級のペア
        (TimeSlot("月", 6), ClassReference(3, 3), ClassReference(3, 6), "数", "森山"),
        (TimeSlot("火", 6), ClassReference(3, 3), ClassReference(3, 6), "理", "白石"),
        # 5組（全学年同期）
        (TimeSlot("火", 6), ClassReference(3, 5), None, "保", "財津"),
        (TimeSlot("水", 6), ClassReference(3, 5), None, "数", "金子み"),
    ]
    
    for time_slot, class_ref, exchange_ref, subject_name, teacher_name in slots_to_fill:
        print(f"\n{class_ref.full_name} {time_slot}に{subject_name}({teacher_name})を配置:")
        
        # 既存の割り当てをチェック
        existing = schedule.get_assignment(time_slot, class_ref)
        if existing:
            print(f"  既に{existing.subject.name}が配置されています")
            continue
        
        # 科目と教師を取得
        subject = None
        teacher = None
        
        for subj in school.get_all_standard_hours(class_ref).keys():
            if subj.name == subject_name:
                subject = subj
                break
        
        for t in school.get_all_teachers():
            if teacher_name in t.name:
                teacher = t
                break
        
        if not subject or not teacher:
            print(f"  エラー: 科目または教師が見つかりません")
            continue
        
        # 割り当てを作成
        assignment = Assignment(class_ref, subject, teacher)
        
        try:
            # メインクラスに配置
            schedule.assign(time_slot, assignment)
            print(f"  ✓ {class_ref.full_name}に配置しました")
            
            # 交流学級がある場合は同期
            if exchange_ref:
                exchange_assignment = Assignment(exchange_ref, subject, teacher)
                schedule.assign(time_slot, exchange_assignment)
                print(f"  ✓ {exchange_ref.full_name}も同期しました")
            
            # 5組の場合は全学年同期
            if class_ref.class_number == 5:
                for grade in [1, 2]:
                    sync_class = ClassReference(grade, 5)
                    sync_assignment = Assignment(sync_class, subject, teacher)
                    schedule.assign(time_slot, sync_assignment)
                    print(f"  ✓ {sync_class.full_name}も同期しました")
            
        except Exception as e:
            print(f"  エラー: {e}")
    
    # 保存
    print("\n時間割を保存中...")
    csv_repo.save_schedule(schedule, "output.csv")
    print("完了！")

if __name__ == "__main__":
    main()