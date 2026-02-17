"""Vehicle scoring and ranking service."""


def score_vehicles(vehicles: list[dict], preferences: dict) -> list[dict]:
    """Score and rank vehicles based on user preferences.

    Scoring factors:
    - price_score: how close to user budget sweet spot (lower = better)
    - condition_score: mileage, known issues, age
    - distance_score: proximity to user zip code
    - feature_score: match against requested features

    Returns vehicles sorted by overall_score descending.
    """
    if not vehicles:
        return []

    prices = [v.get("price", 0) for v in vehicles]
    max_price = max(prices) if prices else 1
    min_price = min(prices) if prices else 0
    price_range = max_price - min_price or 1

    desired_features = set(preferences.get("features", []))

    scored = []
    for v in vehicles:
        price_score = 10.0 - ((v.get("price", 0) - min_price) / price_range) * 5

        max_mileage = preferences.get("max_mileage", 100_000) or 100_000
        mileage = v.get("mileage", 0) or 0
        condition_score = max(0.0, 10.0 - (mileage / max_mileage) * 5)

        vehicle_features = set(v.get("features", []))
        feature_overlap = len(vehicle_features & desired_features) if desired_features else 0
        feature_score = (feature_overlap / max(len(desired_features), 1)) * 10

        issues_count = len(v.get("known_issues", []))
        issue_penalty = min(issues_count * 1.5, 5.0)

        overall = round(
            (price_score * 0.35)
            + (condition_score * 0.25)
            + (feature_score * 0.25)
            + ((10.0 - issue_penalty) * 0.15),
            1,
        )

        v["price_score"] = round(price_score, 1)
        v["condition_score"] = round(condition_score, 1)
        v["overall_score"] = overall
        scored.append(v)

    scored.sort(key=lambda x: x["overall_score"], reverse=True)
    for idx, v in enumerate(scored):
        v["rank"] = idx + 1

    return scored


def pick_top_n(vehicles: list[dict], n: int = 4) -> list[dict]:
    """Return the top N vehicles by overall_score."""
    sorted_vehicles = sorted(vehicles, key=lambda x: x.get("overall_score", 0), reverse=True)
    return sorted_vehicles[:n]
