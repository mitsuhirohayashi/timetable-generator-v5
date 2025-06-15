"""Path configuration for timetable_v5 project."""
import os
from pathlib import Path

class PathConfig:
    """Centralized path configuration for the timetable system."""
    
    def __init__(self, base_dir: Path = None):
        if base_dir is None:
            # Default to timetable_v5 directory
            self.base_dir = Path(__file__).resolve().parent.parent.parent.parent
        else:
            self.base_dir = Path(base_dir).resolve()
        
        # Ensure we're in timetable_v5
        if self.base_dir.name != 'timetable_v5':
            # If not, assume we need to go up and find it
            for parent in self.base_dir.parents:
                if (parent / 'timetable_v5').exists():
                    self.base_dir = parent / 'timetable_v5'
                    break
        
        # Define all paths relative to base_dir
        self.data_dir = self.base_dir / 'data'
        self.config_dir = self.data_dir / 'config'
        self.input_dir = self.data_dir / 'input'
        self.output_dir = self.data_dir / 'output'
        self.logs_dir = self.base_dir / 'logs'
        self.scripts_dir = self.base_dir / 'scripts'
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
    
    def get_output_path(self, filename: str) -> Path:
        """Get the full path for an output file."""
        return self.output_dir / filename
    
    def get_config_path(self, filename: str) -> Path:
        """Get the full path for a config file."""
        return self.config_dir / filename
    
    def get_input_path(self, filename: str) -> Path:
        """Get the full path for an input file."""
        return self.input_dir / filename
    
    def get_log_path(self, filename: str) -> Path:
        """Get the full path for a log file."""
        return self.logs_dir / filename
    
    @property
    def default_output_csv(self) -> Path:
        """Default output CSV path."""
        return self.get_output_path('output.csv')
    
    @property
    def base_timetable_csv(self) -> Path:
        """Base timetable CSV path."""
        return self.get_config_path('base_timetable.csv')
    
    @property
    def input_csv(self) -> Path:
        """Input CSV path."""
        return self.get_input_path('input.csv')
    
    @property
    def followup_csv(self) -> Path:
        """Follow-up CSV path."""
        return self.get_input_path('Follow-up.csv')

# Global instance
path_config = PathConfig()