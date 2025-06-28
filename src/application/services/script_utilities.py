"""
Centralized utilities for scripts to avoid code duplication.
This module provides common functions used across various fix and analysis scripts.
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
from pathlib import Path

from src.domain.utils.schedule_utils import ScheduleUtils
from src.infrastructure.di_container import get_container
from src.domain.interfaces.repositories import IScheduleRepository, ITeacherMappingRepository
from src.domain.interfaces.path_configuration import IPathConfiguration
from src.shared.utils.csv_operations import CSVOperations


class ScriptUtilities:
    """Common utilities for scripts"""
    
    def __init__(self):
        container = get_container()
        self.csv_repo = container.resolve(IScheduleRepository)
        self.teacher_repo = container.resolve(ITeacherMappingRepository)
        self.schedule_utils = ScheduleUtils
        self.path_config = container.resolve(IPathConfiguration)
        self.csv_ops = CSVOperations()
    
    # Re-export commonly used functions from ScheduleUtils
    @staticmethod
    def is_fixed_subject(subject: str) -> bool:
        """Check if subject is fixed"""
        return ScheduleUtils.is_fixed_subject(subject)
    
    @staticmethod
    def get_exchange_class(parent_class: str) -> Optional[str]:
        """Get exchange class for parent class"""
        return ScheduleUtils.EXCHANGE_CLASS_PAIRS.get(parent_class)
    
    @staticmethod
    def is_exchange_class(class_name: str) -> bool:
        """Check if class is exchange class"""
        return class_name in ScheduleUtils.EXCHANGE_CLASSES
    
    @staticmethod
    def is_grade5_class(class_name: str) -> bool:
        """Check if class is Grade 5"""
        return class_name in ScheduleUtils.GRADE5_CLASSES
    
    # CSV Operations
    def read_schedule(self, filepath: Optional[str] = None) -> pd.DataFrame:
        """Read schedule from CSV with standard format"""
        if filepath is None:
            filepath = self.path_config.output_file
        # CSVOperationsを使用して読み込み、DataFrameに変換
        rows = self.csv_ops.read_csv_raw(filepath)
        return pd.DataFrame(rows)
    
    def save_schedule(self, df: pd.DataFrame, filepath: Optional[str] = None):
        """Save schedule to CSV with standard format"""
        if filepath is None:
            filepath = self.path_config.output_file
        # DataFrameをリストのリストに変換してCSVOperationsで書き込み
        rows = df.values.tolist()
        self.csv_ops.write_csv_raw(filepath, rows)
    
    def get_schedule_cell(self, df: pd.DataFrame, class_name: str, day: str, period: int) -> Tuple[int, int, str]:
        """Get cell position and value for given class, day, period"""
        # Find class row
        class_row = None
        for i in range(2, len(df)):
            if df.iloc[i, 0] == class_name:
                class_row = i
                break
        
        if class_row is None:
            raise ValueError(f"Class {class_name} not found")
        
        # Find column for day and period
        col = None
        for j in range(1, len(df.columns)):
            if df.iloc[0, j] == day and str(df.iloc[1, j]) == str(period):
                col = j
                break
        
        if col is None:
            raise ValueError(f"{day}曜{period}限 not found")
        
        value = df.iloc[class_row, col]
        return class_row, col, str(value) if pd.notna(value) else ""
    
    def set_schedule_cell(self, df: pd.DataFrame, class_name: str, day: str, period: int, subject: str):
        """Set value for given class, day, period"""
        row, col, _ = self.get_schedule_cell(df, class_name, day, period)
        df.iloc[row, col] = subject
    
    # Teacher operations
    def load_teacher_mappings(self) -> Dict[str, Dict[str, str]]:
        """Load teacher mappings for all classes"""
        return self.teacher_repo.load_teacher_mapping()
    
    def get_teacher_for_subject(self, class_name: str, subject: str, 
                                teacher_mappings: Optional[Dict] = None) -> Optional[str]:
        """Get teacher for subject in class"""
        if teacher_mappings is None:
            teacher_mappings = self.load_teacher_mappings()
        
        if class_name in teacher_mappings and subject in teacher_mappings[class_name]:
            return teacher_mappings[class_name][subject]
        return None
    
    # Analysis utilities
    def find_empty_slots(self, df: pd.DataFrame) -> List[Dict]:
        """Find all empty slots in schedule"""
        empty_slots = []
        
        for row_idx in range(2, len(df)):
            row = df.iloc[row_idx]
            
            # Skip empty rows
            if pd.isna(row[0]) or str(row[0]).strip() == "":
                continue
            
            class_name = row[0]
            
            for col_idx in range(1, len(row)):
                value = row[col_idx]
                
                if pd.isna(value) or str(value).strip() == "":
                    day = df.iloc[0, col_idx]
                    period = df.iloc[1, col_idx]
                    empty_slots.append({
                        'row': row_idx,
                        'col': col_idx,
                        'class': class_name,
                        'day': day,
                        'period': period
                    })
        
        return empty_slots
    
    def check_daily_duplicates(self, df: pd.DataFrame) -> List[Dict]:
        """Check for daily duplicate violations"""
        violations = []
        
        for row_idx in range(2, len(df)):
            row = df.iloc[row_idx]
            if pd.isna(row[0]) or str(row[0]).strip() == "":
                continue
            
            class_name = row[0]
            
            # Check each day
            for day in ['月', '火', '水', '木', '金']:
                subjects_in_day = {}
                
                for col_idx in range(1, len(row)):
                    if df.iloc[0, col_idx] == day:
                        subject = str(row[col_idx]) if pd.notna(row[col_idx]) else ""
                        if subject and not self.is_fixed_subject(subject):
                            period = df.iloc[1, col_idx]
                            if subject in subjects_in_day:
                                violations.append({
                                    'class': class_name,
                                    'day': day,
                                    'subject': subject,
                                    'periods': [subjects_in_day[subject], period]
                                })
                            else:
                                subjects_in_day[subject] = period
        
        return violations
    
    def check_exchange_class_sync(self, df: pd.DataFrame) -> List[Dict]:
        """Check exchange class synchronization violations"""
        violations = []
        
        for parent_class, exchange_class in ScheduleUtils.EXCHANGE_CLASS_PAIRS.items():
            for col_idx in range(1, df.shape[1]):
                try:
                    parent_row, _, parent_subject = self.get_schedule_cell(df, parent_class, 
                                                                          df.iloc[0, col_idx], 
                                                                          df.iloc[1, col_idx])
                    exchange_row, _, exchange_subject = self.get_schedule_cell(df, exchange_class,
                                                                              df.iloc[0, col_idx],
                                                                              df.iloc[1, col_idx])
                    
                    # Check if exchange class has jiritsu/nissay/sagyou
                    if exchange_subject in ['自立', '日生', '作業']:
                        continue  # These don't need to sync
                    
                    # Otherwise they should match
                    if parent_subject != exchange_subject:
                        violations.append({
                            'parent_class': parent_class,
                            'exchange_class': exchange_class,
                            'day': df.iloc[0, col_idx],
                            'period': df.iloc[1, col_idx],
                            'parent_subject': parent_subject,
                            'exchange_subject': exchange_subject
                        })
                        
                except ValueError:
                    # Class not found, skip
                    continue
        
        return violations
    
    def get_proper_file_location(self, filename: str) -> Path:
        """
        Determine the proper location for a file based on its name and type.
        This helps keep the project organized by placing files in appropriate directories.
        
        Args:
            filename: The name of the file to be placed
            
        Returns:
            Path object with the proper location for the file
        """
        filename_lower = filename.lower()
        base_path = Path(self.path_config.project_root)
        
        # Test files
        if filename_lower.startswith('test_') and filename_lower.endswith('.py'):
            return base_path / 'tests' / 'unit' / filename
        
        # Analysis scripts
        if (filename_lower.startswith('analyze_') or 
            filename_lower.startswith('check_') and filename_lower.endswith('.py')):
            return base_path / 'scripts' / 'analysis' / filename
        
        # Fix scripts
        if filename_lower.startswith('fix_') and filename_lower.endswith('.py'):
            return base_path / 'scripts' / 'fixes' / filename
        
        # Debug scripts
        if filename_lower.startswith('debug_') and filename_lower.endswith('.py'):
            return base_path / 'scripts' / 'debug' / filename
        
        # Documentation
        if filename_lower.endswith(('.md', '.rst')):
            # Special case for README files
            if filename_lower in ['readme.md', 'claude.md']:
                return base_path / filename
            return base_path / 'docs' / filename
        
        # Reports and analysis results
        if (filename_lower.endswith(('_report.json', '_report.txt', '_analysis.json', 
                                     '_analysis.txt', '_summary.md', '_summary.txt'))):
            return base_path / 'docs' / 'reports' / filename
        
        # Log files
        if filename_lower.endswith('.log'):
            return base_path / 'logs' / filename
        
        # Output CSV files
        if filename_lower.endswith('.csv'):
            if 'output' in filename_lower or 'teacher_schedule' in filename_lower:
                return base_path / 'data' / 'output' / filename
            elif 'input' in filename_lower:
                return base_path / 'data' / 'input' / filename
            elif any(config_type in filename_lower for config_type in 
                    ['mapping', 'config', 'rules', 'constraints', 'subjects']):
                return base_path / 'data' / 'config' / filename
        
        # Backup files
        if 'backup' in filename_lower or filename_lower.endswith('.bak'):
            if 'output' in filename_lower:
                return base_path / 'data' / 'output' / 'backup' / filename
            elif 'input' in filename_lower:
                return base_path / 'data' / 'input' / 'backup' / filename
            elif 'config' in filename_lower:
                return base_path / 'data' / 'config' / 'backups' / filename
        
        # Default: don't put in root directory
        # Instead, put temporary files in temp directory
        if any(pattern in filename_lower for pattern in ['temp', 'tmp', 'test']):
            return base_path / 'temp' / filename
        
        # For other files, suggest appropriate location based on extension
        if filename_lower.endswith('.py'):
            return base_path / 'scripts' / 'utilities' / filename
        
        # Default to temp directory to avoid cluttering root
        return base_path / 'temp' / filename
    
    def ensure_file_location(self, filepath: str) -> str:
        """
        Ensure a file is saved in the proper location.
        Creates directories if needed and returns the proper path.
        
        Args:
            filepath: The intended file path
            
        Returns:
            The proper file path as a string
        """
        filename = Path(filepath).name
        proper_path = self.get_proper_file_location(filename)
        
        # Create directory if it doesn't exist
        proper_path.parent.mkdir(parents=True, exist_ok=True)
        
        return str(proper_path)

# Create global instance for easy import
script_utils = ScriptUtilities()