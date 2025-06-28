#!/usr/bin/env python3
"""統合された空きスロット埋めスクリプト"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.domain.services.smart_empty_slot_filler import SmartEmptySlotFiller
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.di_container import DIContainer, get_data_loader

def main():
    """メイン処理"""
    print("=== 空きスロット自動埋めシステム ===\n")
    
    # DIコンテナの初期化
    di_container = DIContainer()
    
    # リポジトリの取得
    csv_repo = CSVScheduleRepository()
    data_loader = get_data_loader()
    
    # 学校データの読み込み
    print("学校データを読み込み中...")
    school = data_loader.load_all_data()
    
    # スケジュールの読み込み
    print("現在の時間割を読み込み中...")
    schedule = csv_repo.load_schedule("data/output/output.csv", school)
    
    # 空きスロットのカウント
    empty_count = 0
    for time_slot, assignment in schedule.get_all_assignments():
        if assignment is None or assignment.subject.name == "":
            empty_count += 1
    
    print(f"\n現在の空きスロット数: {empty_count}")
    
    if empty_count == 0:
        print("空きスロットはありません。処理を終了します。")
        return
    
    # 制約バリデーターの取得
    constraint_validator = di_container.get_constraint_validator()
    
    # SmartEmptySlotFillerの作成と実行
    print("\n空きスロットを埋めています...")
    filler = SmartEmptySlotFiller(constraint_validator)
    filled_count = filler.fill_all_empty_slots(schedule, school)
    
    print(f"\n{filled_count}個の空きスロットを埋めました。")
    
    # 結果の保存
    if filled_count > 0:
        print("\n結果を保存中...")
        csv_repo.save_schedule(schedule, "data/output/output.csv", school)
        print("保存が完了しました: data/output/output.csv")
    
    # 最終的な空きスロット数を確認
    final_empty_count = 0
    for time_slot, assignment in schedule.get_all_assignments():
        if assignment is None or assignment.subject.name == "":
            final_empty_count += 1
    
    print(f"\n最終的な空きスロット数: {final_empty_count}")
    
    if final_empty_count > 0:
        print(f"\n⚠️  まだ{final_empty_count}個の空きスロットが残っています。")
        print("これらは制約により埋められませんでした。")

if __name__ == "__main__":
    main()