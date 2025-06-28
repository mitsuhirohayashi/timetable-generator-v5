"""
改善されたQandAサービス
ステータス管理、視覚的フォーマット、自動整理機能を実装
"""

import os
import re
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Literal
from enum import Enum
import logging


class QuestionStatus(Enum):
    """質問のステータス"""
    UNANSWERED = "未回答"
    RESOLVED = "解決済み"
    PERMANENT = "恒久ルール"
    ARCHIVED = "アーカイブ済み"


class QuestionPriority(Enum):
    """質問の優先度"""
    CRITICAL = "🔴 緊急"
    HIGH = "🟡 高"
    MEDIUM = "🟢 中"
    LOW = "⚪ 低"


class Question:
    """質問データモデル"""
    def __init__(
        self,
        id: str,
        question: str,
        answer: Optional[str] = None,
        status: QuestionStatus = QuestionStatus.UNANSWERED,
        priority: QuestionPriority = QuestionPriority.MEDIUM,
        category: Optional[str] = None,
        context: Optional[str] = None,
        created_at: Optional[datetime] = None,
        resolved_at: Optional[datetime] = None,
        tags: Optional[List[str]] = None
    ):
        self.id = id
        self.question = question
        self.answer = answer
        self.status = status
        self.priority = priority
        self.category = category
        self.context = context
        self.created_at = created_at or datetime.now()
        self.resolved_at = resolved_at
        self.tags = tags or []


class ImprovedQandAService:
    """改善されたQandAシステムを管理するサービス"""
    
    def __init__(self, qa_file_path: str = "QandA/QA.txt", metadata_path: str = "QandA/qa_metadata.json"):
        self.qa_file_path = Path(qa_file_path)
        self.metadata_path = Path(metadata_path)
        self.logger = logging.getLogger(__name__)
        self._ensure_files_exist()
        self.questions: Dict[str, Question] = self._load_questions()
    
    def get_unanswered_questions(self) -> List[Question]:
        """未回答の質問を取得"""
        return [q for q in self.questions.values() if q.status == QuestionStatus.UNANSWERED]
    
    def _ensure_files_exist(self) -> None:
        """必要なファイルが存在することを確認"""
        self.qa_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.qa_file_path.exists():
            self._create_initial_qa_file()
        
        if not self.metadata_path.exists():
            self._create_initial_metadata()
    
    def _create_initial_qa_file(self) -> None:
        """初期のQA.txtファイルを作成（新フォーマット）"""
        initial_content = """# 📚 時間割生成システム - Q&Aマネジメント
==========================================

このファイルは時間割生成システムの質問と回答を管理します。
視覚的に整理され、ステータス管理機能を備えています。

最終更新: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """
==========================================


## 🔴 未回答の質問（要対応）
-----------------------------------
※ これらの質問に回答してください

[未回答の質問はここに表示されます]


## ✅ 解決済みの質問（履歴）
-----------------------------------
※ 解決された質問の記録

[解決済みの質問はここに表示されます]


## 📌 恒久的ルール（常に適用）
-----------------------------------
※ システムが常に参照するルール

### 🏫 担任教師の担当科目ルール
各クラスの担任教師は以下の科目を担当します：
- 学活（学）
- 総合（総、総合）
- 学総（学年総合）
- YT（特別活動）

### ⚠️ 固定科目の保護
以下の科目は絶対に変更してはいけません：
- 欠（欠課）
- YT（特別活動）
- 学、学活（学級活動）
- 総、総合（総合的な学習の時間）
- 道、道徳（道徳）
- 学総（学年総合）
- 行、行事（行事）
- テスト（定期テスト）
- 技家（技術・家庭科合併テスト）

### 🏃 5組の合同授業
5組（1-5, 2-5, 3-5）は全教科で3クラス合同授業を行うため、
1人の教師が3クラスを同時に担当します。これは制約違反ではありません。

### 📝 テスト期間のルール
テスト期間中は以下のルールが適用されます：
- 時間割の変更は原則禁止
- 教師は巡回監督のため複数クラスを担当可能
- 体育の筆記試験は各教室で実施（体育館制限なし）


## 📦 アーカイブ（参考情報）
-----------------------------------
※ 古い解決済み質問（参考用）

[アーカイブされた質問はここに表示されます]


