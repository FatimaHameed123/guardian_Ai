"""CLI helper for structured crime-likelihood predictions."""

from __future__ import annotations

import argparse
import json

from integration import predict_crime_likelihood


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict crime likelihood (0/1)")
    parser.add_argument("--crime-type", required=True)
    parser.add_argument("--area", required=True)
    parser.add_argument("--latitude", type=float, required=True)
    parser.add_argument("--longitude", type=float, required=True)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--hour", type=int, default=12)
    parser.add_argument("--day-of-week", type=int, default=2)
    parser.add_argument("--month", type=int, default=4)
    args = parser.parse_args()

    result = predict_crime_likelihood(
        crime_type=args.crime_type,
        area=args.area,
        latitude=args.latitude,
        longitude=args.longitude,
        year=args.year,
        hour=args.hour,
        day_of_week=args.day_of_week,
        month=args.month,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
