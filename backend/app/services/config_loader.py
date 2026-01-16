"""
Configuration Loader for Dilla AI
Centralizes all configuration management and eliminates hardcoded values
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ConfigLoader:
    """
    Singleton configuration loader that manages all system configurations.
    Loads from YAML files and provides easy access to all config values.
    """
    
    _instance = None
    _configs = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize and load all configuration files"""
        self.config_dir = Path(__file__).parent.parent / 'config'
        self._load_all_configs()
    
    def _load_all_configs(self):
        """Load all YAML configuration files"""
        config_files = {
            'valuation': 'valuation_defaults.yaml',
            'orchestrator': 'orchestrator_config.yaml',
            'model': 'model_config.yaml',
            'lago': 'lago_config.yaml'
        }
        
        for config_name, filename in config_files.items():
            config_path = self.config_dir / filename
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        self._configs[config_name] = yaml.safe_load(f)
                        logger.info(f"Loaded {config_name} config from {filename}")
                except Exception as e:
                    logger.error(f"Failed to load {filename}: {e}")
                    self._configs[config_name] = {}
            else:
                logger.warning(f"Config file {filename} not found")
                self._configs[config_name] = {}
    
    def get(self, path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        Examples:
            - config.get('orchestrator.investment.check_size.default_by_stage.series_a')
            - config.get('valuation.stage_benchmarks.series_b.arr.median')
        """
        keys = path.split('.')
        value = self._configs
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        
        return value if value is not None else default
    
    def get_stage_defaults(self, stage: str) -> Dict[str, Any]:
        """Get all defaults for a specific funding stage"""
        stage_lower = stage.lower().replace(' ', '_')
        
        return {
            'check_size': self.get(f'orchestrator.investment.check_size.default_by_stage.{stage_lower}', 10_000_000),
            'revenue': self.get(f'orchestrator.defaults.revenue_by_stage.{stage_lower}', 1_000_000),
            'burn': self.get(f'orchestrator.defaults.burn_by_stage.{stage_lower}', 500_000),
            'employees': self.get(f'orchestrator.defaults.employees_by_stage.{stage_lower}', 25),
            'valuation': self.get(f'valuation.stage_benchmarks.{stage_lower}.valuation.median', 50_000_000),
            'arr_median': self.get(f'valuation.stage_benchmarks.{stage_lower}.arr.median', 5_000_000),
            'funding_median': self.get(f'valuation.stage_benchmarks.{stage_lower}.funding.median', 15_000_000),
            'dilution': self.get(f'orchestrator.ownership.dilution_per_round.by_stage.{stage_lower}_to_next', 0.20),
            'target_ownership': self.get(f'orchestrator.ownership.target_by_stage.{stage_lower}', 0.15),
        }
    
    def get_business_model_multiple(self, model_type: str) -> float:
        """Get valuation multiple for business model type"""
        model_lower = model_type.lower().replace(' ', '_').replace('-', '_')
        return self.get(f'valuation.business_model_multipliers.{model_lower}', 10)
    
    def get_revenue_thresholds(self) -> Dict[str, float]:
        """Get revenue thresholds for various calculations"""
        return {
            'large_saas': 50_000_000,  # Companies with >$50M revenue
            'mid_size': 10_000_000,     # Companies with $10-50M revenue
            'small': 1_000_000,         # Companies with $1-10M revenue
            'early': 100_000,           # Companies with <$1M revenue
        }
    
    def get_tam_thresholds(self) -> Dict[str, float]:
        """Get TAM thresholds for market scoring"""
        return {
            'massive': 100_000_000_000,  # >$100B TAM
            'large': 50_000_000_000,     # >$50B TAM
            'solid': 10_000_000_000,     # >$10B TAM
            'small': 5_000_000_000,      # <$5B TAM
        }
    
    def get_scoring_thresholds(self) -> Dict[str, float]:
        """Get thresholds for scoring calculations"""
        return {
            'valuation_cap': 1_000_000_000,  # Cap valuation at $1B for scoring
            'revenue_excellent': 100_000_000,  # $100M revenue is excellent
            'market_size_benchmark': 10_000_000_000,  # $10B market size benchmark
        }
    
    def get_fund_defaults(self, fund_size: Optional[float] = None) -> Dict[str, Any]:
        """Get fund-specific defaults"""
        if fund_size is None:
            fund_size = self.get('orchestrator.fund.fund_sizes.medium', 250_000_000)
        
        return {
            'fund_size': fund_size,
            'remaining_capital': fund_size * 0.6,  # Assume 40% deployed
            'check_size_min': fund_size * 0.01,    # 1% of fund minimum
            'check_size_max': fund_size * 0.10,    # 10% of fund maximum
            'check_size_typical': fund_size * 0.03,  # 3% typical check
            'reserve_ratio': self.get('orchestrator.fund.allocation.reserve_ratio', 2.0),
            'target_ownership_min': self.get('orchestrator.ownership.target_by_stage.series_c', 0.10),
            'target_ownership_typical': self.get('orchestrator.ownership.target_by_stage.series_a', 0.20),
        }
    
    def get_position_sizing_defaults(self) -> Dict[str, Any]:
        """Get position sizing defaults from config"""
        return {
            'strategies': ['kelly_criterion', 'equal_weight', 'risk_parity'],
            'constraints': {
                'max_position_size': self.get('orchestrator.fund.allocation.max_single_investment_pct', 0.10),
                'min_position_size': 0.01,
                'max_sector_exposure': 0.30,
                'max_stage_exposure': 0.40,
            },
            'risk_parameters': {
                'portfolio_volatility_target': 0.20,
                'max_drawdown': 0.30,
                'confidence_level': 0.95,
            }
        }
    
    def get_exit_scenarios(self) -> Dict[str, Any]:
        """Get default exit scenario parameters"""
        return {
            'default_exit_valuation': self.get('orchestrator.exit.default_exit_valuation', 1_000_000_000),
            'exit_multiples': {
                'min': self.get('orchestrator.exit.exit_multiple_range.min', 3),
                'max': self.get('orchestrator.exit.exit_multiple_range.max', 10),
                'default': self.get('orchestrator.exit.exit_multiple_range.default', 5),
            },
            'realistic_exit_values': [50_000_000, 86_000_000, 150_000_000, 250_000_000, 500_000_000],
            'probability_bands': {
                'downside': 0.25,
                'base': 0.50,
                'upside': 0.25,
            }
        }
    
    def reload(self):
        """Reload all configuration files"""
        self._configs.clear()
        self._load_all_configs()
        logger.info("Configuration reloaded")


# Global singleton instance
config = ConfigLoader()


def get_config() -> ConfigLoader:
    """Get the global configuration instance"""
    return config


# Convenience functions for common access patterns
def get_stage_check_size(stage: str) -> float:
    """Get default check size for a funding stage"""
    return config.get_stage_defaults(stage)['check_size']


def get_revenue_threshold(company_size: str) -> float:
    """Get revenue threshold for company size category"""
    thresholds = config.get_revenue_thresholds()
    return thresholds.get(company_size, 1_000_000)


def get_tam_threshold(market_size: str) -> float:
    """Get TAM threshold for market size category"""
    thresholds = config.get_tam_thresholds()
    return thresholds.get(market_size, 10_000_000_000)


def get_business_multiple(model: str) -> float:
    """Get valuation multiple for business model"""
    return config.get_business_model_multiple(model)