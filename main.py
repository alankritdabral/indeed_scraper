import argparse
import sys
import time
from scrapling.fetchers import StealthySession
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
    scrape_parser.add_argument("--easy-apply", action="store_true", help="Only scrape jobs that have 'Easily apply' label")

    # Apply Command
    apply_parser = subparsers.add_parser("apply", help="Automate 'Easy Apply' job applications")
    apply_parser.add_argument("-n", "--limit", type=int, default=5, help="Max Easy Apply applications to submit")
    apply_parser.add_argument("--headed", action="store_true", help="Run with visible browser window")

    # Continuous Command
    continuous_parser = subparsers.add_parser("continuous", help="Loop scraping and applying indefinitely")
    continuous_parser.add_argument("-q", "--query", default="Python Developer", help="Search query")
    continuous_parser.add_argument("-l", "--location", default="Remote", help="Location")
    continuous_parser.add_argument("-n", "--limit", type=int, default=10, help="Batch size for each cycle")
    continuous_parser.add_argument("--headed", action="store_true", help="Run with visible browser window")
    continuous_parser.add_argument("--easy-apply", action="store_true", help="Only scrape jobs that have 'Easily apply' label")

    args = parser.parse_args()

    if args.command == "login":
        manager = IndeedSessionManager()
        manager.login_and_save()
    
    elif args.command == "scrape":
        scraper = IndeedScraper(headless=not args.headed)
        try:
            scraper.scrape(args.query, args.location, limit=args.limit, days=args.days, use_db=args.db, easy_apply_only=args.easy_apply)
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
    
    elif args.command == "continuous":
        print(f"🔄 Starting continuous mode for '{args.query}' in '{args.location}'...")
        
        # Create a persistent session for continuous mode to satisfy "dont close the browser"
        shared_session = StealthySession(headless=not args.headed)
        shared_session.start()
        
        try:
            while True:
                try:
                    # 1. Scrape
                    print("\n--- 🕵️ Scraping Phase ---")
                    scraper = IndeedScraper(headless=not args.headed, session=shared_session)
                    scraper.scrape(args.query, args.location, limit=args.limit, use_db=True, easy_apply_only=args.easy_apply)

                    # 2. Apply
                    print("\n--- ⚡ Application Phase ---")
                    applier = AutoApplier(headless=not args.headed, session=shared_session)
                    applier.run(limit=args.limit)
                    
                    print("\n💤 Cycle complete. Resting for 2 minutes...")
                    time.sleep(120)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"\n❌ Error in continuous cycle: {e}")
                    time.sleep(60)
        except KeyboardInterrupt:
            print("\n👋 Continuous mode stopped by user.")
        finally:
            shared_session.close()
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
