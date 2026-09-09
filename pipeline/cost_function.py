"""
CicloConecta — Cycling Cost Function and Navigability Rules.

Defines explicit, deterministic penalty factors for routing on real OpenStreetMap data.
Costs follow the principle:
    cost = length_meters * penalty_factor

A lower penalty factor means a higher preference for cycling infrastructure.
Blocked roads (e.g. motorways, access=no, bicycle=no) return is_cyclable=False.
"""

from typing import Any, Optional


# Minimum possible penalty factor in the system (used for admissible A* heuristic)
MIN_PENALTY_FACTOR: float = 0.70

# Base highway penalty table for roads WITHOUT dedicated cycling infrastructure
# Calm local streets have ~1.0, major roads without infrastructure have high penalties
BASE_HIGHWAY_PENALTIES: dict[str, float] = {
    "cycleway": 0.75,          # Protected dedicated cycleway
    "path": 0.90,              # Generic path (often shared with pedestrians)
    "living_street": 0.95,      # Calmed residential street (pedestrians/bikes priority)
    "residential": 1.05,       # Typical residential street
    "unclassified": 1.10,      # Minor local connector
    "service": 1.15,           # Service alley or driveway
    "pedestrian": 1.20,        # Pedestrian mall (if bicycle allowed)
    "track": 1.25,             # Agricultural / unpaved track
    "tertiary": 1.45,          # Urban collector street
    "tertiary_link": 1.50,
    "secondary": 1.90,         # Arterial street with moderate/heavy vehicular traffic
    "secondary_link": 1.95,
    "primary": 2.60,           # Major arterial without bike infrastructure (dangerous)
    "primary_link": 2.65,
    "trunk": 3.80,             # Urban highway / express road (avoid unless explicit bicycle=yes)
    "trunk_link": 3.90,
}

# Highway types strictly prohibited for bicycles unless explicit bicycle=yes
MOTORWAY_HIGHWAYS: set[str] = {"motorway", "motorway_link"}


def evaluate_edge_cycling_cost(tags: dict[str, Any]) -> tuple[bool, float, str, str]:
    """
    Evaluates an OSM road segment for bicycle transitability and cost penalty.

    Returns:
        (is_cyclable: bool,
         penalty_factor: float,
         category: str,
         infrastructure_label: str)
    """
    highway = tags.get("highway", "")

    # 1. Prohibited highway types
    if highway in MOTORWAY_HIGHWAYS:
        return False, float("inf"), "blocked", "Autopista vehicular no permitida"

    # 2. General access restrictions
    access = tags.get("access", "").lower()
    bicycle = tags.get("bicycle", "").lower()

    if access in ("no", "private") and bicycle not in ("yes", "designated", "permissive"):
        return False, float("inf"), "blocked", "Acceso prohibido"

    if bicycle in ("no", "use_sidepath"):
        return False, float("inf"), "blocked", "Prohibido para bicicletas"

    # 3. Check for dedicated cycling infrastructure on this way
    has_cycleway = any(
        k.startswith("cycleway")
        and v in ("track", "lane", "opposite_track", "opposite_lane", "share_busway", "yes")
        for k, v in tags.items()
    ) or highway == "cycleway"

    segregated = tags.get("segregated") == "yes"
    is_designated = bicycle == "designated"

    # Category A: Dedicated Cycleway or Protected Track (Muy Preferida: 0.70 - 0.85)
    if highway == "cycleway" or tags.get("cycleway") == "track" or any(
        tags.get(f"cycleway:{side}") == "track" for side in ("left", "right", "both")
    ):
        penalty = 0.70 if segregated else 0.78
        label = "Ciclovía segregada protegida" if segregated else "Ciclovía dedicada"
        return True, penalty, "dedicated_cycleway", label

    # Category B: On-Street Cycle Lane or Designated Route (Preferida: 0.85 - 0.95)
    if has_cycleway or is_designated:
        penalty = 0.88
        label = "Ciclobanda demarcada" if has_cycleway else "Vía con preferencia ciclista"
        return True, penalty, "cycle_lane", label

    # 4. Standard roads without dedicated cycling infrastructure
    if highway not in BASE_HIGHWAY_PENALTIES:
        # Unknown minor road: treat conservatively as normal street
        base_penalty = 1.15
        label = f"Vía urbana ({highway or 'general'})"
    else:
        base_penalty = BASE_HIGHWAY_PENALTIES[highway]
        label = f"Calle vehicular ({highway})"

    penalty = base_penalty

    # Adjustments based on speed limit
    maxspeed_str = tags.get("maxspeed", "")
    try:
        maxspeed = float("".join(c for c in maxspeed_str if c.isdigit() or c == "."))
        if maxspeed <= 30:
            penalty *= 0.90  # Calmed 30 km/h zone
        elif maxspeed >= 60:
            penalty += 0.40  # High speed vehicular traffic
        elif maxspeed >= 50:
            penalty += 0.20
    except (ValueError, TypeError):
        pass

    # Adjustments based on number of lanes
    lanes_str = tags.get("lanes", "")
    try:
        lanes = int("".join(c for c in lanes_str if c.isdigit()))
        if lanes >= 4:
            penalty += 0.50
        elif lanes >= 3:
            penalty += 0.25
    except (ValueError, TypeError):
        pass

    # Surface adjustments (unpaved vs smooth asphalt)
    surface = tags.get("surface", "").lower()
    if surface in ("unpaved", "gravel", "ground", "dirt", "compacted"):
        penalty += 0.35  # Rough surface penalty

    category = "arterial_street" if base_penalty >= 1.8 else "local_street"
    return True, round(penalty, 3), category, label


def is_oneway_for_bicycle(tags: dict[str, Any]) -> tuple[bool, bool]:
    """
    Evaluates oneway directionality specifically for bicycles.

    Returns:
        (forward_allowed: bool, backward_allowed: bool)
    """
    oneway = tags.get("oneway", "").lower()
    oneway_bicycle = tags.get("oneway:bicycle", "").lower()
    cycleway = tags.get("cycleway", "").lower()
    cycleway_left = tags.get("cycleway:left", "").lower()
    cycleway_right = tags.get("cycleway:right", "").lower()

    # Explicit bicycle oneway tag takes precedence
    if oneway_bicycle in ("no", "0", "false"):
        return True, True
    if oneway_bicycle in ("yes", "1", "true"):
        return True, False
    if oneway_bicycle in ("-1", "reverse"):
        return False, True

    # Contraflow cycleways allow reverse bicycle transit on oneway streets
    has_contraflow = (
        cycleway in ("opposite", "opposite_lane", "opposite_track")
        or cycleway_left in ("opposite", "opposite_lane", "opposite_track")
        or cycleway_right in ("opposite", "opposite_lane", "opposite_track")
    )
    if has_contraflow:
        return True, True

    # Standard oneway evaluation
    if oneway in ("yes", "1", "true"):
        return True, False
    if oneway in ("-1", "reverse"):
        return False, True

    # Bidirectional by default
    return True, True
