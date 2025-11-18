import sys
import os
from launcher import Launcher

def main():
    # Optionally accept participant name and duration from command line
    import argparse
    parser = argparse.ArgumentParser(description="Run Reading Task Only")
    parser.add_argument('--name', type=str, default="TestSubject", help="Participant name")
    parser.add_argument('--duration', type=int, default=5, help="Duration in minutes")
    args = parser.parse_args()

    app = Launcher()
    duration_seconds = args.duration * 60
    app._run_reading_task(name=args.name, duration_seconds=duration_seconds)

if __name__ == "__main__":
    main()
