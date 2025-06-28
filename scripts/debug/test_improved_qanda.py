"""
改善されたQandAServiceのテストと使用例
"""

import sys
from pathlib import Path

# プロジェクトのルートディレクトリをPythonパスに追加
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.application.services.qanda_service_improved import (
    ImprovedQandAService, QuestionStatus, QuestionPriority
)


def test_improved_qanda_service():
    """改善されたQandAServiceのテスト"""
    print("🧪 改善されたQandAServiceのテストを開始します\n")
    
    # テスト用の新しいQAファイルパス
    test_qa_path = "QandA/QA_test.txt"
    test_metadata_path = "QandA/qa_metadata_test.json"
    
    # サービスを初期化
    service = ImprovedQandAService(
        qa_file_path=test_qa_path,
        metadata_path=test_metadata_path
    )
    
    print("1️⃣ 新しい質問を追加")
    print("-" * 50)
    
    # 高優先度の質問を追加
    q1_id = service.add_question(
        question="井上先生が火曜5限に2-1と2-2で同時に数学を教えることができません。どうすればよいですか？",
        priority=QuestionPriority.CRITICAL,
        category="教師配置",
        context="制約違反: TeacherConflictConstraint",
        tags=["teacher_conflict", "urgent"]
    )
    print(f"✅ 質問を追加しました: {q1_id}")
    
    # 中優先度の質問を追加
    q2_id = service.add_question(
        question="3-6の自立活動は3-3が数学または英語の時のみ可能ですが、現在の配置で問題ありませんか？",
        priority=QuestionPriority.MEDIUM,
        category="交流学級",
        context="自立活動の配置確認"
    )
    print(f"✅ 質問を追加しました: {q2_id}")
    
    # 低優先度の質問を追加
    q3_id = service.add_question(
        question="音楽室の使用制限を追加すべきでしょうか？",
        priority=QuestionPriority.LOW,
        category="施設使用"
    )
    print(f"✅ 質問を追加しました: {q3_id}")
    
    print("\n2️⃣ 統計情報を表示")
    print("-" * 50)
    stats = service.get_statistics()
    print(f"総質問数: {stats['total']}")
    print(f"未回答: {stats['unanswered']}")
    print(f"解決済み: {stats['resolved']}")
    print(f"恒久ルール: {stats['permanent']}")
    print(f"アーカイブ: {stats['archived']}")
    
    print("\n3️⃣ 質問に回答")
    print("-" * 50)
    service.answer_question(
        q1_id,
        "火曜5限の2-1か2-2のどちらかの数学を別の時間に移動させてください。井上先生は同時に2クラスを教えることはできません。"
    )
    print(f"✅ 質問 {q1_id} に回答しました")
    
    service.answer_question(
        q2_id,
        "はい、3-6の自立活動は3-3が数学または英語の時のみ配置可能です。テスト期間中の数学・英語は除きます。"
    )
    print(f"✅ 質問 {q2_id} に回答しました")
    
    print("\n4️⃣ 質問を恒久的ルールに昇格")
    print("-" * 50)
    service.promote_to_permanent(q2_id)
    print(f"✅ 質問 {q2_id} を恒久的ルールに昇格しました")
    
    print("\n5️⃣ エラーから自動質問生成")
    print("-" * 50)
    error_q_id = service.generate_question_from_error(
        error_type="teacher_conflict",
        error_details={
            'teacher': '野口先生',
            'time_slot': '水曜3限',
            'classes': ['2-2', '2-5']
        },
        priority=QuestionPriority.HIGH
    )
    print(f"✅ エラーから質問を生成しました: {error_q_id}")
    
    print("\n6️⃣ キーワード検索")
    print("-" * 50)
    results = service.search_questions("数学")
    print(f"「数学」を含む質問: {len(results)} 件")
    for q in results:
        print(f"  - {q.id}: {q.question[:50]}...")
    
    print("\n7️⃣ カテゴリー別表示")
    print("-" * 50)
    teacher_questions = service.get_questions_by_category("教師配置")
    print(f"教師配置カテゴリーの質問: {len(teacher_questions)} 件")
    
    print("\n8️⃣ 最終的な統計")
    print("-" * 50)
    final_stats = service.get_statistics()
    print(f"総質問数: {final_stats['total']}")
    print(f"未回答: {final_stats['unanswered']}")
    print(f"解決済み: {final_stats['resolved']}")
    print(f"恒久ルール: {final_stats['permanent']}")
    
    if "by_category" in final_stats:
        print("\nカテゴリー別:")
        for cat, count in final_stats["by_category"].items():
            print(f"  - {cat}: {count} 件")
    
    print(f"\n✅ テストが完了しました！")
    print(f"📄 生成されたファイル:")
    print(f"  - {test_qa_path}")
    print(f"  - {test_metadata_path}")
    
    # クリーンアップのオプション
    print("\n🧹 テストファイルを削除しますか？ (y/n): ", end="")
    if input().lower() == 'y':
        Path(test_qa_path).unlink(missing_ok=True)
        Path(test_metadata_path).unlink(missing_ok=True)
        print("✅ テストファイルを削除しました")


def demonstrate_integration():
    """実際のシステムとの統合例"""
    print("\n\n🔗 システム統合の例")
    print("=" * 60)
    
    # 実際のQAファイルを使用
    service = ImprovedQandAService()
    
    print("制約違反が発生した場合の処理例:")
    print("-" * 50)
    
    # 制約違反の例
    violation_example = """
    # 時間割生成中に以下のような制約違反が発生した場合:
    
    try:
        # 時間割生成処理...
        pass
    except ConstraintViolation as e:
        # QandAServiceに質問を自動追加
        q_id = service.generate_question_from_error(
            error_type="constraint_violation",
            error_details={
                'constraint_name': e.constraint_name,
                'description': str(e)
            }
        )
        print(f"制約違反について質問を追加しました: {q_id}")
    """
    
    print(violation_example)
    
    print("\n未回答の質問を確認する例:")
    print("-" * 50)
    
    check_example = """
    # 時間割生成前に未回答の質問をチェック
    unanswered = service.get_questions_by_status(QuestionStatus.UNANSWERED)
    
    if unanswered:
        print(f"⚠️ {len(unanswered)} 件の未回答の質問があります:")
        for q in unanswered:
            print(f"  - [{q.priority.value}] {q.question}")
        
        print("\\n質問に回答してから時間割生成を続行することを推奨します。")
    """
    
    print(check_example)


if __name__ == "__main__":
    test_improved_qanda_service()
    demonstrate_integration()