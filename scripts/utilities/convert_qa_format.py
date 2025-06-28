"""
既存のQA.txtを新しいフォーマットに変換するスクリプト
"""

import sys
import re
from pathlib import Path
from datetime import datetime

# プロジェクトのルートディレクトリをPythonパスに追加
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.application.services.qanda_service_improved import (
    ImprovedQandAService, QuestionStatus, QuestionPriority
)


def parse_existing_qa(file_path: Path) -> dict:
    """既存のQA.txtを解析"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 各セクションのパターン
    sections = {
        'new_questions': [],
        'teacher_placement': [],
        'exchange_class': [],
        'test_period': [],
        'fixed_subjects': [],
        'facility_usage': [],
        'homeroom_teacher': [],
        'meetings': [],
        'subject_placement': [],
        'others': []
    }
    
    # セクションマッピング
    section_mapping = {
        '教師配置に関する質問': 'teacher_placement',
        '交流学級（支援学級）に関する質問': 'exchange_class',
        'テスト期間に関する質問': 'test_period',
        '固定科目に関する質問': 'fixed_subjects',
        '施設使用に関する質問': 'facility_usage',
        '担任教師に関する質問': 'homeroom_teacher',
        '会議・教師不在に関する質問': 'meetings',
        '科目配置に関する質問': 'subject_placement',
        'その他の重要な質問': 'others'
    }
    
    # カテゴリマッピング
    category_mapping = {
        'teacher_placement': '教師配置',
        'exchange_class': '交流学級',
        'test_period': 'テスト期間',
        'fixed_subjects': '固定科目',
        'facility_usage': '施設使用',
        'homeroom_teacher': '担任教師',
        'meetings': '会議・不在',
        'subject_placement': '科目配置',
        'others': 'その他'
    }
    
    # QAパターン（改善版）
    # Q番号がある場合とない場合の両方に対応
    qa_patterns = [
        # Q1.1: 形式
        r'Q(\d+\.\d+):\s*([^\n]+)\s*\nA:\s*([^\n]+(?:\n(?!Q|##|\d+\.).*)*)',
        # Q: 形式（例の質問など）
        r'Q:\s*([^\n]+)\s*\nA:\s*([^\n]+(?:\n(?!Q|##).*)*)',
    ]
    
    # 新規質問パターン（タイムスタンプ付き）
    new_qa_pattern = r'\[([^\]]+)\]\s*\nQ:\s*([^\n]+)(?:\s*\n\s*Context:\s*([^\n]+))?\s*\nA:\s*([^\n]+)'
    
    # 例の質問を処理
    example_pattern = r'例:\s*\nQ:\s*([^\n]+)\s*\nA:\s*([^\n]+)'
    example_match = re.search(example_pattern, content, re.MULTILINE)
    if example_match:
        sections['new_questions'].append({
            'timestamp': None,
            'question': example_match.group(1).strip(),
            'context': None,
            'answer': example_match.group(2).strip(),
            'category': '教師配置'
        })
    
    # 通常のQAを抽出（各セクションを処理）
    current_section = None
    current_category = None
    
    # セクションごとに処理
    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # セクション見出しをチェック
        if line.startswith('##'):
            for section_name, section_key in section_mapping.items():
                if section_name in line:
                    current_section = section_key
                    current_category = category_mapping.get(section_key, 'その他')
                    break
        
        # Q&Aパターンをチェック
        if line.startswith('Q') and i + 1 < len(lines):
            # 複数行の回答を処理
            qa_text = ''
            j = i
            while j < len(lines) and not (lines[j].strip().startswith('Q') and j > i):
                qa_text += lines[j] + '\n'
                j += 1
                if j < len(lines) and (lines[j].strip().startswith('##') or 
                                      (lines[j].strip().startswith('Q') and 'A:' in qa_text)):
                    break
            
            # Q番号付きパターン
            match = re.match(r'Q(\d+\.\d+):\s*(.+)', line)
            if match:
                q_num = match.group(1)
                question = match.group(2).strip()
                
                # 回答を探す
                answer_match = re.search(r'A:\s*(.+?)(?=Q\d+\.\d+:|##|$)', qa_text, re.DOTALL)
                if answer_match:
                    answer = answer_match.group(1).strip()
                    if answer and answer != '[回答をここに追加]' and current_section:
                        sections[current_section].append({
                            'question': question,
                            'answer': answer,
                            'category': current_category or 'その他'
                        })
            
            i = j - 1
        
        i += 1
    
    return sections, category_mapping


def convert_to_new_format(existing_qa_path: Path, new_qa_path: Path):
    """既存のQA.txtを新しいフォーマットに変換"""
    print("🔄 QA.txt変換を開始します...")
    
    # 既存のQAを解析
    sections, category_mapping = parse_existing_qa(existing_qa_path)
    
    # 新しいサービスを初期化
    service = ImprovedQandAService(
        qa_file_path=str(new_qa_path),
        metadata_path=str(new_qa_path.parent / "qa_metadata.json")
    )
    
    # 統計情報
    stats = {
        'unanswered': 0,
        'resolved': 0,
        'permanent': 0,
        'total': 0
    }
    
    # 新規質問を処理
    print("\n📝 新規質問を処理中...")
    for qa in sections['new_questions']:
        if qa['answer']:
            # 回答済み
            q_id = service.add_question(
                question=qa['question'],
                priority=QuestionPriority.MEDIUM,
                category=qa['category'],
                context=qa['context']
            )
            service.answer_question(q_id, qa['answer'])
            stats['resolved'] += 1
        else:
            # 未回答
            service.add_question(
                question=qa['question'],
                priority=QuestionPriority.HIGH,
                category=qa['category'],
                context=qa['context']
            )
            stats['unanswered'] += 1
        stats['total'] += 1
    
    # 既存のQAセクションを処理
    print("\n📚 既存のQ&Aセクションを処理中...")
    
    # 重要な質問を恒久的ルールとして扱う
    permanent_sections = ['fixed_subjects', 'homeroom_teacher', 'test_period']
    
    for section_key, qa_list in sections.items():
        if section_key == 'new_questions':
            continue
        
        category = category_mapping.get(section_key, 'その他')
        print(f"  - {category}: {len(qa_list)} 件")
        
        for qa in qa_list:
            q_id = service.add_question(
                question=qa['question'],
                priority=QuestionPriority.MEDIUM,
                category=category
            )
            
            if qa['answer']:
                service.answer_question(q_id, qa['answer'])
                
                # 重要なセクションの質問は恒久的ルールに昇格
                if section_key in permanent_sections:
                    service.promote_to_permanent(q_id)
                    stats['permanent'] += 1
                else:
                    stats['resolved'] += 1
            else:
                stats['unanswered'] += 1
            
            stats['total'] += 1
    
    print("\n✅ 変換が完了しました！")
    print(f"\n📊 統計情報:")
    print(f"  - 総質問数: {stats['total']}")
    print(f"  - 未回答: {stats['unanswered']}")
    print(f"  - 解決済み: {stats['resolved']}")
    print(f"  - 恒久ルール: {stats['permanent']}")
    
    return service


def main():
    """メイン処理"""
    # パスの設定
    existing_qa = Path("QandA/QA.txt")
    new_qa = Path("QandA/QA_new.txt")
    
    if not existing_qa.exists():
        print(f"❌ エラー: {existing_qa} が見つかりません")
        return
    
    # バックアップを作成
    backup_path = existing_qa.parent / f"QA_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    print(f"📦 バックアップを作成: {backup_path}")
    backup_path.write_text(existing_qa.read_text(encoding='utf-8'), encoding='utf-8')
    
    # 変換を実行
    service = convert_to_new_format(existing_qa, new_qa)
    
    # 古い質問をアーカイブ（30日以上経過した解決済み質問）
    archived_count = service.archive_old_questions(days=30)
    if archived_count > 0:
        print(f"\n📦 {archived_count} 件の古い質問をアーカイブしました")
    
    print(f"\n✨ 新しいQA.txtは {new_qa} に保存されました")
    print("📝 既存のQA.txtを置き換える場合は以下のコマンドを実行してください:")
    print(f"   mv {new_qa} {existing_qa}")


if __name__ == "__main__":
    main()