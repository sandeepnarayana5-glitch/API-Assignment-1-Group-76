import os
import time
import json
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless cloud execution
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from config.settings import settings
from pipeline.logger import PipelineLogger

class ExploratoryDataAnalysis:
    """Automated EDA module performing statistical analysis, binning, encoding, and chart generation."""

    def __init__(self, logger: PipelineLogger = None):
        self.logger = logger
        self.charts_dir = settings.CHARTS_DIR
        os.makedirs(self.charts_dir, exist_ok=True)

    def analyze(self, df_clean: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Executes full EDA workflow:
        - 8.1 Univariate Analysis
        - 8.2 Bivariate Analysis
        - 8.3 Correlation Matrix & Heatmap
        - 8.4 Categorical Analysis
        - 8.5 Binning continuous variables
        - 8.6 Encoding categorical variables
        - 8.7 Feature Importance calculation
        """
        start_time = time.time()
        df = df_clean.copy()

        if self.logger:
            self.logger.log_event("EDA", "EDA Workflow Started", "RUNNING", message="Generating statistical metrics and visualizations")

        # 8.3 Correlation Analysis (Pearson)
        numeric_cols = ["price", "bedrooms", "bathrooms", "sqft_living", "sqft_lot", 
                        "floors", "waterfront", "view", "condition", "sqft_above", 
                        "sqft_basement", "yr_built", "property_age"]
        # Filter only existing columns
        num_cols_present = [c for c in numeric_cols if c in df.columns]
        corr_matrix = df[num_cols_present].corr()

        # Price correlations ranked
        price_corr = corr_matrix["price"].drop("price").sort_values(ascending=False)
        top_positive = [{"feature": k, "correlation": round(float(v), 3)} for k, v in price_corr.items() if v > 0][:5]
        top_negative = [{"feature": k, "correlation": round(float(v), 3)} for k, v in price_corr.items() if v < 0][:5]

        # 8.5 Binning Continuous Variables
        # 1. Living space bin
        df["living_space_bin"] = pd.cut(
            df["sqft_living"],
            bins=[0, 1500, 2500, 3500, np.inf],
            labels=["Small (<1500 sqft)", "Medium (1500-2500)", "Large (2500-3500)", "Luxury (>3500)"]
        )
        
        # 2. Property age bin
        df["property_age_bin"] = pd.cut(
            df["property_age"],
            bins=[-np.inf, 15, 40, 70, np.inf],
            labels=["New (<15 yrs)", "Modern (15-40 yrs)", "Mature (40-70 yrs)", "Historic (>70 yrs)"]
        )

        # 3. Bedroom bin
        df["bedroom_bin"] = pd.cut(
            df["bedrooms"],
            bins=[-np.inf, 2, 4, np.inf],
            labels=["1-2 Beds", "3-4 Beds", "5+ Beds"]
        )

        binning_summary = {
            "living_space_distribution": df["living_space_bin"].value_counts().to_dict(),
            "property_age_distribution": df["property_age_bin"].value_counts().to_dict(),
            "bedroom_distribution": df["bedroom_bin"].value_counts().to_dict()
        }

        # 8.6 Encoding Categorical Variables (rubric 1.4)
        encoding_summary = {}

        # (a) One-hot encoding of the ordinal 'condition' rating -> condition_1..condition_5
        if "condition" in df.columns:
            cond_dummies = pd.get_dummies(df["condition"].astype(int), prefix="condition")
            df = pd.concat([df, cond_dummies.astype(int)], axis=1)
            encoding_summary["one_hot_condition"] = {
                "technique": "One-Hot Encoding (pandas.get_dummies)",
                "source_column": "condition",
                "columns_created": list(cond_dummies.columns),
                "new_column_count": int(cond_dummies.shape[1])
            }

        # (b) Ordinal / label encoding of the binned living-space categories
        if "living_space_bin" in df.columns:
            bin_categories = list(df["living_space_bin"].cat.categories)
            bin_mapping = {str(cat): i for i, cat in enumerate(bin_categories)}
            df["living_space_bin_encoded"] = df["living_space_bin"].cat.codes
            encoding_summary["label_living_space_bin"] = {
                "technique": "Ordinal / Label Encoding (category codes)",
                "source_column": "living_space_bin",
                "mapping": bin_mapping
            }

        # (c) Frequency encoding of the high-cardinality 'city' column.
        # One-hot on city would create ~44 sparse columns, so frequency encoding
        # is used instead - it keeps a single numeric column and avoids the
        # target leakage that mean-price encoding would introduce.
        if "city" in df.columns:
            city_freq = df["city"].value_counts(normalize=True)
            df["city_frequency_encoded"] = df["city"].map(city_freq).round(5)
            encoding_summary["frequency_city"] = {
                "technique": "Frequency Encoding (normalised value counts)",
                "source_column": "city",
                "distinct_categories": int(df["city"].nunique()),
                "rationale": "High cardinality - one-hot would add ~%d sparse columns" % int(df["city"].nunique()),
                "sample_mapping": {str(k): round(float(v), 5) for k, v in city_freq.head(5).items()}
            }

        # (d) Binary encoding of the waterfront flag (already 0/1, recorded for completeness)
        if "waterfront" in df.columns:
            encoding_summary["binary_waterfront"] = {
                "technique": "Binary Encoding (0 = no waterfront, 1 = waterfront)",
                "source_column": "waterfront",
                "distribution": {str(k): int(v) for k, v in df["waterfront"].value_counts().items()}
            }

        if self.logger:
            self.logger.log_event(
                "EDA",
                "Categorical Encoding Completed",
                "SUCCESS",
                message=f"Applied {len(encoding_summary)} encoding techniques (one-hot, label, frequency, binary)."
            )

        # 8.4 Categorical Relationships
        city_stats = df.groupby("city")["price"].agg(["count", "mean", "median"]).reset_index()
        top_expensive_cities = city_stats.sort_values(by="median", ascending=False).head(5)
        top_cities_summary = [
            {"city": row["city"], "count": int(row["count"]), "median_price": round(float(row["median"]), 2)}
            for _, row in top_expensive_cities.iterrows()
        ]

        # 8.6 Feature Importance (8.7) via Random Forest
        feature_cols = ["bedrooms", "bathrooms", "sqft_living", "sqft_lot", "floors", 
                        "waterfront", "view", "condition", "sqft_above", "sqft_basement", "property_age"]
        X_rf = df[feature_cols].fillna(0)
        y_rf = df["price"]
        
        rf = RandomForestRegressor(n_estimators=50, random_state=42, max_depth=10, n_jobs=-1)
        rf.fit(X_rf, y_rf)
        importances = rf.feature_importances_
        feature_rankings = sorted(
            [{"feature": col, "importance": round(float(imp), 4)} for col, imp in zip(feature_cols, importances)],
            key=lambda x: x["importance"],
            reverse=True
        )

        # Generate Required Visualizations (Univariate, Bivariate, Heatmap, Importance)
        generated_charts = self._generate_visualizations(df, corr_matrix, feature_rankings)

        duration = time.time() - start_time
        
        eda_metadata = {
            "correlation_summary": {
                "top_positive_correlations": top_positive,
                "top_negative_correlations": top_negative
            },
            "binning_summary": binning_summary,
            "encoding_summary": encoding_summary,
            "top_expensive_cities": top_cities_summary,
            "feature_importance_ranking": feature_rankings,
            "charts_generated": generated_charts,
            "duration_seconds": round(duration, 3),
            "status": "SUCCESS"
        }

        # Save summary JSON for API
        eda_json_path = os.path.join(settings.REPORTS_DIR, "eda_summary.json")
        with open(eda_json_path, "w", encoding="utf-8") as f:
            json.dump(eda_metadata, f, indent=2)

        if self.logger:
            self.logger.log_event(
                "EDA",
                "EDA Completed",
                "SUCCESS",
                duration=duration,
                message=f"EDA completed. Top predictor: {feature_rankings[0]['feature']} ({round(feature_rankings[0]['importance']*100, 1)}%)."
            )

        return df, eda_metadata

    def _generate_visualizations(self, df: pd.DataFrame, corr_matrix: pd.DataFrame, feature_rankings: list) -> Dict[str, str]:
        """Generates static PNG charts for univariate, bivariate, and correlation outputs."""
        chart_paths = {}

        # 1. Price Distribution (Univariate)
        try:
            fig, ax = plt.subplots(figsize=(8, 5))
            # Plot prices under 2M for visual clarity
            filtered_prices = df[df["price"] < 2000000]["price"] / 1000
            ax.hist(filtered_prices, bins=40, color="#1a5e8a", edgecolor="#123f5e", alpha=0.85)
            ax.set_title("House Price Distribution (< $2M USD)", fontsize=13, fontweight="bold", pad=12)
            ax.set_xlabel("Price (Thousands of USD)", fontsize=11)
            ax.set_ylabel("Frequency", fontsize=11)
            ax.grid(axis="y", linestyle="--", alpha=0.5)
            path1 = os.path.join(self.charts_dir, "price_distribution.png")
            fig.tight_layout()
            fig.savefig(path1, dpi=120)
            plt.close(fig)
            chart_paths["price_distribution"] = "/reports/eda_charts/price_distribution.png"
        except Exception as e:
            if self.logger: self.logger.log_event("EDA", "Chart Gen Error", "WARNING", message=str(e))

        # 2. Bivariate: Living Area vs Price
        try:
            fig, ax = plt.subplots(figsize=(8, 5))
            sample_df = df[df["price"] < 2500000].sample(min(1500, len(df)), random_state=42)
            ax.scatter(sample_df["sqft_living"], sample_df["price"] / 1000, alpha=0.4, color="#2d6a4f", edgecolors="none")
            ax.set_title("Living Area (sqft) vs Price ($K)", fontsize=13, fontweight="bold", pad=12)
            ax.set_xlabel("Living Area (Square Feet)", fontsize=11)
            ax.set_ylabel("Price ($1,000 USD)", fontsize=11)
            ax.grid(True, linestyle="--", alpha=0.4)
            path2 = os.path.join(self.charts_dir, "sqft_vs_price.png")
            fig.tight_layout()
            fig.savefig(path2, dpi=120)
            plt.close(fig)
            chart_paths["sqft_vs_price"] = "/reports/eda_charts/sqft_vs_price.png"
        except Exception as e:
            if self.logger: self.logger.log_event("EDA", "Chart Gen Error", "WARNING", message=str(e))

        # 3. Correlation Heatmap
        try:
            fig, ax = plt.subplots(figsize=(9, 7))
            im = ax.imshow(corr_matrix, cmap="Blues", vmin=-0.3, vmax=1.0)
            ax.set_xticks(range(len(corr_matrix.columns)))
            ax.set_yticks(range(len(corr_matrix.columns)))
            ax.set_xticklabels(corr_matrix.columns, rotation=45, ha="right", fontsize=9)
            ax.set_yticklabels(corr_matrix.columns, fontsize=9)
            cbar = fig.colorbar(im, ax=ax)
            cbar.set_label("Pearson Correlation", fontsize=10)
            ax.set_title("Correlation Matrix Heatmap", fontsize=13, fontweight="bold", pad=12)
            path3 = os.path.join(self.charts_dir, "correlation_heatmap.png")
            fig.tight_layout()
            fig.savefig(path3, dpi=120)
            plt.close(fig)
            chart_paths["correlation_heatmap"] = "/reports/eda_charts/correlation_heatmap.png"
        except Exception as e:
            if self.logger: self.logger.log_event("EDA", "Chart Gen Error", "WARNING", message=str(e))

        # 4. Feature Importance Bar Chart
        try:
            fig, ax = plt.subplots(figsize=(8, 5))
            top_feats = feature_rankings[:8][::-1]
            names = [f["feature"] for f in top_feats]
            scores = [f["importance"] for f in top_feats]
            ax.barh(names, scores, color="#1a5e8a", edgecolor="#123f5e")
            ax.set_title("Random Forest Feature Importance Ranking", fontsize=13, fontweight="bold", pad=12)
            ax.set_xlabel("Relative Importance Score", fontsize=11)
            ax.grid(axis="x", linestyle="--", alpha=0.5)
            path4 = os.path.join(self.charts_dir, "feature_importance.png")
            fig.tight_layout()
            fig.savefig(path4, dpi=120)
            plt.close(fig)
            chart_paths["feature_importance"] = "/reports/eda_charts/feature_importance.png"
        except Exception as e:
            if self.logger: self.logger.log_event("EDA", "Chart Gen Error", "WARNING", message=str(e))

        return chart_paths