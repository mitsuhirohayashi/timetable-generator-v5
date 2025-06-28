"""Follow-upデータローダー

Follow-up.csvファイルからデータを読み込むヘルパークラスです。
"""
import logging
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ....infrastructure.config.path_manager import PathManager

from ....shared.utils.csv_operations import CSVOperations


class FollowupLoader:
    """Follow-upデータローダー"""
    
    def __init__(self, path_manager: 'PathManager'):
        self.path_manager = path_manager
        self.logger = logging.getLogger(__name__)
        self.csv_ops = CSVOperations()
    
    def load_followup_data(self) -> Optional[Dict[str, Any]]:
        """Follow-up.csvからデータを読み込む
        
        Returns:
            曜日をキーとしたFollow-upデータの辞書、または読み込み失敗時はNone
        """
        try:
            followup_path = self.path_manager.get_input_path('Follow-up.csv')
            
            followup_data = {}
            
            # CSVOperationsを使用して読み込み
            rows = self.csv_ops.read_csv(followup_path)
            for row in rows:
                if '曜日' in row:
                    day = row['曜日'].strip()
                    content = []
                    for key, value in row.items():
                        if key != '曜日' and value and value.strip():
                            content.append(value.strip())
                    if content:
                        followup_data[day] = ' '.join(content)
            
            if followup_data:
                self.logger.info(f"Follow-upデータを{len(followup_data)}件読み込みました")
                return followup_data
            else:
                self.logger.warning("Follow-upデータが空です")
                return None
                
        except FileNotFoundError:
            self.logger.warning("Follow-up.csvファイルが見つかりません")
            return None
        except Exception as e:
            self.logger.error(f"Follow-upデータの読み込みに失敗しました: {e}")
            return None