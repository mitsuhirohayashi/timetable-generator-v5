#!/usr/bin/env python3
"""改善版時間割生成器のテスト

5組優先配置と教師スケジュール管理を統合した新しい生成器をテストします。
"""
import os
import sys
import logging
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.domain.services.implementations.improved_csp_generator import ImprovedCSPGenerator
from src.domain.services.unified_constraint_system import UnifiedConstraintSystem
from src.domain.services.smart_empty_slot_filler import SmartEmptySlotFiller
from src.application.services.constraint_registration_service import ConstraintRegistrationService
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader


def setup_logging(verbose: bool = True):
    """ロギングの設定"""
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # 特定のモジュールのログレベルを調整
    logging.getLogger('src.infrastructure').setLevel(logging.WARNING)
    logging.getLogger('src.domain.constraints').setLevel(logging.WARNING)


def main():
    """メイン処理"""
    print("\n" + "="*60)
    print("改善版時間割生成器のテスト")
    print("="*60)
    
    # ロギング設定
    setup_logging(verbose=True)
    
    # 既存のシステムと同じ方法でデータを読み込む
    print("\n1. データ読み込み中...")
    from src.application.use_cases.data_loading_use_case import DataLoadingUseCase
    from src.infrastructure.config.path_config import path_config
    
    # データローディング
    data_loader = DataLoadingUseCase()
    school, initial_schedule, teacher_absences = data_loader.load_all_data()
    
    # リポジトリとローダーの初期化（保存用）
    repository = CSVScheduleRepository()
    absence_loader = TeacherAbsenceLoader()
    
    # 制約システムの初期化
    print("\n2. 制約システムを初期化中...")
    constraint_system = UnifiedConstraintSystem()
    registration_service = ConstraintRegistrationService(constraint_system)
    registration_service.register_all_constraints(school, absence_loader)
    
    # 改善版生成器の初期化と実行
    print("\n3. 改善版CSP生成器で時間割を生成中...")
    generator = ImprovedCSPGenerator()
    schedule = generator.generate(school, initial_schedule)
    
    # 空きスロット埋め
    print("\n4. 空きスロットを埋めています...")
    filler = SmartEmptySlotFiller(
        constraint_validator=generator.constraint_validator,
        use_enhanced_features=True
    )
    empty_before = filler.count_empty_slots(schedule, school)
    filled_count = filler.fill_empty_slots(schedule, school)
    empty_after = filler.count_empty_slots(schedule, school)
    
    print(f"空きスロット: {empty_before} → {empty_after} (埋めた数: {filled_count})")
    
    # 結果の保存
    print("\n5. 結果を保存中...")
    output_path = repository.save_schedule(
        schedule,
        "output_improved.csv",
        use_support_hours=False
    )
    print(f"時間割を保存しました: {output_path}")
    
    # 制約違反のチェック
    print("\n6. 制約違反をチェック中...")
    violations = constraint_system.validate_all(schedule, school)
    
    if violations:
        print(f"\n⚠️  {len(violations)}件の制約違反が見つかりました:")
        
        # 違反をタイプ別に集計
        violation_types = {}
        for v in violations:
            constraint_name = v.constraint_name if hasattr(v, 'constraint_name') else 'Unknown'
            if constraint_name not in violation_types:
                violation_types[constraint_name] = []
            violation_types[constraint_name].append(v)
        
        # タイプ別に表示
        for constraint_name, vlist in violation_types.items():
            print(f"\n【{constraint_name}】({len(vlist)}件)")
            for v in vlist[:3]:  # 各タイプ最大3件まで表示
                if hasattr(v, 'description'):
                    print(f"  - {v.description}")
                else:
                    print(f"  - {v}")
    else:
        print("\n✅ 制約違反はありません！")
    
    # 生成統計の表示
    print("\n7. 生成統計:")
    if hasattr(generator, 'stats'):
        stats = generator.stats
        total = stats.get('total_slots', 1)
        filled = stats.get('filled_slots', 0)
        fill_rate = filled / total * 100 if total > 0 else 0
        
        print(f"  - 総スロット数: {total}")
        print(f"  - 埋められたスロット: {filled} ({fill_rate:.1f}%)")
        print(f"  - Phase 1 (5組): {stats.get('phase1_filled', 0)}")
        print(f"  - Phase 2 (交流学級): {stats.get('phase2_filled', 0)}")
        print(f"  - Phase 3 (通常クラス): {stats.get('phase3_filled', 0)}")
        print(f"  - 解決された競合: {stats.get('conflicts_resolved', 0)}")
    
    # 教師統計の表示
    if hasattr(generator, 'teacher_tracker'):
        teacher_stats = generator.teacher_tracker.get_statistics()
        print("\n8. 教師配置統計:")
        print(f"  - 総割り当て数: {teacher_stats.get('total_assignments', 0)}")
        print(f"  - 5組合同授業: {teacher_stats.get('grade5_joint_classes', 0)}")
        print(f"  - 防止された重複: {teacher_stats.get('conflicts_prevented', 0)}")
        print(f"  - 防止されたルール違反: {teacher_stats.get('rule_violations_prevented', 0)}")
        
        if 'top_loaded_teachers' in teacher_stats:
            print("\n  負荷の高い教師（上位5名）:")
            for teacher_info in teacher_stats['top_loaded_teachers'][:5]:
                print(f"    - {teacher_info['name']}: {teacher_info['total_classes']}コマ")
    
    print("\n" + "="*60)
    print("テスト完了")
    print("="*60)
    
    # 元の出力との比較
    print("\n9. 既存の出力との比較:")
    try:
        import subprocess
        result = subprocess.run(
            ["python3", "scripts/analysis/diagnose_issues_simple.py"],
            capture_output=True,
            text=True,
            cwd=project_root
        )
        
        if "5組同期違反:" in result.stdout:
            # 結果から数値を抽出
            lines = result.stdout.split('\n')
            for line in lines:
                if "5組同期違反:" in line:
                    print(f"  既存: {line.strip()}")
                elif "教師重複:" in line:
                    print(f"  既存: {line.strip()}")
        
        # 改善版の診断も実行
        print("\n  改善版の結果を確認中...")
        # output.csvを一時的にバックアップ
        os.rename("data/output/output.csv", "data/output/output_backup_temp.csv")
        os.rename("data/output/output_improved.csv", "data/output/output.csv")
        
        result2 = subprocess.run(
            ["python3", "scripts/analysis/diagnose_issues_simple.py"],
            capture_output=True,
            text=True,
            cwd=project_root
        )
        
        # 復元
        os.rename("data/output/output.csv", "data/output/output_improved.csv")
        os.rename("data/output/output_backup_temp.csv", "data/output/output.csv")
        
        if "5組同期違反:" in result2.stdout:
            lines = result2.stdout.split('\n')
            for line in lines:
                if "5組同期違反:" in line:
                    print(f"  改善版: {line.strip()}")
                elif "教師重複:" in line:
                    print(f"  改善版: {line.strip()}")
    
    except Exception as e:
        print(f"  比較中にエラーが発生: {e}")


if __name__ == "__main__":
    main()