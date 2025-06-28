"""
QandAサービス
システムが実行時に質問を生成し、ユーザーの回答を学習する機能を提供
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging


class QandAService:
    """QandAシステムを管理するサービス"""
    
    def __init__(self, qa_file_path: str = "QandA/QA.txt"):
        self.qa_file_path = Path(qa_file_path)
        self.logger = logging.getLogger(__name__)
        self._ensure_qa_file_exists()
        self.question_marker = "### システムからの質問（最新の質問が上に表示されます）"
        self.user_marker = "### ユーザーからの新しい要件・質問"
    
    def _ensure_qa_file_exists(self) -> None:
        """QA.txtファイルが存在することを確認"""
        if not self.qa_file_path.exists():
            self.qa_file_path.parent.mkdir(parents=True, exist_ok=True)
            self._create_initial_qa_file()
    
    def _create_initial_qa_file(self) -> None:
        """初期のQA.txtファイルを作成"""
        initial_content = """# 時間割生成システム - 質問と回答集 (QA.txt)

このファイルは、時間割生成システムの改善のために必要な情報を質問形式でまとめたものです。
システムが実行時に必要な情報を質問として追加し、人間が回答を記入することで、システムが賢くなっていきます。

---

## 【新規質問追加欄】 - システムが自動的に質問を追加します

### システムからの質問（最新の質問が上に表示されます）

[システムが実行時にエラーや不明な点があった場合、ここに自動的に質問を追加します]

### ユーザーからの新しい要件・質問

Q: [ユーザーが新しい要件や質問をここに追加できます]
A: [回答をここに追加]

---

