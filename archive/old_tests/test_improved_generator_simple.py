#!/usr/bin/env python3
"""改善版時間割生成器の簡易テスト

DIコンテナを使わずに直接テストします。
"""
import os
import sys
import logging
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.domain.services.implementations.improved_csp_generator import ImprovedCSPGenerator
from src.infrastructure.di_container import DIContainer


def main():
    """メイン処理"""
    print("\n" + "="*60)
    print("改善版時間割生成器の簡易テスト")
    print("="*60)
    
    # ロギング設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # DIコンテナの初期化
    print("\n1. システムを初期化中...")
    container = DIContainer()
    
    # データ読み込み
    print("\n2. データを読み込み中...")
    data_loader = container.get_data_loading_use_case()
    school, initial_schedule, teacher_absences = data_loader.load_all_data()
    print(f"  - クラス数: {len(school.get_all_classes())}")
    print(f"  - 教師数: {len(school.teachers)}")
    print(f"  - 科目数: {len(school.subjects)}")
    
    # 制約登録
    print("\n3. 制約を登録中...")
    constraint_service = container.get_constraint_registration_service()
    constraint_service.register_all_constraints(school, teacher_absences)
    
    # 改善版生成器でテスト
    print("\n4. 改善版CSP生成器で時間割を生成中...")
    generator = ImprovedCSPGenerator()
    
    try:
        schedule = generator.generate(school, initial_schedule)
        print("✓ 生成が完了しました")
    except Exception as e:
        print(f"✗ 生成中にエラーが発生: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 統計情報の表示
    if hasattr(generator, 'stats'):
        stats = generator.stats
        print("\n生成統計:")
        print(f"  - Phase 1 (5組): {stats.get('phase1_filled', 0)}スロット")
        print(f"  - Phase 2 (交流学級): {stats.get('phase2_filled', 0)}スロット")
        print(f"  - Phase 3 (通常クラス): {stats.get('phase3_filled', 0)}スロット")
        print(f"  - 解決された競合: {stats.get('conflicts_resolved', 0)}件")
    
    # 結果の保存
    print("\n5. 結果を保存中...")
    try:
        repository = container.get_schedule_repository()
        repository.save_schedule(schedule, "output_improved_test.csv")
        print("✓ 保存が完了しました: data/output/output_improved_test.csv")
    except Exception as e:
        print(f"✗ 保存中にエラーが発生: {e}")
    
    # 簡易チェック
    print("\n6. 簡易チェック:")
    
    # 5組の同期チェック
    grade5_violations = 0
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            from src.domain.value_objects.time_slot import TimeSlot, ClassReference
            time_slot = TimeSlot(day, period)
            
            subjects = []
            for grade in [1, 2, 3]:
                class_ref = ClassReference(grade, 5)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment:
                    subjects.append(assignment.subject.name)
            
            if subjects and len(set(subjects)) > 1:
                grade5_violations += 1
    
    print(f"  - 5組同期違反: {grade5_violations}件")
    
    # 空きスロット数
    empty_count = 0
    for class_ref in school.get_all_classes():
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                if not schedule.get_assignment(time_slot, class_ref):
                    empty_count += 1
    
    total_slots = len(school.get_all_classes()) * 5 * 6
    fill_rate = (total_slots - empty_count) / total_slots * 100
    print(f"  - 空きスロット: {empty_count}/{total_slots} ({100-fill_rate:.1f}%)")
    
    print("\n" + "="*60)
    print("テスト完了")
    print("="*60)


if __name__ == "__main__":
    main()