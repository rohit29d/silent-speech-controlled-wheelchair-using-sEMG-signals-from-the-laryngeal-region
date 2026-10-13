import argparse

from configs.settings import OFFLINE_SUMMARY_FILENAME, RT_CONFIDENCE_THRESH
from src.inference.offline_inference_report import run_offline_inference_report
from src.inference.realtime_testing import main_menu as realtime_main
from src.models.train_classifier import main as train_main
from src.models.train_classifier_entire_dataset import main as train_entire_main
from src.utils.demo_samples import main as demo_samples_main


def main():
    parser = argparse.ArgumentParser(description="Speech recognition pipeline entry point.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("train")
    subparsers.add_parser("train-entire-dataset")
    subparsers.add_parser("realtime")
    subparsers.add_parser("demo-samples")

    infer_parser = subparsers.add_parser("infer-offline")
    infer_parser.add_argument("csv_path", nargs="?", default=None)
    infer_parser.add_argument("--n-windows", type=int, default=None)
    infer_parser.add_argument("--conf-threshold", type=float, default=RT_CONFIDENCE_THRESH)
    infer_parser.add_argument("--output", default=OFFLINE_SUMMARY_FILENAME)

    args = parser.parse_args()

    if args.command == "train":
        train_main()
    elif args.command == "train-entire-dataset":
        train_entire_main()
    elif args.command == "realtime":
        realtime_main()
    elif args.command == "demo-samples":
        demo_samples_main()
    elif args.command == "infer-offline":
        csv_path = args.csv_path or input("Enter CSV file path: ").strip().strip('"')
        if not csv_path:
            print("No CSV path provided. Exiting.")
            return
        out_csv = run_offline_inference_report(
            csv_path=csv_path,
            n_windows=args.n_windows,
            confidence_threshold=args.conf_threshold,
            out_csv=args.output,
        )
        print(f"Saved summary: {out_csv}")


if __name__ == "__main__":
    main()
