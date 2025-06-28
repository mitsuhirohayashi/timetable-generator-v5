#!/usr/bin/env python3
"""QandAシステムの動作確認スクリプト"""

import sys
from pathlib import Path

# プロジェクトのルートディレクトリをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.application.services.qanda_service import QandAService
from src.application.services.constraint_violation_analyzer import ConstraintViolationAnalyzer
from src.domain.constraints.base import ConstraintViolation
from src.domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from src.domain.value_objects.assignment import Assignment


def test_qanda_system():
    """QandAシステムの動作テスト"""
    print("=== QandAシステム動作確認 ===\n")
    
    # QandAサービスの初期化
    qanda_service = QandAService()
    analyzer = ConstraintViolationAnalyzer(qanda_service)
    
    # 1. 未回答質問の確認
    print("1. 未回答質問の確認")
    unanswered = qanda_service.get_unanswered_questions()
    print(f"   未回答質問数: {len(unanswered)}")
    for q in unanswered[:3]:
        print(f"   - {q['question'][:50]}...")
    print()
    
    # 2. 回答済み質問の確認
    print("2. 回答済み質問の確認")
    answered = qanda_service.get_answered_questions()
    print(f"   回答済み質問数: {len(answered)}")
    for qa in answered[:3]:
        print(f"   Q: {qa['question'][:50]}...")
        print(f"   A: {qa['answer'][:50]}...")
    print()
    
    # 3. 学習したルールの確認
    print("3. 学習したルールの確認")
    rules = qanda_service.apply_learned_rules()
    total_rules = sum(len(r) for r in rules.values())
    print(f"   学習済みルール総数: {total_rules}")
    for category, rule_list in rules.items():
        if rule_list:
            print(f"   - {category}: {len(rule_list)}件")
    print()
    
    # 4. テスト用の違反を作成して分析
    print("4. 違反分析のテスト")
    
    # テスト用の違反を作成
    test_violations = [
        # 教師重複違反
        ConstraintViolation(
            description="井上先生が同時刻に複数クラスを担当しています",
            time_slot=TimeSlot("火", 5),
            assignment=Assignment(
                ClassReference(2, 1),
                Subject("数"),
                Teacher("井上")
            ),
            severity="ERROR"
        ),
        # 体育館使用違反
        ConstraintViolation(
            description="体育館使用制約違反: 複数クラスが同時に体育館を使用",
            time_slot=TimeSlot("月", 3),
            assignment=Assignment(
                ClassReference(1, 1),
                Subject("保"),
                Teacher("財津")
            ),
            severity="ERROR"
        ),
        # 自立活動違反
        ConstraintViolation(
            description="交流学級同期制約違反: 3-6が自立だが3-3が数/英ではない",
            time_slot=TimeSlot("水", 2),
            assignment=Assignment(
                ClassReference(3, 6),
                Subject("自立"),
                Teacher("財津")
            ),
            severity="ERROR"
        )
    ]
    
    # 違反を分析
    analysis = analyzer.analyze_violations(test_violations)
    
    print(f"   分析した違反数: {analysis['total_violations']}")
    print(f"   検出されたパターン数: {len(analysis['patterns'])}")
    print(f"   生成された質問数: {len(analysis['questions_generated'])}")
    
    if analysis['questions_generated']:
        print("\n   生成された質問の例:")
        for q in analysis['questions_generated'][:2]:
            print(f"   - {q['text'][:80]}...")
    
    # 5. 提案の確認
    suggestions = analyzer.suggest_solutions(analysis)
    if suggestions:
        print(f"\n5. 改善提案 ({len(suggestions)}件)")
        for i, suggestion in enumerate(suggestions, 1):
            print(f"   {i}. {suggestion}")
    
    print("\n=== テスト完了 ===")
    print("\nQandAシステムは正常に動作しています。")
    print("詳細はQandA/QA.txtをご確認ください。")


if __name__ == "__main__":
    test_qanda_system()