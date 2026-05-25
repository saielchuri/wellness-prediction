"""
Test suite for Nytia Health Capstone pipeline components.
Run with: pytest tests/ -v
"""
import pytest
import pandas as pd
import numpy as np
import yaml
import os
import sys

# Add service paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'features'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'ingestion'))


@pytest.fixture
def config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
    with open(config_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def sample_row():
    return {
        'dif_nutri': '(-1000)-(-250)',
        'c_val_nut': '600-1000',
        'dif_obesic': '250-1000',
        'c_val_obe': '0-400',
        'dif_sleep': '250-1000',
        'c_val_sle': '600-1000',
        'dif_depre': '(-250)-0',
        'c_val_dep': '600-1000',
        'dif_wellr': '0-250',
        'c_val_wel': '0-400',
        'dif_anti_stress': '(-250)-0',
        'c_val_anti_stress': '400-600',
        'dif_anti_smoke': '(-250)-0',
        'c_val_anti_smoke': '0-400',
        'dif_move': '(-1000)-(-250)',
        'c_val_movement': '400-600',
        'recommendations': 'Take a post-meal walk.',
        'status_assessment': 'Be careful! You need to start improving with respect to your Anti-Smoke, and Movement.'
    }


@pytest.fixture
def sample_df(sample_row):
    return pd.DataFrame([sample_row] * 10)


# ── Encoding Tests ──
class TestOrdinalEncoding:
    def test_trajectory_encoding_values(self, config):
        mapping = config['encoding']['trajectory']
        assert mapping['(-1000)-(-250)'] == 1
        assert mapping['(-250)-0'] == 2
        assert mapping['0-250'] == 3
        assert mapping['250-1000'] == 4

    def test_current_value_encoding_values(self, config):
        mapping = config['encoding']['current_value']
        assert mapping['0-400'] == 1
        assert mapping['400-600'] == 2
        assert mapping['600-1000'] == 3

    def test_encoding_applied_correctly(self, sample_df, config):
        from src.feature_builder import ordinal_encode
        df = ordinal_encode(sample_df.copy(), config)
        assert df['dif_nutri_enc'].iloc[0] == 1  # (-1000)-(-250) -> 1
        assert df['c_val_nut_enc'].iloc[0] == 3   # 600-1000 -> 3
        assert df['dif_obesic_enc'].iloc[0] == 4   # 250-1000 -> 4
        assert df['c_val_obe_enc'].iloc[0] == 1    # 0-400 -> 1

    def test_no_null_after_encoding(self, sample_df, config):
        from src.feature_builder import ordinal_encode
        df = ordinal_encode(sample_df.copy(), config)
        enc_cols = [c + '_enc' for c in config['columns']['trajectory'] + config['columns']['current_value']]
        assert df[enc_cols].isnull().sum().sum() == 0


# ── Feature Derivation Tests ──
class TestFeatureDerivation:
    def test_declining_count(self, sample_df, config):
        from src.feature_builder import ordinal_encode, derive_features
        df = ordinal_encode(sample_df.copy(), config)
        df = derive_features(df, config)
        # dif_nutri=1, dif_depre=2, dif_anti_stress=2, dif_anti_smoke=2, dif_move=1 -> 5 declining
        assert df['total_declining_count'].iloc[0] == 5

    def test_critical_cval_count(self, sample_df, config):
        from src.feature_builder import ordinal_encode, derive_features
        df = ordinal_encode(sample_df.copy(), config)
        df = derive_features(df, config)
        # c_val_obe=1, c_val_wel=1, c_val_anti_smoke=1 -> 3 critical
        assert df['critical_cval_count'].iloc[0] == 3

    def test_risk_tier_assignment(self, sample_df, config):
        from src.feature_builder import ordinal_encode, derive_features
        df = ordinal_encode(sample_df.copy(), config)
        df = derive_features(df, config)
        # 5 declining, 3 critical -> High risk (tier 2)
        assert df['risk_tier'].iloc[0] == 2
        assert df['risk_label'].iloc[0] == 'High'

    def test_risk_tiers_are_valid(self, sample_df, config):
        from src.feature_builder import ordinal_encode, derive_features
        df = ordinal_encode(sample_df.copy(), config)
        df = derive_features(df, config)
        assert set(df['risk_tier'].unique()).issubset({0, 1, 2})


# ── Config Tests ──
class TestConfiguration:
    def test_config_has_all_sections(self, config):
        assert 'columns' in config
        assert 'encoding' in config
        assert 'risk_tiers' in config
        assert 'model' in config
        assert 'recommendations' in config

    def test_eight_dimensions(self, config):
        assert len(config['columns']['trajectory']) == 8
        assert len(config['columns']['current_value']) == 8
        assert len(config['dimensions']) == 8

    def test_model_hyperparameters(self, config):
        hp = config['model']['hyperparameters']
        assert hp['max_depth'] > 0
        assert 0 < hp['learning_rate'] <= 1
        assert hp['n_estimators'] > 0
