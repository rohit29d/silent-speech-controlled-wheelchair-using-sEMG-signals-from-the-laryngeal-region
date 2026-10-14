from configs.settings import FEATURE_CSV_FILENAME, VALID_LABELS
from src.models.results_visualization import (
    plot_class_distribution,
    plot_confusion_matrix,
    plot_feature_importance,
    print_classification_report,
)
from src.models.train_classifier import train_random_forest_classifier


def main():
    results = train_random_forest_classifier(FEATURE_CSV_FILENAME)
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
        results["y_all_labels"],
        title="Entire Dataset Class Distribution",
        filename="class_distribution_entire_dataset.png",
    )
    print_classification_report(results["y_test_labels"], results["y_pred_labels"], VALID_LABELS)


if __name__ == "__main__":
    main()
