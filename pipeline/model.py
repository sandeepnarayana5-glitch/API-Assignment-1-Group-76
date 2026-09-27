import os
import time
import json
import math
from typing import Dict, Any, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from config.settings import settings
from pipeline.logger import PipelineLogger

class ModelPipeline:
    """Trains and compares Baseline (Linear Regression) vs Improved (Random Forest) models."""

    def __init__(self, logger: PipelineLogger = None):
        self.logger = logger
        self.feature_columns = [
            "bedrooms", "bathrooms", "sqft_living", "sqft_lot", 
            "floors", "waterfront", "view", "condition", 
            "sqft_above", "sqft_basement", "property_age"
        ]
        self.model_save_path = os.path.join(settings.MODELS_DIR, "house_price_model.joblib")
        self.metrics_save_path = os.path.join(settings.REPORTS_DIR, "model_comparison.json")

    def train_and_evaluate(self, df: pd.DataFrame) -> Tuple[Any, Dict[str, Any]]:
        """
        Splits data, trains Linear Regression and Random Forest Regressor,
        computes MAE, MSE, RMSE, R2, and saves the best model.
        """
        start_time = time.time()
        
        if self.logger:
            self.logger.log_event("Modeling", "Model Training Started", "RUNNING", message="Evaluating baseline vs improved models")

        # Prepare X and y
        X = df[self.feature_columns].fillna(0)
        y = df["price"]

        # 80/20 train/test split with deterministic seed
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42)

        # Both models are trained on the raw price target. Extreme luxury
        # outliers (top 0.5%) were already removed during preprocessing, which
        # is what lets the tree model beat the linear baseline here.

        # 1. Baseline Model: Linear Regression
        lr = LinearRegression()
        lr.fit(X_train, y_train)
        lr_pred = lr.predict(X_test)

        lr_mae = mean_absolute_error(y_test, lr_pred)
        lr_mse = mean_squared_error(y_test, lr_pred)
        lr_rmse = math.sqrt(lr_mse)
        lr_r2 = r2_score(y_test, lr_pred)

        # 2. Improved Model: Random Forest Regressor
        rf = RandomForestRegressor(n_estimators=200, max_depth=14, min_samples_leaf=2,
                                   random_state=42, n_jobs=-1)
        rf.fit(X_train, y_train)
        rf_pred = rf.predict(X_test)

        rf_mae = mean_absolute_error(y_test, rf_pred)
        rf_mse = mean_squared_error(y_test, rf_pred)
        rf_rmse = math.sqrt(rf_mse)
        rf_r2 = r2_score(y_test, rf_pred)

        # Comparison table
        comparison = {
            "baseline_model": {
                "name": "Linear Regression",
                "mae": round(lr_mae, 2),
                "mse": round(lr_mse, 2),
                "rmse": round(lr_rmse, 2),
                "r2": round(lr_r2, 4)
            },
            "improved_model": {
                "name": "Random Forest Regressor",
                "mae": round(rf_mae, 2),
                "mse": round(rf_mse, 2),
                "rmse": round(rf_rmse, 2),
                "r2": round(rf_r2, 4)
            },
            "selected_model": "Random Forest Regressor" if rf_r2 >= lr_r2 else "Linear Regression",
            "selection_criterion": "Highest R2 on the held-out 20% test split",
            "target_preparation": "price>0 filter and top-0.5% outlier removal applied in preprocessing",
            "selected_metrics": {
                "mae": round(rf_mae if rf_r2 >= lr_r2 else lr_mae, 2),
                "rmse": round(rf_rmse if rf_r2 >= lr_r2 else lr_rmse, 2),
                "r2": round(max(rf_r2, lr_r2), 4)
            },
            "features_used": self.feature_columns,
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "evaluation_timestamp": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())
        }

        # Save the best model
        best_model = rf if rf_r2 >= lr_r2 else lr
        joblib.dump({"model": best_model, "features": self.feature_columns}, self.model_save_path)

        # Save metrics JSON
        with open(self.metrics_save_path, "w", encoding="utf-8") as f:
            json.dump(comparison, f, indent=2)

        duration = time.time() - start_time

        if self.logger:
            self.logger.log_event(
                "Modeling",
                "Model Evaluation Completed",
                "SUCCESS",
                duration=duration,
                message=f"Best model: {comparison['selected_model']} (R²: {max(rf_r2, lr_r2):.3f}, MAE: ${min(rf_mae, lr_mae):,.0f})"
            )

        return best_model, comparison

    def predict(self, feature_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Inference function using saved model."""
        if not os.path.exists(self.model_save_path):
            raise FileNotFoundError("Trained model artifact not found. Please run pipeline first.")
            
        saved = joblib.load(self.model_save_path)
        model = saved["model"]
        features = saved["features"]

        # Build feature vector
        row = []
        for feat in features:
            val = feature_dict.get(feat, 0)
            row.append(float(val))

        X_input = pd.DataFrame([row], columns=features)
        raw_prediction = float(model.predict(X_input)[0])
        # Real-world safety guard: house valuation cannot be negative
        predicted_price = max(10000.0, raw_prediction)

        return {
            "predicted_price": round(predicted_price, 2),
            "currency": "USD",
            "model_used": model.__class__.__name__,
            "features_provided": feature_dict
        }
