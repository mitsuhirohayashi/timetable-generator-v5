"""ドキュメント自動生成モジュール

コードの変更に基づいて CLAUDE.md と sequence_diagram.md を自動更新する。
"""
import ast
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple
import re
from datetime import datetime


class DocumentationGenerator:
    """ドキュメント生成クラス"""
    
    def __init__(self, project_root: Path = None):
        self.logger = logging.getLogger(__name__)
        self.project_root = project_root or Path.cwd()
        self.src_path = self.project_root / "src"
        
    def update_documentation(self) -> Dict[str, bool]:
        """ドキュメントを更新"""
        self.logger.info("ドキュメント自動更新を開始")
        
        results = {
            "claude_md": self._update_claude_md(),
            "sequence_diagram": self._update_sequence_diagram()
        }
        
        self.logger.info(f"ドキュメント更新完了: {results}")
        return results
    
    def _update_claude_md(self) -> bool:
        """CLAUDE.md を更新"""
        try:
            # 現在のコード構造を解析
            architecture = self._analyze_architecture()
            constraints = self._analyze_constraints()
            commands = self._analyze_commands()
            
            # CLAUDE.md を読み込み
            claude_path = self.project_root / "CLAUDE.md"
            if claude_path.exists():
                with open(claude_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            else:
                content = self._get_claude_md_template()
            
            # セクションを更新
            content = self._update_architecture_section(content, architecture)
            content = self._update_constraints_section(content, constraints)
            content = self._update_commands_section(content, commands)
            content = self._update_timestamp(content)
            
            # ファイルに書き込み
            with open(claude_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
            
        except Exception as e:
            self.logger.error(f"CLAUDE.md 更新エラー: {e}")
            return False
    
    def _update_sequence_diagram(self) -> bool:
        """sequence_diagram.md を更新"""
        try:
            # フローを解析
            main_flow = self._analyze_main_flow()
            constraint_flow = self._analyze_constraint_flow()
            
            # sequence_diagram.md を読み込み
            seq_path = self.project_root / "sequence_diagram.md"
            if seq_path.exists():
                with open(seq_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            else:
                content = self._get_sequence_diagram_template()
            
            # フローを更新
            content = self._update_main_flow_section(content, main_flow)
            content = self._update_constraint_flow_section(content, constraint_flow)
            content = self._update_timestamp(content)
            
            # ファイルに書き込み
            with open(seq_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
            
        except Exception as e:
            self.logger.error(f"sequence_diagram.md 更新エラー: {e}")
            return False
    
    def _analyze_architecture(self) -> Dict[str, any]:
        """アーキテクチャを解析"""
        architecture = {
            "layers": [],
            "entities": [],
            "value_objects": [],
            "services": [],
            "use_cases": []
        }
        
        # 各レイヤーのファイルを解析
        for layer_path, layer_name in [
            (self.src_path / "domain", "Domain Layer"),
            (self.src_path / "application", "Application Layer"),
            (self.src_path / "infrastructure", "Infrastructure Layer"),
            (self.src_path / "presentation", "Presentation Layer")
        ]:
            if layer_path.exists():
                layer_info = {
                    "name": layer_name,
                    "path": f"src/{layer_path.name}/",
                    "components": []
                }
                
                # Pythonファイルを解析
                for py_file in layer_path.rglob("*.py"):
                    if py_file.name != "__init__.py":
                        classes = self._extract_classes(py_file)
                        if classes:
                            layer_info["components"].extend(classes)
                
                architecture["layers"].append(layer_info)
        
        # エンティティを特定
        entities_path = self.src_path / "domain" / "entities"
        if entities_path.exists():
            for py_file in entities_path.glob("*.py"):
                if py_file.name != "__init__.py":
                    architecture["entities"].extend(self._extract_classes(py_file))
        
        # 値オブジェクトを特定
        vo_path = self.src_path / "domain" / "value_objects"
        if vo_path.exists():
            for py_file in vo_path.glob("*.py"):
                if py_file.name != "__init__.py":
                    architecture["value_objects"].extend(self._extract_classes(py_file))
        
        return architecture
    
    def _analyze_constraints(self) -> Dict[str, List[str]]:
        """制約を解析"""
        constraints = {"hard": [], "soft": []}
        
        constraints_path = self.src_path / "domain" / "constraints"
        if not constraints_path.exists():
            return constraints
        
        for py_file in constraints_path.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # クラス定義を探す
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # 制約クラスかチェック
                        if "Constraint" in node.name:
                            # ソフト制約かハード制約かを判定
                            is_soft = self._is_soft_constraint(content, node.name)
                            if is_soft:
                                constraints["soft"].append(node.name)
                            else:
                                constraints["hard"].append(node.name)
                
            except Exception as e:
                self.logger.warning(f"制約解析エラー {py_file}: {e}")
        
        return constraints
    
    def _analyze_commands(self) -> List[Dict[str, str]]:
        """コマンドを解析"""
        commands = []
        
        # CLI main.py を解析
        cli_path = self.src_path / "presentation" / "cli" / "main.py"
        if not cli_path.exists():
            return commands
        
        try:
            with open(cli_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # argparse の add_argument を探す
            parser_pattern = r'parser\.add_argument\(["\']([^"\']+)["\'].*?help=["\']([^"\']+)["\']'
            matches = re.finditer(parser_pattern, content, re.DOTALL)
            
            for match in matches:
                arg_name = match.group(1)
                help_text = match.group(2)
                if arg_name.startswith("--"):
                    commands.append({
                        "argument": arg_name,
                        "description": help_text
                    })
            
        except Exception as e:
            self.logger.warning(f"コマンド解析エラー: {e}")
        
        return commands
    
    def _analyze_main_flow(self) -> List[str]:
        """メインフローを解析"""
        flows = []
        
        # GenerateScheduleUseCase を解析
        use_case_path = self.src_path / "application" / "use_cases" / "generate_schedule.py"
        if not use_case_path.exists():
            return flows
        
        try:
            with open(use_case_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # execute メソッドのステップを抽出
            step_pattern = r'# Step \d+: (.+)'
            matches = re.finditer(step_pattern, content)
            
            for match in matches:
                flows.append(match.group(1))
            
        except Exception as e:
            self.logger.warning(f"メインフロー解析エラー: {e}")
        
        return flows
    
    def _analyze_constraint_flow(self) -> List[str]:
        """制約フローを解析"""
        flows = []
        
        # BasicScheduleGenerator を解析
        generator_path = self.src_path / "domain" / "services" / "schedule_generator.py"
        if not generator_path.exists():
            return flows
        
        try:
            with open(generator_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # _fix_violations メソッドを探す
            if "_fix_violations" in content:
                flows.append("制約違反の修正処理")
            if "_fix_hard_violations" in content:
                flows.append("ハード制約違反の修正")
            if "_fix_soft_violations" in content:
                flows.append("ソフト制約違反の修正")
            
        except Exception as e:
            self.logger.warning(f"制約フロー解析エラー: {e}")
        
        return flows
    
    def _extract_classes(self, py_file: Path) -> List[str]:
        """Pythonファイルからクラスを抽出"""
        classes = []
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.append(node.name)
        
        except Exception as e:
            self.logger.warning(f"クラス抽出エラー {py_file}: {e}")
        
        return classes
    
    def _is_soft_constraint(self, content: str, class_name: str) -> bool:
        """ソフト制約かどうかを判定"""
        # StandardHoursConstraint や推奨系の制約はソフト制約
        soft_keywords = ["Standard", "Duplicate", "Preference", "Recommendation"]
        return any(keyword in class_name for keyword in soft_keywords)
    
    def _update_architecture_section(self, content: str, architecture: Dict) -> str:
        """アーキテクチャセクションを更新"""
        # 既存のアーキテクチャセクションを新しい情報で置き換え
        new_section = "\n### Core Architecture Layers\n"
        
        for layer in architecture["layers"]:
            new_section += f"- **{layer['name']}** (`{layer['path']}`) - "
            if "domain" in layer["path"]:
                new_section += "Core business logic and rules\n"
                if architecture["entities"]:
                    new_section += f"  - **Entities**: {', '.join(architecture['entities'][:5])}\n"
                if architecture["value_objects"]:
                    new_section += f"  - **Value Objects**: {', '.join(architecture['value_objects'][:5])}\n"
            elif "application" in layer["path"]:
                new_section += "Use cases and orchestration\n"
            elif "infrastructure" in layer["path"]:
                new_section += "External concerns\n"
            elif "presentation" in layer["path"]:
                new_section += "User interfaces\n"
        
        # セクションを置き換え
        pattern = r'### Core Architecture Layers.*?(?=###|\n\n)'
        if re.search(pattern, content, re.DOTALL):
            content = re.sub(pattern, new_section.strip() + "\n", content, flags=re.DOTALL)
        else:
            # セクションが存在しない場合は追加
            content += "\n" + new_section
        
        return content
    
    def _update_constraints_section(self, content: str, constraints: Dict) -> str:
        """制約セクションを更新"""
        new_section = "\n### Constraint Types\n\n"
        
        if constraints["hard"]:
            new_section += "**Hard Constraints (must be satisfied):**\n"
            for constraint in constraints["hard"]:
                desc = self._get_constraint_description(constraint)
                new_section += f"- `{constraint}` - {desc}\n"
        
        if constraints["soft"]:
            new_section += "\n**Soft Constraints (preferred but not required):**\n"
            for constraint in constraints["soft"]:
                desc = self._get_constraint_description(constraint)
                new_section += f"- `{constraint}` - {desc}\n"
        
        # セクションを置き換え
        pattern = r'### Constraint Types.*?(?=###|\n\n)'
        if re.search(pattern, content, re.DOTALL):
            content = re.sub(pattern, new_section.strip() + "\n", content, flags=re.DOTALL)
        
        return content
    
    def _update_commands_section(self, content: str, commands: List[Dict]) -> str:
        """コマンドセクションを更新"""
        # 既存のコマンドセクションは保持（手動で書かれた例が含まれているため）
        return content
    
    def _update_timestamp(self, content: str) -> str:
        """タイムスタンプを更新"""
        timestamp = f"\n<!-- Last auto-updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->\n"
        
        # 既存のタイムスタンプを置き換え
        pattern = r'<!-- Last auto-updated:.*?-->'
        if re.search(pattern, content):
            content = re.sub(pattern, timestamp.strip(), content)
        else:
            # タイムスタンプがない場合は末尾に追加
            content += timestamp
        
        return content
    
    def _update_main_flow_section(self, content: str, flows: List[str]) -> str:
        """メインフローセクションを更新"""
        if not flows:
            return content
        
        # Note over の部分を更新
        for i, flow in enumerate(flows, 1):
            pattern = f'Note over UseCase: Step {i}:.*'
            replacement = f'Note over UseCase: Step {i}: {flow}'
            if re.search(pattern, content):
                content = re.sub(pattern, replacement, content)
        
        return content
    
    def _update_constraint_flow_section(self, content: str, flows: List[str]) -> str:
        """制約フローセクションを更新"""
        # 既存の制約フローは詳細なので、大きな変更がない限り保持
        return content
    
    def _get_constraint_description(self, constraint_name: str) -> str:
        """制約の説明を取得"""
        descriptions = {
            "SubjectValidityConstraint": "Ensures subjects are valid for specific classes",
            "TeacherConflictConstraint": "Prevents teacher double-booking",
            "TeacherAvailabilityConstraint": "Respects teacher unavailability",
            "ExchangeClassConstraint": "Ensures exchange classes align with parent classes",
            "DailySubjectDuplicateConstraint": "Avoids same subject multiple times per day",
            "StandardHoursConstraint": "Maintains weekly hour targets per subject",
            "SpecialNeedsDuplicateConstraint": "Prevents duplicate special needs subjects"
        }
        return descriptions.get(constraint_name, "Constraint for schedule validation")
    
    def _get_claude_md_template(self) -> str:
        """CLAUDE.md のテンプレートを取得"""
        return """# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

### Running the Application
```bash
# Generate a basic timetable
python main.py generate

# Generate with soft constraints enabled
python main.py generate --soft-constraints --max-iterations 200

# Validate an existing timetable
python main.py validate output_timetable.csv
```

## Architecture Overview

This is a Domain-Driven Design (DDD) timetable generation system with clean layered architecture.

### Core Architecture Layers

### Key Design Patterns

### Constraint Types

<!-- Last auto-updated: Never -->
"""
    
    def _get_sequence_diagram_template(self) -> str:
        """sequence_diagram.md のテンプレートを取得"""
        return """# 時間割生成システム シーケンス図

## メイン処理フロー

```mermaid
sequenceDiagram
    participant User as ユーザー
    participant CLI as TimetableCLI
    participant UseCase as GenerateScheduleUseCase
```

<!-- Last auto-updated: Never -->
"""