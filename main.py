import argparse
import sys
from src.scraper.engine import IndeedScraper
from src.login import IndeedSessionManager
from src.applier import AutoApplier

def main():
    parser = argparse.ArgumentParser(description="Indeed Job Automation Suite")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Login Command
    login_parser = subparsers.add_parser("login", help="Log in to Indeed and save session")
    
    # Scrape Command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape jobs from Indeed")
    scrape_parser.add_argument("-q", "--query", default="Python Developer", help="Search query")
    scrape_parser.add_argument("-l", "--location", default="Remote", help="Location")
    scrape_parser.add_argument("-n", "--limit", type=int, default=10, help="Max jobs to scrape")
    scrape_parser.add_argument("--days", type=int, default=None, help="Filter by date posted (days)")
    scrape_parser.add_argument("--headed", action="store_true", help="Run with visible browser window")
    scrape_parser.add_argument("--db", action="store_true", default=True, help="Save to SQLite database (default: True)")

    # Apply Command
    apply_parser = subparsers.add_parser("apply", help="Automate job applications")
    apply_parser.add_argument("-n", "--limit", type=int, default=5, help="Max applications to submit")
    apply_parser.add_argument("--headed", action="store_true", help="Run with visible browser window")

    args = parser.parse_args()

    if args.command == "login":
        manager = IndeedSessionManager()
        manager.login_and_save()
    
    elif args.command == "scrape":
        scraper = IndeedScraper(headless=not args.headed)
        try:
            scraper.scrape(args.query, args.location, limit=args.limit, days=args.days, use_db=args.db)
            scraper.save_data()
        except KeyboardInterrupt:
            print("\nInterrupted.")
        finally:
            print("\n✅ Scraping session complete.")

    elif args.command == "apply":
        applier = AutoApplier(headless=not args.headed)
        try:
            applier.run(limit=args.limit)
        except KeyboardInterrupt:
            print("\nInterrupted.")
        finally:
            print("\n✅ Application session complete.")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
