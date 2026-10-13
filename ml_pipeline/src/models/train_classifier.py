import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

from configs.settings import (
    FEATURE_CSV_FILENAME,
    LABEL_ENCODER_FILENAME,
    METADATA_FILENAME,
    MODEL_FILENAME,
    N_FEATURES_SELECTED,
    OUTPUT_DIR,
    RANDOM_SEED,
    RF_CONFIG,
    SCALER_FILENAME,
    SELECTOR_FILENAME,
    TEST_SIZE,
    VALID_LABELS,
)
from src.models.results_visualization import (
    plot_class_distribution,
    plot_confusion_matrix,
    plot_feature_importance,
    print_classification_report,
)


def select_features_kbest(X_train, y_train, X_test, feature_names, k="auto"):
    selector_full = SelectKBest(score_func=f_classif, k="all")
    selector_full.fit(X_train, y_train)
    f_scores = selector_full.scores_
    p_values = selector_full.pvalues_

    print("\n" + "=" * 80)
    print("FEATURE SIGNIFICANCE (ANOVA F-test)")
    print("=" * 80)
    print(f"\n{'Rank':<6}{'Feature':<30}{'F-score':<15}{'p-value':<15}")
    print("-" * 80)
    for rank, idx in enumerate(np.argsort(f_scores)[::-1][:10], start=1):
        sig = "YES" if p_values[idx] < 0.05 else "NO"
        print(f"{rank:<6}{feature_names[idx]:<30}{f_scores[idx]:<15.4f}{p_values[idx]:<15.2e} {sig}")

    if k == "auto":
        k = N_FEATURES_SELECTED

    selector = SelectKBest(score_func=f_classif, k=k)
    X_train_sel = selector.fit_transform(X_train, y_train)
    X_test_sel = selector.transform(X_test)
    selected_names = np.array(feature_names)[selector.get_support()].tolist()
    return X_train_sel, X_test_sel, selector, selected_names


def train_random_forest_classifier(csv_filename: str = FEATURE_CSV_FILENAME):
    csv_path = Path(csv_filename)
    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} not found. Run feature extraction first.")

    df = pd.read_csv(csv_path)
    feature_cols = [col for col in df.columns if col not in ["Label", "Subject"]]
    feature_names = np.array(feature_cols)
    X_all = df[feature_cols].values.astype(np.float32)
    y_all = df["Label"].values

    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y_all)

    X_train_raw, X_test_raw, y_train, y_test = train_test_split(
        X_all,
        y_encoded,
        test_size=TEST_SIZE,
        stratify=y_encoded,
        random_state=RANDOM_SEED,
    )

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train_raw)
    X_test = scaler.transform(X_test_raw)
    X_train_sel, X_test_sel, selector, selected_names = select_features_kbest(
        X_train,
        y_train,
        X_test,
        feature_names,
        k="auto",
    )

    rf = RandomForestClassifier(**RF_CONFIG)
    rf.fit(X_train_sel, y_train)
    y_pred = rf.predict(X_test_sel)

    y_test_labels = label_encoder.inverse_transform(y_test)
    y_pred_labels = label_encoder.inverse_transform(y_pred)
    test_acc = accuracy_score(y_test, y_pred)
    test_f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)

    print(classification_report(y_test_labels, y_pred_labels, zero_division=0))

    cv_splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    cv_scores = cross_val_score(rf, X_train_sel, y_train, cv=cv_splitter, scoring="accuracy", n_jobs=-1)

    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(rf, output_dir / MODEL_FILENAME)
    joblib.dump(scaler, output_dir / SCALER_FILENAME)
    joblib.dump(label_encoder, output_dir / LABEL_ENCODER_FILENAME)

    selector_info = {
        "mask": selector.get_support().tolist(),
        "selected_features": selected_names,
        "all_features": feature_names.tolist(),
        "n_features_selected": len(selected_names),
        "n_features_total": len(feature_names),
    }
    joblib.dump(selector_info, output_dir / SELECTOR_FILENAME)

    metadata = {
        "model_type": "RandomForest",
        "n_estimators": RF_CONFIG["n_estimators"],
        "max_depth": RF_CONFIG["max_depth"],
        "n_features_selected": len(selected_names),
        "n_features_total": len(feature_names),
        "n_classes": len(label_encoder.classes_),
        "classes": label_encoder.classes_.tolist(),
        "test_accuracy": float(test_acc),
        "test_f1_score": float(test_f1),
        "cv_mean_accuracy": float(cv_scores.mean()),
        "cv_std_accuracy": float(cv_scores.std()),
        "selected_features": selected_names,
        "random_state": RANDOM_SEED,
        "training_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
    }
    with (output_dir / METADATA_FILENAME).open("w", encoding="utf-8") as file_obj:
        json.dump(metadata, file_obj, indent=4)

    return {
        "model": rf,
        "selected_names": selected_names,
        "y_test_labels": y_test_labels,
        "y_pred_labels": y_pred_labels,
        "y_all_labels": y_all,
        "test_accuracy": test_acc,
        "test_f1_score": test_f1,
        "cv_scores": cv_scores,
        "confusion_matrix": confusion_matrix(y_test, y_pred),
    }


def main():
    results = train_random_forest_classifier()
    plot_confusion_matrix(
        results["y_test_labels"],
        results["y_pred_labels"],
        VALID_LABELS,
        title="Random Forest - Test Set",
        filename="confusion_matrix_rf.png",
    )
    plot_feature_importance(
        results["model"],
        results["selected_names"],
        top_n=15,
        filename="feature_importance_rf.png",
    )
    plot_class_distribution(
        results["y_test_labels"],
        title="Test Set Class Distribution",
        filename="class_distribution_test.png",
    )
    print_classification_report(results["y_test_labels"], results["y_pred_labels"], VALID_LABELS)


if __name__ == "__main__":
    main()
