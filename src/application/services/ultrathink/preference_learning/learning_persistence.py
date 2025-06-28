"""学習データの永続化モジュール

学習状態の保存と読み込みを管理します。
"""
import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Any

from .data_models import LearningState


class LearningPersistence:
    """学習データ永続化クラス"""
    
    def __init__(self, data_dir: str):
        """初期化
        
        Args:
            data_dir: データ保存ディレクトリ
        """
        self.logger = logging.getLogger(__name__)
        self.data_dir = data_dir
        
        # データディレクトリの作成
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
    
    def save_state(self, state: LearningState, learning_history: List[Dict]):
        """学習状態を保存
        
        Args:
            state: 学習状態
            learning_history: 学習履歴
        """
        state_file = os.path.join(self.data_dir, "learning_state.json")
        
        # 保存用のデータを準備
        state_data = {
            'success_patterns': state.success_patterns[-100:],  # 最新100件
            'failure_patterns': state.failure_patterns[-100:],  # 最新100件
            'teacher_learning_data': state.teacher_learning_data,
            'adaptive_parameters': state.adaptive_parameters,
            'statistics': state.statistics,
            'last_updated': datetime.now().isoformat()
        }
        
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2)
        
        # 学習履歴も保存（最新20件）
        history_file = os.path.join(self.data_dir, "learning_history.json")
        recent_history = learning_history[-20:]
        
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(recent_history, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"学習状態を保存しました: {state_file}")
    
    def load_state(self, state: LearningState) -> List[Dict]:
        """学習状態を読み込み
        
        Args:
            state: 読み込み先の学習状態オブジェクト
            
        Returns:
            学習履歴
        """
        state_file = os.path.join(self.data_dir, "learning_state.json")
        learning_history = []
        
        if os.path.exists(state_file):
            with open(state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
                
                state.success_patterns = state_data.get('success_patterns', [])
                state.failure_patterns = state_data.get('failure_patterns', [])
                state.teacher_learning_data = state_data.get('teacher_learning_data', {})
                state.adaptive_parameters.update(state_data.get('adaptive_parameters', {}))
                state.statistics.update(state_data.get('statistics', {}))
                
                self.logger.info(f"学習状態を読み込みました: {state_file}")
        else:
            self.logger.info("学習状態ファイルが見つかりません。新規作成します。")
        
        # 学習履歴の読み込み
        history_file = os.path.join(self.data_dir, "learning_history.json")
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                learning_history = json.load(f)
                self.logger.info(f"学習履歴を読み込みました: {len(learning_history)}件")
        
        return learning_history
    
    def initialize_seasonal_factors(self) -> Dict[int, Dict[str, float]]:
        """季節要因を初期化
        
        Returns:
            月ごとの季節要因
        """
        return {
            1: {'morning': 0.4, 'afternoon': 0.6},  # 1月：寒いので遅めが好まれる
            2: {'morning': 0.45, 'afternoon': 0.55},
            3: {'morning': 0.5, 'afternoon': 0.5},
            4: {'morning': 0.6, 'afternoon': 0.4},  # 4月：新学期で朝型
            5: {'morning': 0.6, 'afternoon': 0.4},
            6: {'morning': 0.55, 'afternoon': 0.45},
            7: {'morning': 0.6, 'afternoon': 0.4},  # 7月：暑くなる前の朝型
            8: {'morning': 0.6, 'afternoon': 0.4},
            9: {'morning': 0.55, 'afternoon': 0.45},
            10: {'morning': 0.5, 'afternoon': 0.5},
            11: {'morning': 0.45, 'afternoon': 0.55},
            12: {'morning': 0.4, 'afternoon': 0.6}  # 12月：寒いので遅めが好まれる
        }
    
    def export_teacher_data(self, teacher_name: str, teacher_data: Dict) -> str:
        """特定の教師のデータをエクスポート
        
        Args:
            teacher_name: 教師名
            teacher_data: 教師の学習データ
            
        Returns:
            エクスポートファイルのパス
        """
        export_dir = os.path.join(self.data_dir, "exports")
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)
        
        filename = f"teacher_{teacher_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(export_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                'teacher_name': teacher_name,
                'data': teacher_data,
                'exported_at': datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"{teacher_name}先生のデータをエクスポートしました: {filepath}")
        return filepath
    
    def cleanup_old_data(self, days_to_keep: int = 90):
        """古いデータをクリーンアップ
        
        Args:
            days_to_keep: 保持する日数
        """
        # TODO: 実装が必要な場合は後で追加
        pass