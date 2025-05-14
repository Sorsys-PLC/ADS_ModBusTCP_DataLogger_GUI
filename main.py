import logging
import argparse
from tcp_logger import start_tcp_logging
from utils import initialize_db

# Logger setup
log_file = os.path.join(os.environ["USERPROFILE"], "Documents", "PLC_Logs", "logger.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, mode='a'),
        logging.StreamHandler()
    ]
)


def main():
    parser = argparse.ArgumentParser(description="Unified PLC Data Logger")
    parser.add_argument('--tcp', action='store_true', help="Enable TCP Modbus Logging")
    parser.add_argument('--ads', action='store_true', help="Enable ADS Data Pull")
    args = parser.parse_args()

    if args.tcp:
        initialize_db("TCP")
        logging.info("Starting TCP Modbus Logging...")
        start_tcp_logging()

    elif args.ads:
        from ads_data_pull import start_ads_data_pull  # ← import only if needed
        initialize_db("ADS")
        logging.info("Starting ADS Data Pull...")
        start_ads_data_pull()

    else:
        logging.error("No mode specified. Use --tcp or --ads.")
        parser.print_help()

if __name__ == "__main__":
    main()
