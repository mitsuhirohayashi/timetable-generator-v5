"""ドキュメント管理サービス

プログラムの実行前後でドキュメントの読み込みと更新を自動的に行う。
"""
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from ...infrastructure.documentation.doc_analyzer import DocumentationAnalyzer
from ...infrastructure.documentation.doc_generator import DocumentationGenerator


class DocumentationService:
    """ドキュメント管理サービス
    
    プログラムの変更前にドキュメントを読み込んで構造を理解し、
    変更後に自動的にドキュメントを更新する。
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DocumentationService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.logger = logging.getLogger(__name__)
            self.project_root = Path.cwd()
            self.analyzer = DocumentationAnalyzer(self.project_root)
            self.generator = DocumentationGenerator(self.project_root)
            self._architecture_info = None
            self._sequence_info = None
            self._initialized = True
    
    def initialize(self) -> None:
        """サービスを初期化してドキュメントを読み込む"""
        self.logger.info("=== ドキュメント管理サービスを初期化 ===")
        
        # ドキュメントを解析
        doc_info = self.analyzer.analyze_documentation()
        self._architecture_info = doc_info.get("architecture", {})
        self._sequence_info = doc_info.get("sequence_flows", {})
        
        # 解析結果をログ出力
        self.logger.info("ドキュメント解析完了:")
        self.logger.info(self.analyzer.get_architecture_summary())
        self.logger.info(self.analyzer.get_sequence_summary())
    
    def get_architecture_info(self) -> Dict[str, Any]:
        """アーキテクチャ情報を取得"""
        if self._architecture_info is None:
            self.initialize()
        return self._architecture_info
    
    def get_sequence_info(self) -> Dict[str, Any]:
        """シーケンス情報を取得"""
        if self._sequence_info is None:
            self.initialize()
        return self._sequence_info
    
    def update_documentation_if_needed(self, force: bool = False) -> Dict[str, bool]:
        """必要に応じてドキュメントを更新"""
        if force:
            self.logger.info("ドキュメントの強制更新を実行")
            return self.generator.update_documentation()
        
        # 通常は手動でのみ更新（自動更新は開発時の git hook で行う）
        self.logger.debug("ドキュメント更新はスキップ（手動更新モード）")
        return {"claude_md": False, "sequence_diagram": False}
    
    def log_architecture_understanding(self) -> None:
        """理解したアーキテクチャをログ出力"""
        if not self._architecture_info:
            self.initialize()
        
        self.logger.info("\n=== システムアーキテクチャの理解 ===")
        
        # レイヤー構造
        layers = self._architecture_info.get("layers", [])
        if layers:
            self.logger.info("◆ レイヤー構造:")
            for layer in layers:
                self.logger.info(f"  - {layer['name']} ({layer['path']})")
        
        # 制約システム
        constraints = self._architecture_info.get("constraints", {})
        if constraints:
            self.logger.info("◆ 制約システム:")
            if constraints.get("hard"):
                self.logger.info(f"  - ハード制約: {len(constraints['hard'])}個")
            if constraints.get("soft"):
                self.logger.info(f"  - ソフト制約: {len(constraints['soft'])}個")
        
        # デザインパターン
        patterns = self._architecture_info.get("key_patterns", [])
        if patterns:
            self.logger.info("◆ 使用されているデザインパターン:")
            for pattern in patterns:
                self.logger.info(f"  - {pattern}")
    
    def check_before_modification(self, target_module: str) -> None:
        """変更前のチェック"""
        self.logger.info(f"\n=== {target_module} の変更前チェック ===")
        
        # アーキテクチャ情報を確認
        if not self._architecture_info:
            self.initialize()
        
        # 対象モジュールに関連する情報をログ出力
        if "constraint" in target_module.lower():
            constraints = self._architecture_info.get("constraints", {})
            self.logger.info("現在の制約システム:")
            self.logger.info(f"  - ハード制約: {constraints.get('hard', [])}")
            self.logger.info(f"  - ソフト制約: {constraints.get('soft', [])}")
        
        elif "use_case" in target_module.lower() or "application" in target_module.lower():
            self.logger.info("アプリケーション層の主要フロー:")
            main_flow = self._sequence_info.get("main_flow", [])
            for i, flow in enumerate(main_flow[:5], 1):
                self.logger.info(f"  {i}. {flow}")
        
        elif "service" in target_module.lower() or "generator" in target_module.lower():
            self.logger.info("ドメインサービスの処理フロー:")
            constraint_flow = self._sequence_info.get("constraint_flow", [])
            for flow in constraint_flow[:3]:
                self.logger.info(f"  - {flow}")


# グローバルインスタンス
documentation_service = DocumentationService()


def get_documentation_service() -> DocumentationService:
    """ドキュメント管理サービスのインスタンスを取得"""
    return documentation_service