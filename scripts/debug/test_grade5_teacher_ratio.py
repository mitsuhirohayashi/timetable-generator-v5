#!/usr/bin/env python3
"""5組の教師選択比率をテストするスクリプト"""

import sys
from pathlib import Path

# プロジェクトのルートディレクトリをsys.pathに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.domain.services.grade5_teacher_selector import Grade5TeacherSelector
from src.domain.value_objects.time_slot import Teacher, Subject, ClassReference
from src.infrastructure.repositories.csv_repository import CSVSchoolRepository
from src.infrastructure.config.path_config import PathConfig


def main():
    """教師選択比率のテスト"""
    print("=== 5組教師選択比率テスト ===\n")
    
    # CSVSchoolRepositoryで学校データを読み込み
    path_config = PathConfig()
    csv_repo = CSVSchoolRepository(str(path_config.data_dir))
    school = csv_repo.load_school_data()
    
    # 教師選択サービスのインスタンス作成
    selector = Grade5TeacherSelector()
    
    # テスト用のクラスと科目
    class_ref = ClassReference(1, 5)  # 1年5組
    subject_kokugo = Subject("国")
    
    print("国語の教師選択をシミュレーション（100回）")
    print("-" * 50)
    
    # 100回選択をシミュレート
    for i in range(100):
        teacher = selector.select_teacher(school, subject_kokugo, class_ref)
        if teacher:
            if (i + 1) % 10 == 0:
                print(f"{i + 1}回目: {teacher.name}先生を選択")
    
    # 選択結果のレポートを表示
    print("\n" + "=" * 50)
    report = selector.get_selection_report()
    
    if "国" in report["summary"]:
        print("\n国語の教師選択結果:")
        kokugo_summary = report["summary"]["国"]
        print(f"総選択回数: {kokugo_summary['total_selections']}")
        
        print("\n教師別の選択状況:")
        for teacher_name, stats in kokugo_summary["teacher_ratios"].items():
            print(f"  {teacher_name}先生: {stats['count']}回 ({stats['ratio']:.1%})")
        
        # 理想的な比率との差を計算
        print("\n理想比率（50:50）との差:")
        for teacher_name, stats in kokugo_summary["teacher_ratios"].items():
            diff = abs(stats['ratio'] - 0.5) * 100
            print(f"  {teacher_name}先生: {diff:.1f}%ポイント")
    
    # 他の科目もテスト（比率設定なし）
    print("\n" + "=" * 50)
    print("\n数学の教師選択をシミュレーション（20回）")
    print("-" * 50)
    
    subject_math = Subject("数")
    selector.reset_history()
    
    for i in range(20):
        teacher = selector.select_teacher(school, subject_math, class_ref)
        if teacher:
            if (i + 1) % 5 == 0:
                print(f"{i + 1}回目: {teacher.name}先生を選択")
    
    # 数学の結果も表示
    report = selector.get_selection_report()
    if "数" in report["summary"]:
        print("\n数学の教師選択結果:")
        math_summary = report["summary"]["数"]
        print(f"総選択回数: {math_summary['total_selections']}")
        
        print("\n教師別の選択状況:")
        for teacher_name, stats in math_summary["teacher_ratios"].items():
            print(f"  {teacher_name}先生: {stats['count']}回 ({stats['ratio']:.1%})")


if __name__ == "__main__":
    main()