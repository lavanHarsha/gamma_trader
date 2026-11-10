import sys
import os
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.orchestrator import SystemOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("FullTrainScript")

def main():
    logger.info("Initializing Gamma_trader-Web Full Year Ingestion & Meta-Labeling...")
    orch = SystemOrchestrator()
    
    # 1. Download 1-year historical bars (365 days)
    logger.info("Downloading 365 days of 15m intraday bars for all 10 stocks & indices from Groww...")
    download_stats = orch.download_historical_data(days=365, interval_min=15)
    logger.info(f"Historical Download Summary: {download_stats}")

    # 2. Run full training pipeline
    logger.info("Running Feature Engineering, Stage-1 Candlestick Scanning, Triple-Barrier Labeling & Walk-Forward Training...")
    report = orch.run_training_pipeline()
    logger.info("TRAINING COMPLETE!")
    logger.info(f"OOS Performance Tear Sheet: {report.get('overall_oos_metrics')}")

if __name__ == "__main__":
    main()

