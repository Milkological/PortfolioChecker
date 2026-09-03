import sys

from portfolio_checker import cli

if __name__ == "__main__":
    holdings_file = sys.argv[1] if len(sys.argv) > 1 else None
    cli.run(holdings_file=holdings_file)