==========================================
このファイルは自動的に管理されています。
手動で編集する場合は、フォーマットを維持してください。
"""
        with open(self.qa_file_path, 'w', encoding='utf-8') as f:
            f.write(initial_content)
    
    def _create_initial_metadata(self) -> None:
        """初期のメタデータファイルを作成"""
        initial_metadata = {
            "version": "2.0",
            "last_updated": datetime.now().isoformat(),
            "statistics": {
                "total_questions": 0,
                "unanswered": 0,
                "resolved": 0,
                "permanent": 0,
                "archived": 0
            },
            "categories": [
                "教師配置",
                "交流学級",
                "テスト期間",
                "固定科目",
                "施設使用",
                "担任教師",
                "会議・不在",
                "科目配置",
                "その他"
            ],
            "questions": {}
        }
        with open(self.metadata_path, 'w', encoding='utf-8') as f:
            json.dump(initial_metadata, f, ensure_ascii=False, indent=2)
    
    def _load_questions(self) -> Dict[str, Question]:
        """メタデータから質問を読み込む"""
        questions = {}
        try:
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            for q_id, q_data in metadata.get("questions", {}).items():
                questions[q_id] = Question(
                    id=q_id,
                    question=q_data["question"],
                    answer=q_data.get("answer"),
                    status=QuestionStatus(q_data["status"]),
                    priority=QuestionPriority(q_data["priority"]),
                    category=q_data.get("category"),
                    context=q_data.get("context"),
                    created_at=datetime.fromisoformat(q_data["created_at"]),
                    resolved_at=datetime.fromisoformat(q_data["resolved_at"]) if q_data.get("resolved_at") else None,
                    tags=q_data.get("tags", [])
                )
        except Exception as e:
            self.logger.error(f"質問の読み込みに失敗しました: {e}")
        
        return questions
    
    def _save_questions(self) -> None:
        """質問をメタデータとQA.txtに保存"""
        # メタデータを保存
        try:
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            metadata["last_updated"] = datetime.now().isoformat()
            metadata["questions"] = {}
            
            # 統計を更新
            stats = {
                "total_questions": len(self.questions),
                "unanswered": 0,
                "resolved": 0,
                "permanent": 0,
                "archived": 0
            }
            
            for question in self.questions.values():
                metadata["questions"][question.id] = {
                    "question": question.question,
                    "answer": question.answer,
                    "status": question.status.value,
                    "priority": question.priority.value,
                    "category": question.category,
                    "context": question.context,
                    "created_at": question.created_at.isoformat(),
                    "resolved_at": question.resolved_at.isoformat() if question.resolved_at else None,
                    "tags": question.tags
                }
                
                # 統計を更新
                if question.status == QuestionStatus.UNANSWERED:
                    stats["unanswered"] += 1
                elif question.status == QuestionStatus.RESOLVED:
                    stats["resolved"] += 1
                elif question.status == QuestionStatus.PERMANENT:
                    stats["permanent"] += 1
                elif question.status == QuestionStatus.ARCHIVED:
                    stats["archived"] += 1
            
            metadata["statistics"] = stats
            
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            # QA.txtを更新
            self._update_qa_file()
            
        except Exception as e:
            self.logger.error(f"質問の保存に失敗しました: {e}")
    
    def _update_qa_file(self) -> None:
        """QA.txtファイルを更新"""
        # 質問をステータスと優先度でソート
        unanswered = sorted(
            [q for q in self.questions.values() if q.status == QuestionStatus.UNANSWERED],
            key=lambda x: (x.priority.value, x.created_at),
            reverse=True
        )
        resolved = sorted(
            [q for q in self.questions.values() if q.status == QuestionStatus.RESOLVED],
            key=lambda x: x.resolved_at or x.created_at,
            reverse=True
        )
        permanent = [q for q in self.questions.values() if q.status == QuestionStatus.PERMANENT]
        archived = sorted(
            [q for q in self.questions.values() if q.status == QuestionStatus.ARCHIVED],
            key=lambda x: x.resolved_at or x.created_at,
            reverse=True
        )
        
        # 既存のファイルから恒久的ルールセクションを保持
        permanent_section = self._extract_permanent_section()
        
        # 新しい内容を構築
        content = f"""# 📚 時間割生成システム - Q&Aマネジメント
==========================================

このファイルは時間割生成システムの質問と回答を管理します。
視覚的に整理され、ステータス管理機能を備えています。

最終更新: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
==========================================


## 🔴 未回答の質問（要対応）
-----------------------------------
※ これらの質問に回答してください

"""
        
        if unanswered:
            for q in unanswered:
                content += f"\n{q.priority.value} [{q.created_at.strftime('%Y-%m-%d %H:%M')}] ID: {q.id}\n"
                if q.category:
                    content += f"📁 カテゴリー: {q.category}\n"
                content += f"❓ 質問: {q.question}\n"
                if q.context:
                    content += f"📝 背景: {q.context}\n"
                content += f"💬 回答: [ここに回答を記入してください]\n"
                content += "-" * 50 + "\n"
        else:
            content += "\n✨ 現在、未回答の質問はありません。\n"
        
        content += """

