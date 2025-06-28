#!/usr/bin/env python3
"""
Grade 5 Test Exclusion統合テスト

実際のスケジュール生成でGrade 5 Test Exclusion Constraintが
正しく動作することを確認
"""
import sys
from pathlib import Path
import logging

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent))

from src.application.services.schedule_generation_service import ScheduleGenerationService
from src.application.services.data_loading_service import DataLoadingService
from src.application.services.constraint_registration_service import ConstraintRegistrationService
from src.domain.services.unified_constraint_system import UnifiedConstraintSystem
from src.infrastructure.config.path_manager import get_path_manager

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_grade5_test_exclusion(schedule, data_dir):
    """5組のテスト期間中の科目配置をチェック"""
    logger.info("\n=== 5組のテスト期間配置をチェック ===")
    
    # Follow-up.csvからテスト期間を読み取る
    data_loading = DataLoadingService()
    weekly_req, _ = data_loading.load_weekly_requirements(data_dir, None, schedule)
    test_periods = weekly_req.get('test_periods', [])
    
    violations = []
    
    for test_period in test_periods:
        if hasattr(test_period, 'day') and hasattr(test_period, 'periods'):
            day = test_period.day
            for period in test_period.periods:
                logger.info(f"\n{day}曜{period}限（テスト期間）:")
                
                # 通常クラスのテスト科目を収集
                test_subjects_by_grade = {}
                for grade in range(1, 4):
                    for class_num in range(1, 8):
                        if class_num == 5:  # 5組はスキップ
                            continue
                        
                        class_ref = f"{grade}-{class_num}"
                        from src.domain.value_objects.time_slot import TimeSlot, ClassReference
                        time_slot = TimeSlot(day, period)
                        cr = ClassReference(grade, class_num)
                        assignment = schedule.get_assignment(time_slot, cr)
                        
                        if assignment and assignment.subject.name != "欠":
                            if grade not in test_subjects_by_grade:
                                test_subjects_by_grade[grade] = set()
                            test_subjects_by_grade[grade].add(assignment.subject.name)
                
                # 5組の科目をチェック
                for grade in range(1, 4):
                    class_ref = f"{grade}-5"
                    cr = ClassReference(grade, 5)
                    assignment = schedule.get_assignment(TimeSlot(day, period), cr)
                    
                    if assignment and assignment.subject.name != "欠":
                        subject = assignment.subject.name
                        logger.info(f"  {class_ref}: {subject}", end="")
                        
                        # 同学年の通常クラスがテストを受けている科目と比較
                        if grade in test_subjects_by_grade:
                            test_subjects = test_subjects_by_grade[grade]
                            if subject in test_subjects:
                                logger.info(" ❌ 違反（同学年がテスト中）")
                                violations.append({
                                    'class': class_ref,
                                    'day': day,
                                    'period': period,
                                    'subject': subject,
                                    'conflict': f"同学年が{subject}のテスト中"
                                })
                            else:
                                logger.info(" ✓ OK")
                                logger.info(f"    （同学年のテスト科目: {', '.join(test_subjects)}）")
                        else:
                            logger.info(" ✓ OK（同学年にテストなし）")
    
    return violations

def test_integration():
    """統合テスト実行"""
    logger.info("=== Grade 5 Test Exclusion統合テスト開始 ===")
    
    # パス設定
    path_manager = get_path_manager()
    data_dir = path_manager.data_dir
    
    # サービスの初期化
    data_loading = DataLoadingService()
    constraint_service = ConstraintRegistrationService()
    
    # 学校データの読み込み
    logger.info("\n学校データを読み込み中...")
    school, use_enhanced = data_loading.load_school_data(data_dir)
    
    # 初期スケジュールの読み込み
    logger.info("初期スケジュールを読み込み中...")
    initial_schedule = data_loading.load_initial_schedule(
        data_dir, "input.csv", start_empty=False, validate=False
    )
    
    # 週次要望の読み込み
    logger.info("週次要望を読み込み中...")
    weekly_req, teacher_absences = data_loading.load_weekly_requirements(
        data_dir, school, initial_schedule
    )
    
    # 制約システムの初期化
    logger.info("制約システムを初期化中...")
    constraint_system = UnifiedConstraintSystem()
    constraint_service.register_all_constraints(
        constraint_system, data_dir, teacher_absences
    )
    
    # ScheduleGenerationServiceを初期化
    generation_service = ScheduleGenerationService(constraint_system, path_manager)
    
    # スケジュール生成
    logger.info("\nスケジュールを生成中...")
    schedule = generation_service.generate_schedule(
        school=school,
        initial_schedule=initial_schedule,
        max_iterations=100,
        use_advanced_csp=True
    )
    
    if result.success:
        logger.info(f"✓ スケジュール生成成功（{result.generation_time:.1f}秒）")
        
        # 5組のテスト期間配置をチェック
        violations = check_grade5_test_exclusion(result.schedule, data_dir)
        
        if violations:
            logger.error(f"\n❌ {len(violations)}件の5組テスト期間違反が見つかりました:")
            for v in violations:
                logger.error(f"  - {v['class']} {v['day']}曜{v['period']}限: "
                           f"{v['subject']} ({v['conflict']})")
            return False
        else:
            logger.info("\n✅ 5組のテスト期間配置は全て適切です")
            
            # CSVに出力して確認
            from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
            output_path = data_dir / "output" / "test_grade5_exclusion.csv"
            repo = CSVScheduleRepository(str(data_dir))
            repo.save(result.schedule, str(output_path))
            logger.info(f"\nスケジュールを保存しました: {output_path}")
            
            return True
    else:
        logger.error(f"❌ スケジュール生成失敗: {result.error_message}")
        return False

if __name__ == "__main__":
    try:
        success = test_integration()
        if success:
            logger.info("\n🎉 Grade 5 Test Exclusion Constraintは完全に実装されています！")
            logger.info("5組はテスト期間中、通常クラスのテスト科目を受けません。")
        else:
            logger.error("\n統合テストに失敗しました")
            sys.exit(1)
    except Exception as e:
        logger.error(f"\n統合テスト中にエラーが発生しました: {e}", exc_info=True)
        sys.exit(1)