"""
        with open(self.qa_file_path, 'w', encoding='utf-8') as f:
            f.write(initial_content)
    
    def add_system_question(self, question: str, context: Optional[str] = None) -> bool:
        """
        システムからの質問をQA.txtに追加
        
        Args:
            question: 質問内容
            context: 質問の背景情報（オプション）
            
        Returns:
            追加に成功した場合True
        """
        try:
            # 既存の内容を読み込む
            with open(self.qa_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 既に同じ質問が存在するかチェック
            if question in content:
                self.logger.info(f"質問は既に存在します: {question[:50]}...")
                return False
            
            # タイムスタンプを追加
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 質問フォーマット
            formatted_question = f"\n[{timestamp}]\nQ: {question}"
            if context:
                formatted_question += f"\n   Context: {context}"
            formatted_question += "\nA: [回答をここに追加]\n"
            
            # システムからの質問セクションを見つけて、その直後に追加
            marker_pos = content.find(self.question_marker)
            if marker_pos == -1:
                self.logger.error("QA.txtの形式が不正です")
                return False
            
            # マーカーの次の行に挿入
            lines = content.split('\n')
            insert_line = 0
            for i, line in enumerate(lines):
                if self.question_marker in line:
                    insert_line = i + 2  # マーカーの2行後（空行の後）
                    break
            
            # 質問を挿入
            lines.insert(insert_line, formatted_question)
            
            # ファイルに書き戻す
            with open(self.qa_file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            
            self.logger.info(f"新しい質問をQA.txtに追加しました: {question[:50]}...")
            return True
            
        except Exception as e:
            self.logger.error(f"質問の追加に失敗しました: {e}")
            return False
    
    def get_unanswered_questions(self) -> List[Dict[str, str]]:
        """
        回答されていない質問のリストを取得
        
        Returns:
            未回答の質問のリスト（各要素は{'question': str, 'timestamp': str}の辞書）
        """
        unanswered = []
        
        try:
            with open(self.qa_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 質問と回答のパターンを検索
            pattern = r'\[([0-9\-\s:]+)\]\s*\nQ:\s*([^\n]+)(?:\n\s*Context:\s*([^\n]+))?\s*\nA:\s*\[回答をここに追加\]'
            matches = re.finditer(pattern, content, re.MULTILINE)
            
            for match in matches:
                unanswered.append({
                    'timestamp': match.group(1),
                    'question': match.group(2),
                    'context': match.group(3) if match.group(3) else None
                })
            
        except Exception as e:
            self.logger.error(f"未回答質問の取得に失敗しました: {e}")
        
        return unanswered
    
    def get_answered_questions(self) -> List[Dict[str, str]]:
        """
        回答済みの質問と回答のペアを取得
        
        Returns:
            回答済みの質問のリスト（各要素は{'question': str, 'answer': str}の辞書）
        """
        answered = []
        
        try:
            with open(self.qa_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 全てのQ&Aペアを探す（既存の質問も含む）
            pattern = r'Q[:\d.]*\s*([^\n]+)\s*\nA:\s*([^\[\n][^\n]*)'
            matches = re.finditer(pattern, content, re.MULTILINE)
            
            for match in matches:
                answer = match.group(2).strip()
                if answer and answer != "[回答をここに追加]":
                    answered.append({
                        'question': match.group(1).strip(),
                        'answer': answer
                    })
            
        except Exception as e:
            self.logger.error(f"回答済み質問の取得に失敗しました: {e}")
        
        return answered
    
    def apply_learned_rules(self) -> Dict[str, any]:
        """
        回答済みの質問から学習し、システムに適用可能なルールを抽出
        
        Returns:
            学習したルールの辞書
        """
        learned_rules = {
            'teacher_rules': [],
            'subject_rules': [],
            'constraint_rules': [],
            'other_rules': []
        }
        
        answered = self.get_answered_questions()
        
        for qa in answered:
            question = qa['question'].lower()
            answer = qa['answer']
            
            # 教師に関するルール
            if '教師' in question or '先生' in question:
                learned_rules['teacher_rules'].append({
                    'question': qa['question'],
                    'rule': answer
                })
            
            # 科目配置に関するルール
            elif '科目' in question or '授業' in question or 'コマ' in question:
                learned_rules['subject_rules'].append({
                    'question': qa['question'],
                    'rule': answer
                })
            
            # 制約に関するルール
            elif '制約' in question or 'できません' in question or '違反' in question:
                learned_rules['constraint_rules'].append({
                    'question': qa['question'],
                    'rule': answer
                })
            
            # その他のルール
            else:
                learned_rules['other_rules'].append({
                    'question': qa['question'],
                    'rule': answer
                })
        
        return learned_rules
    
    def generate_question_from_error(self, error_type: str, error_details: Dict[str, any]) -> Optional[str]:
        """
        エラー情報から自動的に質問を生成
        
        Args:
            error_type: エラーの種類
            error_details: エラーの詳細情報
            
        Returns:
            生成された質問文字列、生成できない場合はNone
        """
        question = None
        
        if error_type == "teacher_conflict":
            teacher = error_details.get('teacher', '不明な教師')
            time_slot = error_details.get('time_slot', '不明な時間')
            classes = error_details.get('classes', [])
            
            if len(classes) > 1:
                class_list = ', '.join(str(c) for c in classes)
                question = f"{teacher}が{time_slot}に{class_list}の{len(classes)}クラスで同時に授業を行うことはできませんが、どのように対処すべきですか？"
        
        elif error_type == "constraint_violation":
            constraint = error_details.get('constraint_name', '不明な制約')
            description = error_details.get('description', '')
            question = f"{constraint}違反が発生しました：{description}。この問題をどのように解決すべきですか？"
        
        elif error_type == "empty_slots":
            class_ref = error_details.get('class', '不明なクラス')
            count = error_details.get('count', 0)
            question = f"{class_ref}に{count}個の空きコマがありますが、どの科目で埋めるべきですか？"
        
        elif error_type == "subject_hours":
            class_ref = error_details.get('class', '不明なクラス')
            subject = error_details.get('subject', '不明な科目')
            expected = error_details.get('expected', 0)
            actual = error_details.get('actual', 0)
            question = f"{class_ref}の{subject}の授業時数が標準時数（{expected}時間）と異なります（現在{actual}時間）。どのように調整すべきですか？"
        
        return question