"""Entry point for the JHive development application."""

import logging


def main() -> None:
    """Run the safe starter command without connecting to a broker or market feed."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("JHive is ready for development; no live market data or trading is enabled.")


if __name__ == "__main__":
    main()