## ✅ 解決済みの質問（履歴）
-----------------------------------
※ 解決された質問の記録

"""
        
        if resolved:
            # 最新10件のみ表示
            for q in resolved[:10]:
                content += f"\n[{q.resolved_at.strftime('%Y-%m-%d') if q.resolved_at else 'N/A'}] ID: {q.id}\n"
                if q.category:
                    content += f"📁 {q.category}\n"
                content += f"Q: {q.question}\n"
                content += f"A: {q.answer}\n"
                content += "-" * 30 + "\n"
            
            if len(resolved) > 10:
                content += f"\n... 他 {len(resolved) - 10} 件の解決済み質問があります。\n"
        else:
            content += "\n（解決済みの質問はまだありません）\n"
        
        content += """

## 📌 恒久的ルール（常に適用）
-----------------------------------
※ システムが常に参照するルール

"""
        content += permanent_section
        
        content += """

## 📦 アーカイブ（参考情報）
-----------------------------------
※ 古い解決済み質問（参考用）

"""
        
        if archived:
            content += f"アーカイブされた質問: {len(archived)} 件\n"
            content += "（詳細はqa_metadata.jsonを参照）\n"
        else:
            content += "（アーカイブされた質問はありません）\n"
        
        content += """

==========================================
このファイルは自動的に管理されています。
手動で編集する場合は、フォーマットを維持してください。
"""
        
        with open(self.qa_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _extract_permanent_section(self) -> str:
        """既存のQA.txtから恒久的ルールセクションを抽出"""
        try:
            with open(self.qa_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 恒久的ルールセクションを探す
            start_marker = "## 📌 恒久的ルール（常に適用）"
            end_marker = "## 📦 アーカイブ（参考情報）"
            
            start = content.find(start_marker)
            end = content.find(end_marker)
            
            if start != -1 and end != -1:
                section = content[start + len(start_marker):end].strip()
                return section.replace("-----------------------------------\n※ システムが常に参照するルール\n\n", "")
            
        except Exception:
            pass
        
        # デフォルトの恒久的ルール
        return """### 🏫 担任教師の担当科目ルール
各クラスの担任教師は以下の科目を担当します：
- 学活（学）
- 総合（総、総合）
- 学総（学年総合）
- YT（特別活動）

### ⚠️ 固定科目の保護
以下の科目は絶対に変更してはいけません：
- 欠（欠課）
- YT（特別活動）
- 学、学活（学級活動）
- 総、総合（総合的な学習の時間）
- 道、道徳（道徳）
- 学総（学年総合）
- 行、行事（行事）
- テスト（定期テスト）
- 技家（技術・家庭科合併テスト）

### 🏃 5組の合同授業
5組（1-5, 2-5, 3-5）は全教科で3クラス合同授業を行うため、
1人の教師が3クラスを同時に担当します。これは制約違反ではありません。

