#!/usr/bin/env python3
"""5組優先配置アルゴリズムの簡易テスト"""

import logging
from src.domain.entities.school import School
from src.domain.entities.schedule import Schedule
from src.domain.services.unified_constraint_system import UnifiedConstraintSystem
from src.domain.services.implementations.improved_csp_generator import ImprovedCSPGenerator
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository

# ログ設定
logging.basicConfig(level=logging.INFO)

def main():
    print("=== 5組優先配置アルゴリズム 簡易テスト ===\n")
    
    try:
        # 必要なオブジェクトを初期化
        schedule_repo = CSVScheduleRepository()
        school_repo = CSVSchoolRepository()
        
        # データ読み込み
        print("データ読み込み中...")
        school = school_repo.load_school_data("data/config/base_timetable.csv")
        initial_schedule = schedule_repo.load("data/input/input.csv", school)
        
        # 制約システム初期化
        constraint_system = UnifiedConstraintSystem()
        
        # 生成器を作成
        print("\n5組優先配置生成器を初期化...")
        generator = ImprovedCSPGenerator(constraint_system)
        
        # 生成実行（followup_constraintsなしで）
        print("時間割生成中...")
        schedule = generator.generate(
            school=school,
            initial_schedule=initial_schedule,
            followup_constraints=None  # Follow-upなしでテスト
        )
        
        print("\n✅ 生成完了！")
        
        # 統計情報を表示
        print(f"\n統計情報:")
        print(f"  Phase 1 (5組): {generator.stats['phase1_placed']}個配置")
        print(f"  Phase 2 (交流学級): {generator.stats['phase2_placed']}個配置")
        print(f"  Phase 3 (通常クラス): {generator.stats['phase3_placed']}個配置")
        print(f"  競合解決: {generator.stats['conflicts_resolved']}個")
        print(f"  バックトラック: {generator.stats['backtracks']}回")
        
        # 簡易違反チェック
        print("\n=== 簡易違反チェック ===")
        validation_result = constraint_system.validate_schedule(schedule, school)
        
        if validation_result.is_valid:
            print("✅ 制約違反なし！")
        else:
            print(f"❌ {len(validation_result.violations)}件の制約違反")
            
            # 違反タイプ別に集計
            violation_types = {}
            for v in validation_result.violations:
                vtype = v.constraint_type
                if vtype not in violation_types:
                    violation_types[vtype] = 0
                violation_types[vtype] += 1
            
            for vtype, count in violation_types.items():
                print(f"  - {vtype}: {count}件")
        
        # 出力保存
        print("\n結果を保存中...")
        schedule_repo.save_schedule(schedule, "data/output/output_grade5_priority_simple.csv")
        print("✅ 保存完了: data/output/output_grade5_priority_simple.csv")
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()