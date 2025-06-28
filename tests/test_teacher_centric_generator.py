#!/usr/bin/env python3
"""
教師中心時間割生成器のテスト

フェーズ2の実装をテストし、教師重複が解消されることを確認します。
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.domain.services.ultrathink.teacher_centric_generator import TeacherCentricGenerator
from src.application.services.data_loading_service import DataLoadingService
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.config.path_config import path_config
from src.domain.services.constraint_validator import ConstraintValidator
from src.domain.services.exchange_class_synchronizer import ExchangeClassSynchronizer
from src.domain.services.grade5_synchronizer_refactored import RefactoredGrade5Synchronizer
from collections import defaultdict
import logging

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def analyze_teacher_duplications(schedule, school):
    """教師重複を分析"""
    
    days = ["月", "火", "水", "木", "金"]
    periods = [1, 2, 3, 4, 5, 6]
    
    duplications = []
    total_slots = 0
    
    # テスト期間を除外
    test_periods = {
        ("月", 1), ("月", 2), ("月", 3),
        ("火", 1), ("火", 2), ("火", 3),
        ("水", 1), ("水", 2)
    }
    
    # 固定科目の教師を除外
    fixed_teachers = {"欠", "YT担当", "道担当", "学担当", "総担当", "学総担当", "行担当"}
    
    for day in days:
        for period in periods:
            total_slots += 1
            
            # テスト期間はスキップ
            if (day, period) in test_periods:
                continue
            
            # 教師ごとにクラスを収集
            teacher_classes = defaultdict(list)
            
            from src.domain.value_objects.time_slot import TimeSlot
            time_slot = TimeSlot(day, period)
            
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.teacher:
                    teacher_name = assignment.teacher.name
                    
                    # 固定科目の教師はスキップ
                    if teacher_name in fixed_teachers:
                        continue
                    
                    teacher_classes[teacher_name].append({
                        'class': class_ref,
                        'subject': assignment.subject.name
                    })
            
            # 重複をチェック
            for teacher_name, classes in teacher_classes.items():
                if len(classes) > 1:
                    # 5組のみの場合は正常
                    from src.domain.value_objects.time_slot import ClassReference
                    grade5_refs = {ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)}
                    
                    all_grade5 = all(c['class'] in grade5_refs for c in classes)
                    
                    if not all_grade5:
                        duplications.append({
                            'day': day,
                            'period': period,
                            'teacher': teacher_name,
                            'classes': classes
                        })
    
    return duplications, total_slots

def main():
    print("=== 教師中心時間割生成器のテスト ===\n")
    
    # データ読み込み
    data_loading_service = DataLoadingService()
    school, _ = data_loading_service.load_school_data(path_config.data_dir)
    
    # 初期スケジュールの読み込み（固定授業）
    schedule_repo = CSVScheduleRepository(path_config.data_dir)
    initial_schedule = schedule_repo.load("input/input.csv", school)
    
    print(f"学校データ: {len(school.get_all_classes())}クラス, {len(school.get_all_teachers())}教師")
    print(f"初期スケジュール: {len(initial_schedule.get_all_assignments())}個の固定授業\n")
    
    # サービスの初期化
    constraint_validator = ConstraintValidator()
    exchange_synchronizer = ExchangeClassSynchronizer()
    grade5_synchronizer = RefactoredGrade5Synchronizer()
    
    # 教師中心生成器の作成
    generator = TeacherCentricGenerator(
        constraint_validator=constraint_validator,
        exchange_synchronizer=exchange_synchronizer,
        grade5_synchronizer=grade5_synchronizer,
        enable_logging=True
    )
    
    # 時間割生成
    print("教師中心アプローチで時間割を生成中...\n")
    
    try:
        generated_schedule = generator.generate(
            school=school,
            initial_schedule=initial_schedule,
            seed=42  # 再現性のため
        )
        
        print("\n生成完了！")
        
        # 結果の分析
        print("\n【生成結果の分析】")
        print("-" * 60)
        
        # 配置数
        total_assignments = len(generated_schedule.get_all_assignments())
        print(f"総配置数: {total_assignments}個")
        
        # 教師重複の分析
        duplications, total_slots = analyze_teacher_duplications(generated_schedule, school)
        
        print(f"\n教師重複分析:")
        print(f"  総時間枠: {total_slots}個")
        print(f"  教師重複: {len(duplications)}件")
        
        if duplications:
            print("\n重複の詳細（最初の5件）:")
            for i, dup in enumerate(duplications[:5]):
                print(f"\n{i+1}. {dup['day']}曜{dup['period']}限 - {dup['teacher']}先生:")
                for class_info in dup['classes']:
                    print(f"   - {class_info['class']}: {class_info['subject']}")
        else:
            print("\n★ 教師重複は完全に解消されました！")
        
        # 制約違反の分析
        violations = constraint_validator.validate_all_constraints(generated_schedule, school)
        
        print(f"\n制約違反分析:")
        violation_types = defaultdict(int)
        for v in violations:
            violation_types[v.get('type', 'unknown')] += 1
        
        if violation_types:
            for vtype, count in sorted(violation_types.items()):
                print(f"  {vtype}: {count}件")
        else:
            print("  制約違反なし")
        
        # 時間割を保存
        output_path = path_config.output_dir / "output_teacher_centric.csv"
        schedule_repo.save_schedule(generated_schedule, str(output_path))
        print(f"\n生成した時間割を保存: {output_path}")
        
        # フェーズ1との比較
        print("\n【フェーズ1との比較】")
        print("-" * 60)
        print("フェーズ1（即座修正）: 10件の真の教師重複")
        print(f"フェーズ2（教師中心）: {len(duplications)}件の教師重複")
        
        improvement = (10 - len(duplications)) / 10 * 100 if duplications else 100
        print(f"\n改善率: {improvement:.1f}%")
        
    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()