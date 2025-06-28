#!/usr/bin/env python3
"""
フェーズ3: インテリジェント修正システムのテスト

IntelligentScheduleOptimizerの動作を検証し、
10件の教師重複を解決できるか確認します。
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.domain.services.ultrathink.intelligent_schedule_optimizer import IntelligentScheduleOptimizer
from src.application.services.data_loading_service import DataLoadingService
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.config.path_config import path_config
from src.domain.value_objects.time_slot import ClassReference
import logging

logging.basicConfig(level=logging.INFO)

def count_teacher_conflicts(schedule, school):
    """教師重複をカウント（テスト期間を除く）"""
    from collections import defaultdict
    from src.domain.value_objects.time_slot import TimeSlot
    
    test_periods = {
        ("月", 1), ("月", 2), ("月", 3),
        ("火", 1), ("火", 2), ("火", 3),
        ("水", 1), ("水", 2)
    }
    
    fixed_teachers = {
        "欠", "欠課先生", "YT担当", "YT担当先生", 
        "道担当", "道担当先生", "学担当", "学担当先生", 
        "総担当", "総担当先生", "学総担当", "学総担当先生", 
        "行担当", "行担当先生", "技家担当", "技家担当先生"
    }
    
    grade5_refs = {ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)}
    
    conflicts = 0
    days = ["月", "火", "水", "木", "金"]
    
    for day in days:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            # テスト期間はスキップ
            if (day, period) in test_periods:
                continue
            
            # 教師ごとにクラスを収集
            teacher_assignments = defaultdict(list)
            
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.teacher:
                    teacher_name = assignment.teacher.name
                    
                    # 固定科目の教師は除外
                    if teacher_name in fixed_teachers:
                        continue
                    
                    teacher_assignments[teacher_name].append(class_ref)
            
            # 重複をチェック
            for teacher_name, classes in teacher_assignments.items():
                if len(classes) > 1:
                    # 5組のみの場合は正常
                    all_grade5 = all(c in grade5_refs for c in classes)
                    if not all_grade5:
                        conflicts += 1
    
    return conflicts

def main():
    print("=== フェーズ3: インテリジェント修正システムのテスト ===\n")
    
    # データ読み込み
    data_loading_service = DataLoadingService()
    school, _ = data_loading_service.load_school_data(path_config.data_dir)
    
    # 現在の時間割を読み込む
    schedule_repo = CSVScheduleRepository(path_config.data_dir)
    schedule = schedule_repo.load("output/output.csv", school)
    
    # オプティマイザーの作成
    optimizer = IntelligentScheduleOptimizer()
    
    print("【最適化前の状態分析中...】")
    
    # 現在の教師重複をチェック（簡易的な実装）
    teacher_conflicts_count = count_teacher_conflicts(schedule, school)
    print(f"\n検出された教師重複（テスト期間除く）: {teacher_conflicts_count}件")
    
    # 最適化実行
    print("\n【最適化実行中...】")
    
    try:
        stats = optimizer.optimize(schedule, school, max_iterations=20)
        
        print("\n【最適化結果】")
        print(f"初期違反数: {stats['initial_violations']}")
        print(f"最終違反数: {stats['final_violations']}")
        print(f"実行した交換数: {stats['swaps_performed']}")
        print(f"実行した連鎖数: {stats['chains_executed']}")
        print(f"改善スコア: {stats['improvement_score']:.2f}")
        
        # 改善率計算
        if stats['initial_violations'] > 0:
            improvement_rate = (stats['initial_violations'] - stats['final_violations']) / stats['initial_violations'] * 100
            print(f"\n全体改善率: {improvement_rate:.1f}%")
        
        # 最適化後の教師重複をチェック
        teacher_conflicts_after = count_teacher_conflicts(schedule, school)
        print(f"\n最適化後の教師重複: {teacher_conflicts_after}件")
        
        if teacher_conflicts_count > 0:
            teacher_improvement = (teacher_conflicts_count - teacher_conflicts_after) / teacher_conflicts_count * 100
            print(f"教師重複改善率: {teacher_improvement:.1f}%")
        
        # 学習パターンの表示
        print("\n【学習されたパターン】")
        if hasattr(optimizer, 'learning_patterns'):
            for pattern, count in optimizer.learning_patterns.items():
                print(f"- {pattern}: {count}回")
        else:
            print("（学習パターンなし）")
        
        # 時間割を保存
        if teacher_conflicts_after < teacher_conflicts_count:
            output_path = path_config.output_dir / "output_phase3_optimized.csv"
            schedule_repo.save_schedule(schedule, str(output_path))
            print(f"\n最適化後の時間割を保存: {output_path}")
            
    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

def is_test_period(time_slot):
    """テスト期間かどうかをチェック"""
    test_periods = {
        ("月", 1), ("月", 2), ("月", 3),
        ("火", 1), ("火", 2), ("火", 3),
        ("水", 1), ("水", 2)
    }
    return (time_slot.day, time_slot.period) in test_periods

if __name__ == "__main__":
    main()