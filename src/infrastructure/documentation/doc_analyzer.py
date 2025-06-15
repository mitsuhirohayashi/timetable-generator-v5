"""ドキュメント解析モジュール

プログラムの変更前に CLAUDE.md と sequence_diagram.md を読み込んで
構造を理解するための解析器。
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional
import re


class DocumentationAnalyzer:
    """ドキュメント解析クラス
    
    CLAUDE.md と sequence_diagram.md を読み込んで、
    システムの構造とフローを理解する。
    """
    
    def __init__(self, project_root: Path = None):
        self.logger = logging.getLogger(__name__)
        self.project_root = project_root or Path.cwd()
        self.claude_md_path = self.project_root / "CLAUDE.md"
        self.sequence_md_path = self.project_root / "sequence_diagram.md"
        self._architecture_info = None
        self._sequence_info = None
    
    def analyze_documentation(self) -> Dict[str, any]:
        """ドキュメントを解析して構造情報を取得"""
        self.logger.info("ドキュメント解析を開始")
        
        result = {
            "architecture": self._analyze_claude_md(),
            "sequence_flows": self._analyze_sequence_diagram(),
            "analyzed": True
        }
        
        self.logger.info("ドキュメント解析完了")
        return result
    
    def _analyze_claude_md(self) -> Dict[str, any]:
        """CLAUDE.md を解析"""
        if not self.claude_md_path.exists():
            self.logger.warning(f"CLAUDE.md が見つかりません: {self.claude_md_path}")
            return {}
        
        with open(self.claude_md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        architecture_info = {
            "layers": self._extract_layers(content),
            "constraints": self._extract_constraints(content),
            "key_patterns": self._extract_patterns(content),
            "commands": self._extract_commands(content),
            "file_formats": self._extract_file_formats(content)
        }
        
        self._architecture_info = architecture_info
        return architecture_info
    
    def _analyze_sequence_diagram(self) -> Dict[str, any]:
        """sequence_diagram.md を解析"""
        if not self.sequence_md_path.exists():
            self.logger.warning(f"sequence_diagram.md が見つかりません: {self.sequence_md_path}")
            return {}
        
        with open(self.sequence_md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        sequence_info = {
            "main_flow": self._extract_main_flow(content),
            "constraint_flow": self._extract_constraint_flow(content),
            "data_loading_flow": self._extract_data_loading_flow(content)
        }
        
        self._sequence_info = sequence_info
        return sequence_info
    
    def _extract_layers(self, content: str) -> List[Dict[str, str]]:
        """アーキテクチャレイヤーを抽出"""
        layers = []
        
        # レイヤーセクションを探す
        layer_pattern = r'- \*\*(\w+ Layer)\*\* \(`([^`]+)`\) - (.+?)(?=\n- \*\*|\n\n)'
        matches = re.finditer(layer_pattern, content, re.DOTALL)
        
        for match in matches:
            layer_name = match.group(1)
            layer_path = match.group(2)
            description = match.group(3).strip()
            
            layers.append({
                "name": layer_name,
                "path": layer_path,
                "description": description
            })
        
        return layers
    
    def _extract_constraints(self, content: str) -> Dict[str, List[str]]:
        """制約情報を抽出"""
        constraints = {"hard": [], "soft": []}
        
        # ハード制約の抽出
        hard_section = re.search(r'\*\*Hard Constraints.*?:(.*?)(?=\*\*Soft|\n\n)', content, re.DOTALL)
        if hard_section:
            constraints["hard"] = re.findall(r'- `(\w+)`', hard_section.group(1))
        
        # ソフト制約の抽出
        soft_section = re.search(r'\*\*Soft Constraints.*?:(.*?)(?=\n\n|\#)', content, re.DOTALL)
        if soft_section:
            constraints["soft"] = re.findall(r'- `(\w+)`', soft_section.group(1))
        
        return constraints
    
    def _extract_patterns(self, content: str) -> List[str]:
        """デザインパターンを抽出"""
        patterns = []
        pattern_section = re.search(r'### Key Design Patterns(.*?)(?=###|\n\n)', content, re.DOTALL)
        if pattern_section:
            patterns = re.findall(r'\*\*([^*]+)\*\*:', pattern_section.group(1))
        return patterns
    
    def _extract_commands(self, content: str) -> List[Dict[str, str]]:
        """コマンド情報を抽出"""
        commands = []
        command_section = re.search(r'### Running the Application(.*?)(?=###)', content, re.DOTALL)
        if command_section:
            cmd_matches = re.finditer(r'# (.+?)\npython main\.py (.+)', command_section.group(1))
            for match in cmd_matches:
                commands.append({
                    "description": match.group(1),
                    "command": f"python main.py {match.group(2)}"
                })
        return commands
    
    def _extract_file_formats(self, content: str) -> Dict[str, List[str]]:
        """ファイルフォーマット情報を抽出"""
        formats = {"input": [], "output": []}
        
        # Input Files セクション
        input_section = re.search(r'\*\*Input Files:\*\*(.*?)(?=\*\*Output:|###)', content, re.DOTALL)
        if input_section:
            formats["input"] = re.findall(r'- `([^`]+)`', input_section.group(1))
        
        # Output セクション
        output_section = re.search(r'\*\*Output:\*\*(.*?)(?=###|\n\n)', content, re.DOTALL)
        if output_section:
            formats["output"] = re.findall(r'- `([^`]+)`', output_section.group(1))
        
        return formats
    
    def _extract_main_flow(self, content: str) -> List[str]:
        """メインフローを抽出"""
        flows = []
        main_flow_section = re.search(r'## メイン処理フロー(.*?)(?=##|$)', content, re.DOTALL)
        if main_flow_section:
            flows = re.findall(r'Note over \w+: (.+)', main_flow_section.group(1))
        return flows
    
    def _extract_constraint_flow(self, content: str) -> List[str]:
        """制約チェックフローを抽出"""
        flows = []
        constraint_section = re.search(r'## 制約チェック詳細フロー(.*?)(?=##|$)', content, re.DOTALL)
        if constraint_section:
            flows = re.findall(r'alt (.+)', constraint_section.group(1))
        return flows
    
    def _extract_data_loading_flow(self, content: str) -> List[str]:
        """データ読み込みフローを抽出"""
        flows = []
        data_section = re.search(r'## データ読み込みフロー(.*?)(?=##|$)', content, re.DOTALL)
        if data_section:
            flows = re.findall(r'Repo->>[\w]+: (.+)', data_section.group(1))
        return flows
    
    def get_architecture_summary(self) -> str:
        """アーキテクチャ概要を取得"""
        if not self._architecture_info:
            self.analyze_documentation()
        
        summary = "【システムアーキテクチャ概要】\n"
        
        # _architecture_infoがNoneまたは空の場合の処理
        if not self._architecture_info:
            return summary
        
        # レイヤー情報
        if self._architecture_info.get("layers"):
            summary += "\n◆ アーキテクチャレイヤー:\n"
            for layer in self._architecture_info["layers"]:
                summary += f"  - {layer['name']} ({layer['path']})\n"
        
        # 制約情報
        if self._architecture_info.get("constraints"):
            summary += "\n◆ 制約システム:\n"
            summary += f"  - ハード制約: {', '.join(self._architecture_info['constraints']['hard'])}\n"
            summary += f"  - ソフト制約: {', '.join(self._architecture_info['constraints']['soft'])}\n"
        
        # デザインパターン
        if self._architecture_info.get("key_patterns"):
            summary += "\n◆ 主要デザインパターン:\n"
            for pattern in self._architecture_info["key_patterns"]:
                summary += f"  - {pattern}\n"
        
        return summary
    
    def get_sequence_summary(self) -> str:
        """シーケンスフロー概要を取得"""
        if not self._sequence_info:
            self.analyze_documentation()
        
        summary = "【処理フロー概要】\n"
        
        # _sequence_info が None または空の場合の処理
        if not self._sequence_info:
            return summary
        
        # メインフロー
        if self._sequence_info.get("main_flow"):
            summary += "\n◆ メイン処理フロー:\n"
            for i, flow in enumerate(self._sequence_info["main_flow"], 1):
                summary += f"  {i}. {flow}\n"
        
        return summary
    
    def should_update_documentation(self, changed_files: List[str]) -> bool:
        """変更されたファイルに基づいてドキュメント更新が必要か判定"""
        # 主要なソースコードの変更があれば更新が必要
        important_patterns = [
            r'src/domain/.*\.py$',
            r'src/application/.*\.py$',
            r'src/infrastructure/.*\.py$',
            r'src/presentation/.*\.py$',
            r'main\.py$'
        ]
        
        for file in changed_files:
            for pattern in important_patterns:
                if re.match(pattern, file):
                    return True
        
        return False