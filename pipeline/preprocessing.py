import os
import time
import json
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from config.settings import settings
from pipeline.logger import PipelineLogger

class DataPreprocessing:
    """Preprocesses real estate data for EDA and modeling according to Assignment 1.3."""

    def __init__(self, logger: PipelineLogger = None):
        self.logger = logger
        self.scaler = StandardScaler()

    def process(self, df_raw: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Executes full preprocessing pipeline:
        - Data-type analysis
        - Missing-value audit & imputation
        - Duplicate & invalid-value checks (handling price <= 0)
        - Summary statistics calculation
        - Numerical feature scaling
        - Saves processed dataset
        """
        start_time = time.time()
        df = df_raw.copy()
        
        if self.logger:
            self.logger.log_event("Preprocessing", "Preprocessing Started", "RUNNING", message="Initiating data validation & cleaning")

        # 1. Data Type Analysis (7.3)
        type_analysis = {}
        for col in df.columns:
            dtype = str(df[col].dtype)
            if col in ["price", "sqft_living", "sqft_lot", "sqft_above", "sqft_basement", "yr_built", "yr_renovated"]:
                logical_type = "Numerical (Continuous)"
            elif col in ["bedrooms", "bathrooms", "floors"]:
                logical_type = "Numerical (Discrete)"
            elif col in ["waterfront"]:
                logical_type = "Categorical (Binary)"
            elif col in ["view", "condition"]:
                logical_type = "Categorical (Ordinal)"
            elif col in ["date"]:
                logical_type = "Temporal (Date/Time)"
            else:
                logical_type = "Categorical (Nominal)"
                
            type_analysis[col] = {
                "detected_type": dtype,
                "logical_type": logical_type
            }

        # 2. Duplicate & Invalid Value Checks (7.5)
        initial_rows = len(df)
        duplicates_count = int(df.duplicated().sum())
        if duplicates_count > 0:
            df = df.drop_duplicates()

        # Handle invalid/null-like target prices (price <= 0)
        # As discovered, 49 properties have price = 0.0, representing non-market/missing transaction data.
        zero_prices_count = int((df["price"] <= 0).sum())
        clean_target_df = df[df["price"] > 0].copy()
        removed_records = initial_rows - len(clean_target_df)

        if self.logger:
            self.logger.log_event(
                "Preprocessing",
                "Quality Checks Completed",
                "SUCCESS",
                message=f"Removed {duplicates_count} duplicates and {zero_prices_count} invalid price=0 records."
            )

        df = clean_target_df

        # Extreme luxury outlier removal.
        # Prices run up to $26.5M against a median near $460K. That long tail
        # dominates squared-error training and is not representative of the
        # mainstream market this model targets, so the top 0.5% is trimmed.
        outlier_threshold = float(df["price"].quantile(0.995))
        rows_before_outliers = len(df)
        df = df[df["price"] <= outlier_threshold].copy()
        outliers_removed = rows_before_outliers - len(df)
        removed_records = initial_rows - len(df)

        if self.logger:
            self.logger.log_event(
                "Preprocessing",
                "Outlier Removal Completed",
                "SUCCESS",
                message=f"Removed {outliers_removed} records above the 99.5th percentile price threshold (${outlier_threshold:,.0f})."
            )

        # 3. Missing-Value Analysis & Imputation (7.2)
        missing_audit = {}
        imputation_log = []
        
        for col in df.columns:
            null_count = int(df[col].isnull().sum())
            null_pct = round((null_count / len(df)) * 100, 2)
            missing_audit[col] = {
                "missing_count": null_count,
                "missing_percentage": null_pct,
                "action_taken": "None"
            }
            
            # Numeric column imputation if missing
            if pd.api.types.is_numeric_dtype(df[col]) and null_count > 0:
                med_val = df[col].median()
                df[col] = df[col].fillna(med_val)
                missing_audit[col]["action_taken"] = f"Imputed with median ({med_val})"
                imputation_log.append(f"{col}: {null_count} nulls imputed with median ({med_val})")
            elif not pd.api.types.is_numeric_dtype(df[col]) and null_count > 0:
                mode_val = df[col].mode()[0]
                df[col] = df[col].fillna(mode_val)
                missing_audit[col]["action_taken"] = f"Imputed with mode ({mode_val})"
                imputation_log.append(f"{col}: {null_count} nulls imputed with mode ({mode_val})")

        # 4. Summary Statistics (7.1)
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        summary_stats = {}
        for col in numeric_cols:
            series = df[col]
            summary_stats[col] = {
                "count": int(series.count()),
                "mean": round(float(series.mean()), 2),
                "std": round(float(series.std()), 2),
                "min": round(float(series.min()), 2),
                "q25": round(float(series.quantile(0.25)), 2),
                "median": round(float(series.median()), 2),
                "q75": round(float(series.quantile(0.75)), 2),
                "max": round(float(series.max()), 2)
            }

        # 5. Feature Derivation & Scaling (7.4)
        # Calculate derived feature: property_age and is_renovated
        # Dataset dates are 2014, so current_year baseline is 2014
        df["property_age"] = 2014 - df["yr_built"]
        df["is_renovated"] = (df["yr_renovated"] > 0).astype(int)

        # Scale selected continuous numerical features
        scale_cols = ["sqft_living", "sqft_lot", "sqft_above", "sqft_basement", "property_age"]
        scaled_cols = [f"{col}_scaled" for col in scale_cols]
        scaled_values = self.scaler.fit_transform(df[scale_cols])
        
        for idx, sc_col in enumerate(scaled_cols):
            df[sc_col] = np.round(scaled_values[:, idx], 4)

        # 6. Save Clean Processed Dataset
        os.makedirs(os.path.dirname(settings.PROCESSED_DATA_PATH), exist_ok=True)
        df.to_csv(settings.PROCESSED_DATA_PATH, index=False)

        # Save summary stats JSON for API/Dashboard
        stats_path = os.path.join(settings.REPORTS_DIR, "summary_statistics.json")
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(summary_stats, f, indent=2)

        duration = time.time() - start_time
        
        metadata = {
            "initial_rows": initial_rows,
            "processed_rows": len(df),
            "removed_records": removed_records,
            "duplicates_removed": duplicates_count,
            "zero_prices_removed": zero_prices_count,
            "outliers_removed": outliers_removed,
            "outlier_threshold_price": round(outlier_threshold, 2),
            "data_types": type_analysis,
            "missing_value_audit": missing_audit,
            "imputation_log": imputation_log,
            "summary_statistics": summary_stats,
            "scaled_features": scale_cols,
            "scaling_strategy": "StandardScaler (Z-score normalization: zero mean, unit variance)",
            "duration_seconds": round(duration, 3),
            "status": "SUCCESS"
        }

        if self.logger:
            self.logger.log_event(
                "Preprocessing",
                "Preprocessing Completed",
                "SUCCESS",
                duration=duration,
                message=f"Clean dataset saved with {len(df)} records ({removed_records} invalid records filtered)."
            )

        return df, metadata