### 📝 テスト期間のルール
テスト期間中は以下のルールが適用されます：
- 時間割の変更は原則禁止
- 教師は巡回監督のため複数クラスを担当可能
- 体育の筆記試験は各教室で実施（体育館制限なし）"""
    
    def add_question(
        self,
        question: str,
        priority: QuestionPriority = QuestionPriority.MEDIUM,
        category: Optional[str] = None,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """
        新しい質問を追加
        
        Returns:
            生成された質問ID
        """
        # 質問IDを生成
        q_id = f"Q{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 質問オブジェクトを作成
        new_question = Question(
            id=q_id,
            question=question,
            priority=priority,
            category=category,
            context=context,
            tags=tags
        )
        
        self.questions[q_id] = new_question
        self._save_questions()
        
        self.logger.info(f"新しい質問を追加しました: {q_id} - {question[:50]}...")
        return q_id
    
    def answer_question(self, question_id: str, answer: str) -> bool:
        """
        質問に回答を追加し、ステータスを解決済みに変更
        """
        if question_id not in self.questions:
            self.logger.error(f"質問ID {question_id} が見つかりません")
            return False
        
        question = self.questions[question_id]
        question.answer = answer
        question.status = QuestionStatus.RESOLVED
        question.resolved_at = datetime.now()
        
        self._save_questions()
        self.logger.info(f"質問 {question_id} に回答を追加しました")
        return True
    
    def promote_to_permanent(self, question_id: str) -> bool:
        """
        質問を恒久的ルールに昇格
        """
        if question_id not in self.questions:
            return False
        
        question = self.questions[question_id]
        if not question.answer:
            self.logger.error("回答のない質問は恒久的ルールにできません")
            return False
        
        question.status = QuestionStatus.PERMANENT
        self._save_questions()
        self.logger.info(f"質問 {question_id} を恒久的ルールに昇格しました")
        return True
    
    def archive_old_questions(self, days: int = 30) -> int:
        """
        指定日数以上経過した解決済み質問をアーカイブ
        """
        archived_count = 0
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for question in self.questions.values():
            if (question.status == QuestionStatus.RESOLVED and
                question.resolved_at and
                question.resolved_at < cutoff_date):
                question.status = QuestionStatus.ARCHIVED
                archived_count += 1
        
        if archived_count > 0:
            self._save_questions()
            self.logger.info(f"{archived_count} 件の質問をアーカイブしました")
        
        return archived_count
    
    def get_questions_by_status(self, status: QuestionStatus) -> List[Question]:
        """
        指定されたステータスの質問を取得
        """
        return [q for q in self.questions.values() if q.status == status]
    
    def get_questions_by_category(self, category: str) -> List[Question]:
        """
        指定されたカテゴリーの質問を取得
        """
        return [q for q in self.questions.values() if q.category == category]
    
    def search_questions(self, keyword: str) -> List[Question]:
        """
        キーワードで質問を検索
        """
        keyword_lower = keyword.lower()
        results = []
        
        for question in self.questions.values():
            if (keyword_lower in question.question.lower() or
                (question.answer and keyword_lower in question.answer.lower()) or
                (question.context and keyword_lower in question.context.lower())):
                results.append(question)
        
        return results
    
    def generate_question_from_error(
        self,
        error_type: str,
        error_details: Dict[str, any],
        priority: QuestionPriority = QuestionPriority.HIGH
    ) -> Optional[str]:
        """
        エラー情報から自動的に質問を生成して追加
        """
        question = None
        category = "その他"
        context = f"エラータイプ: {error_type}"
        
        if error_type == "teacher_conflict":
            teacher = error_details.get('teacher', '不明な教師')
            time_slot = error_details.get('time_slot', '不明な時間')
            classes = error_details.get('classes', [])
            category = "教師配置"
            
            if len(classes) > 1:
                class_list = ', '.join(str(c) for c in classes)
                question = f"{teacher}が{time_slot}に{class_list}の{len(classes)}クラスで同時に授業を行うことはできませんが、どのように対処すべきですか？"
        
        elif error_type == "constraint_violation":
            constraint = error_details.get('constraint_name', '不明な制約')
            description = error_details.get('description', '')
            category = "制約違反"
            question = f"{constraint}違反が発生しました：{description}。この問題をどのように解決すべきですか？"
        
        elif error_type == "empty_slots":
            class_ref = error_details.get('class', '不明なクラス')
            count = error_details.get('count', 0)
            category = "科目配置"
            question = f"{class_ref}に{count}個の空きコマがありますが、どの科目で埋めるべきですか？"
        
        elif error_type == "subject_hours":
            class_ref = error_details.get('class', '不明なクラス')
            subject = error_details.get('subject', '不明な科目')
            expected = error_details.get('expected', 0)
            actual = error_details.get('actual', 0)
            category = "科目配置"
            question = f"{class_ref}の{subject}の授業時数が標準時数（{expected}時間）と異なります（現在{actual}時間）。どのように調整すべきですか？"
        
        if question:
            return self.add_question(
                question=question,
                priority=priority,
                category=category,
                context=context,
                tags=[error_type]
            )
        
        return None
    
    def get_statistics(self) -> Dict[str, int]:
        """
        質問の統計情報を取得
        """
        stats = {
            "total": len(self.questions),
            "unanswered": len([q for q in self.questions.values() if q.status == QuestionStatus.UNANSWERED]),
            "resolved": len([q for q in self.questions.values() if q.status == QuestionStatus.RESOLVED]),
            "permanent": len([q for q in self.questions.values() if q.status == QuestionStatus.PERMANENT]),
            "archived": len([q for q in self.questions.values() if q.status == QuestionStatus.ARCHIVED])
        }
        
        # カテゴリー別統計
        category_stats = {}
        for question in self.questions.values():
            if question.category:
                category_stats[question.category] = category_stats.get(question.category, 0) + 1
        
        stats["by_category"] = category_stats
        return stats
    
    def get_answered_questions(self) -> List[Dict[str, any]]:
        """
        回答済みの質問を取得
        
        Returns:
            回答済み質問のリスト
        """
        answered = []
        for question in self.questions.values():
            if question.status in [QuestionStatus.RESOLVED, QuestionStatus.PERMANENT] and question.answer:
                answered.append({
                    'id': question.id,
                    'question': question.question,
                    'answer': question.answer,
                    'category': question.category,
                    'status': question.status.value,
                    'created_at': question.created_at.isoformat() if question.created_at else None,
                    'resolved_at': question.resolved_at.isoformat() if question.resolved_at else None
                })
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
        
        return stats