#!/usr/bin/env python3
"""
フェーズ4: ハイブリッドアプローチのテスト

全フェーズを統合した究極の時間割生成システムをテストします。
目標: 教師重複0件を達成
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.domain.services.ultrathink.hybrid_schedule_generator import HybridScheduleGenerator
from src.application.services.data_loading_service import DataLoadingService
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.config.path_config import path_config
from src.domain.value_objects.time_slot import ClassReference, TimeSlot
import logging

logging.basicConfig(level=logging.INFO)

def count_teacher_conflicts(schedule, school):
    """教師重複をカウント（テスト期間を除く）"""
    from collections import defaultdict
    
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
    conflict_details = []
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
                        conflict_details.append({
                            'time_slot': time_slot,
                            'teacher': teacher_name,
                            'classes': classes
                        })
    
    return conflicts, conflict_details

def main():
    print("=== フェーズ4: ハイブリッドアプローチのテスト ===\n")
    
    # データ読み込み
    data_loading_service = DataLoadingService()
    school, _ = data_loading_service.load_school_data(path_config.data_dir)
    
    # 現在の時間割を読み込む（初期解として使用）
    schedule_repo = CSVScheduleRepository(path_config.data_dir)
    initial_schedule = schedule_repo.load("output/output.csv", school)
    
    # 現在の状態を確認
    conflicts, details = count_teacher_conflicts(initial_schedule, school)
    print(f"【初期状態】")
    print(f"教師重複: {conflicts}件\n")
    
    if details:
        print("重複の詳細（最初の5件）:")
        for i, detail in enumerate(details[:5]):
            print(f"{i+1}. {detail['time_slot']} - {detail['teacher']}先生")
            print(f"   クラス: {', '.join(str(c) for c in detail['classes'])}")
    
    # ハイブリッド生成器の作成
    generator = HybridScheduleGenerator(
        learning_file="phase4_learning.json",
        enable_logging=True
    )
    
    print("\n【ハイブリッド生成開始】")
    print("目標: 教師重複0件")
    print("-" * 50)
    
    try:
        # 生成実行
        result = generator.generate(
            school=school,
            initial_schedule=None,  # 新規生成
            target_violations=0,    # 違反0を目標
            time_limit=180         # 3分制限
        )
        
        # 結果の確認
        final_conflicts, final_details = count_teacher_conflicts(result.schedule, school)
        
        print("\n" + "=" * 50)
        print("【最終結果】")
        print(f"教師重複: {final_conflicts}件")
        print(f"全違反: {result.statistics['final_violations']}件")
        print(f"実行時間: {result.statistics['elapsed_time']:.1f}秒")
        
        # 改善率
        if conflicts > 0:
            improvement = (conflicts - final_conflicts) / conflicts * 100
            print(f"\n改善率: {improvement:.1f}%")
        
        # 残存する問題の詳細
        if final_details:
            print("\n【残存する教師重複】")
            for i, detail in enumerate(final_details):
                print(f"{i+1}. {detail['time_slot']} - {detail['teacher']}先生")
                print(f"   クラス: {', '.join(str(c) for c in detail['classes'])}")
        else:
            print("\n✓ 教師重複が完全に解消されました！")
        
        # 統計情報
        print("\n【生成統計】")
        print(f"- フェーズ2試行: {result.statistics['phase2_attempts']}回")
        print(f"- フェーズ3反復: {result.statistics['phase3_iterations']}回")
        print(f"- 脱出戦略実行: {result.statistics['escapes']}回")
        print(f"- ランダムリスタート: {result.statistics['restarts']}回")
        
        # 学習情報
        print("\n【学習データ】")
        print(f"- 学習済みパターン: {result.learning_data['patterns_learned']}個")
        print(f"- 教師の好み記録: {result.learning_data['teacher_preferences']}人分")
        
        # 時間割を保存
        if final_conflicts < conflicts:
            output_path = path_config.output_dir / "output_phase4_hybrid.csv"
            schedule_repo.save_schedule(result.schedule, str(output_path))
            print(f"\n生成された時間割を保存: {output_path}")
            
    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()