import math

KEEPS_TRANSFERS = {"wildcard", "freehit"}
POINTS_PER_HIT = 4


def selling_price(purchase: float, now: float, sell_on_fee: float) -> float:
    if now <= purchase:
        return now
    rise_tenths = round((now - purchase) * 10)
    kept_tenths = math.floor(rise_tenths * (1 - sell_on_fee) + 1e-9)
    return round(purchase + kept_tenths / 10, 1)


def purchase_prices(
    transfers: list[dict], free_hit_events: set[int]
) -> dict[int, float]:
    prices = {}
    for t in sorted(transfers, key=lambda t: t["time"]):
        if t["event"] not in free_hit_events:
            prices[t["element_in"]] = t["element_in_cost"] / 10
    return prices


def free_transfers(
    history: list[dict], chips: dict[int, str], pending: int, most: int
) -> int | None:
    if not history:
        return None
    available = None
    for week in history:
        if available is None:
            available = 1
            continue
        if chips.get(week["event"]) in KEEPS_TRANSFERS:
            continue
        used = week["event_transfers"]
        hits = week["event_transfers_cost"] // POINTS_PER_HIT
        if hits:
            available = used - hits
        available = min(most, max(available - used, 0) + 1)
    return max(available - pending, 0)


def chips_left(chips: list[dict], used: dict[int, str], gameweek: int) -> list[dict]:
    left = []
    for chip in chips:
        window = range(chip["start_event"], chip["stop_event"] + 1)
        played = any(
            name == chip["name"] and event in window for event, name in used.items()
        )
        if not played and gameweek <= chip["stop_event"]:
            left.append(
                {
                    "chip": chip["name"],
                    "from_gameweek": chip["start_event"],
                    "to_gameweek": chip["stop_event"],
                    "playable_now": gameweek in window,
                }
            )
    return left
