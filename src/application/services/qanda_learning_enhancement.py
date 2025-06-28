"""QandA学習機能強化サービス

ユーザーからの要望やルールを自動的にQA.txtに記録し、
システムが継続的に改善される仕組みを提供します。
"""

import logging
from datetime import datetime
from pathlib import Path
import re
from typing import Dict, List, Tuple, Optional
from ...domain.utils.schedule_utils import ScheduleUtils

class QandALearningEnhancementService:
    """QandA学習機能を強化し、ユーザーフィードバックを自動的に反映"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.qa_file = Path("QandA/QA.txt")
        self.learning_patterns = {
            'exchange_class': re.compile(r'交流学級|6組|7組|親学級|同期'),
            'empty_slot': re.compile(r'空き|埋め|スロット'),
            'teacher': re.compile(r'先生|教師|重複|同時'),
            'test_period': re.compile(r'テスト|試験|期間'),
            'rule': re.compile(r'ルール|規則|必ず|禁止|してはいけない'),
        }
    
    def analyze_user_feedback(self, feedback: str) -> Dict[str, any]:
        """ユーザーフィードバックを分析してルール化"""
        analysis = {
            'category': self._detect_category(feedback),
            'priority': self._estimate_priority(feedback),
            'rule_type': self._determine_rule_type(feedback),
            'actionable': self._extract_actionable_rule(feedback),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return analysis
    
    def _detect_category(self, text: str) -> str:
        """フィードバックのカテゴリを検出"""
        for category, pattern in self.learning_patterns.items():
            if pattern.search(text):
                return category
        return 'general'
    
    def _estimate_priority(self, text: str) -> str:
        """優先度を推定"""
        high_priority_words = ['必ず', '絶対', '重要', 'エラー', '違反']
        medium_priority_words = ['望ましい', '推奨', '改善']
        
        for word in high_priority_words:
            if word in text:
                return 'HIGH'
        
        for word in medium_priority_words:
            if word in text:
                return 'MEDIUM'
        
        return 'LOW'
    
    def _determine_rule_type(self, text: str) -> str:
        """ルールのタイプを判定"""
        if '禁止' in text or 'してはいけない' in text:
            return 'prohibition'
        elif '必ず' in text or '必須' in text:
            return 'mandatory'
        elif '場合' in text or '条件' in text:
            return 'conditional'
        else:
            return 'guideline'
    
    def _extract_actionable_rule(self, text: str) -> Optional[str]:
        """実行可能なルールを抽出"""
        # パターンベースでルールを抽出
        patterns = [
            (r'(.+)を(.+)する', r'\1を\2する'),
            (r'(.+)は(.+)でなければならない', r'\1は\2である必要がある'),
            (r'(.+)の場合は(.+)', r'\1の場合は\2'),
        ]
        
        for pattern, replacement in patterns:
            match = re.search(pattern, text)
            if match:
                return re.sub(pattern, replacement, match.group())
        
        return text
    
    def add_rule_to_qa(self, rule: str, category: str = 'general', 
                       priority: str = 'MEDIUM') -> bool:
        """新しいルールをQA.txtに追加"""
        try:
            # 既存のQA.txtを読み込む
            content = self._read_qa_file()
            
            # 恒久的ルールセクションを探す
            permanent_section_start = content.find('## 📌 恒久的ルール（常に適用）')
            if permanent_section_start == -1:
                self.logger.error("QA.txtに恒久的ルールセクションが見つかりません")
                return False
            
            # 新しいルールを適切な場所に挿入
            timestamp = datetime.now().strftime('%Y-%m-%d')
            new_rule = f"\n### 🆕 {category.title()}ルール（{timestamp}追加）\n{rule}\n"
            
            # アーカイブセクションの前に挿入
            archive_section = content.find('## 📦 アーカイブ')
            if archive_section > permanent_section_start:
                # 恒久的ルールセクションの最後に追加
                content = content[:archive_section] + new_rule + content[archive_section:]
            else:
                # ファイルの最後に追加
                content += new_rule
            
            # ファイルに書き込む
            self._write_qa_file(content)
            
            self.logger.info(f"新しいルールをQA.txtに追加しました: {rule[:50]}...")
            return True
            
        except Exception as e:
            self.logger.error(f"QA.txtへのルール追加に失敗: {e}")
            return False
    
    def _read_qa_file(self) -> str:
        """QA.txtファイルを読み込む"""
        if not self.qa_file.exists():
            return ""
        
        with open(self.qa_file, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _write_qa_file(self, content: str):
        """QA.txtファイルに書き込む"""
        # バックアップを作成
        if self.qa_file.exists():
            backup_path = self.qa_file.with_suffix('.backup')
            self.qa_file.rename(backup_path)
        
        # 新しい内容を書き込む
        with open(self.qa_file, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def extract_rules_from_violations(self, violations: List[str]) -> List[Dict[str, str]]:
        """制約違反から新しいルールを抽出"""
        rules = []
        
        for violation in violations:
            # 交流学級同期違反
            if '交流学級' in violation and '親学級' in violation:
                match = re.search(r'(\d+年\d+組).*親学級.*(\d+年\d+組)', violation)
                if match:
                    rule = {
                        'text': f"{match.group(1)}（交流学級）は{match.group(2)}（親学級）と同じ授業にする",
                        'category': 'exchange_class',
                        'priority': 'HIGH'
                    }
                    rules.append(rule)
            
            # 教師重複違反
            elif '教師重複' in violation:
                match = re.search(r'(.+先生)が(.+曜\d+限)に複数クラス', violation)
                if match:
                    rule = {
                        'text': f"{match.group(1)}は{match.group(2)}に1クラスまで",
                        'category': 'teacher',
                        'priority': 'HIGH'
                    }
                    rules.append(rule)
        
        return rules
    
    def apply_learned_rules(self, schedule, school) -> int:
        """学習したルールを時間割に適用"""
        applied_count = 0
        
        # QA.txtから恒久ルールを読み込む
        rules = self._load_permanent_rules()
        
        for rule in rules:
            if self._apply_single_rule(schedule, school, rule):
                applied_count += 1
        
        return applied_count
    
    def _load_permanent_rules(self) -> List[Dict[str, str]]:
        """QA.txtから恒久ルールを読み込む"""
        rules = []
        content = self._read_qa_file()
        
        # 恒久的ルールセクションを解析
        lines = content.split('\n')
        in_permanent_section = False
        current_rule = []
        
        for line in lines:
            if '## 📌 恒久的ルール' in line:
                in_permanent_section = True
                continue
            elif '## 📦 アーカイブ' in line:
                break
            
            if in_permanent_section and line.strip():
                if line.startswith('###'):
                    # 新しいルールカテゴリ
                    if current_rule:
                        rules.append({'text': '\n'.join(current_rule)})
                    current_rule = [line]
                else:
                    current_rule.append(line)
        
        if current_rule:
            rules.append({'text': '\n'.join(current_rule)})
        
        return rules
    
    def _apply_single_rule(self, schedule, school, rule: Dict[str, str]) -> bool:
        """単一のルールを適用"""
        # ルールテキストを解析して適用
        # 実際の実装は各ルールタイプに応じて行う
        return False
    
    def generate_improvement_suggestions(self, statistics: Dict) -> List[str]:
        """統計情報から改善提案を生成"""
        suggestions = []
        
        # 空きスロットが多い場合
        if statistics.get('empty_slots', 0) > 10:
            suggestions.append(
                "空きスロットが多数あります。交流学級同期を考慮した"
                "空きスロット埋めスクリプト（manual_fill_empty_slots_with_sync.py）"
                "の使用を推奨します。"
            )
        
        # 交流学級同期違反が多い場合
        if statistics.get('exchange_sync_violations', 0) > 0:
            suggestions.append(
                "交流学級同期違反があります。QA.txtの交流学級同期ルールを"
                "確認し、生成時に適用されているか確認してください。"
            )
        
        return suggestions