"""
Predefined simulation scenarios.

Each scenario defines weather and load parameters representing
a specific operating condition for testing and evaluation.
"""

from dataclasses import dataclass
from .profiles import WeatherParams, LoadParams


@dataclass
class Scenario:
    """A named combination of weather + load parameters."""
    name: str
    description: str
    weather: WeatherParams
    load: LoadParams


# ── Scenario catalog ──────────────────────────────────────────

SUNNY_SUMMER = Scenario(
    name="sunny_summer",
    description="Clear summer day in Meknès. High irradiance, AC active.",
    weather=WeatherParams(
        cloud_factor=0.0,
        temp_min_c=22.0,
        temp_max_c=38.0,
        humidity_min_pct=20.0,
        humidity_max_pct=50.0,
    ),
    load=LoadParams(
        load_multiplier=1.0,
        ac_active=True,
        is_weekend=False,
    ),
)

CLOUDY_WINTER = Scenario(
    name="cloudy_winter",
    description="Overcast winter day. Low PV output, no AC, higher heating-related load.",
    weather=WeatherParams(
        cloud_factor=0.7,
        temp_min_c=5.0,
        temp_max_c=14.0,
        humidity_min_pct=50.0,
        humidity_max_pct=85.0,
    ),
    load=LoadParams(
        load_multiplier=1.2,
        ac_active=False,
        is_weekend=False,
    ),
)

HIGH_DEMAND = Scenario(
    name="high_demand",
    description="Sunny day with unusually high consumption (guests, appliances).",
    weather=WeatherParams(
        cloud_factor=0.0,
        temp_min_c=24.0,
        temp_max_c=40.0,
        humidity_min_pct=15.0,
        humidity_max_pct=45.0,
    ),
    load=LoadParams(
        load_multiplier=1.5,
        ac_active=True,
        is_weekend=False,
    ),
)

LOW_DEMAND_WEEKEND = Scenario(
    name="low_demand_weekend",
    description="Sunny weekend with low consumption (family away).",
    weather=WeatherParams(
        cloud_factor=0.1,
        temp_min_c=20.0,
        temp_max_c=32.0,
        humidity_min_pct=25.0,
        humidity_max_pct=55.0,
    ),
    load=LoadParams(
        load_multiplier=0.6,
        ac_active=False,
        is_weekend=True,
    ),
)

PARTLY_CLOUDY = Scenario(
    name="partly_cloudy",
    description="Variable cloud cover, moderate temperature.",
    weather=WeatherParams(
        cloud_factor=0.4,
        temp_min_c=18.0,
        temp_max_c=30.0,
        humidity_min_pct=30.0,
        humidity_max_pct=65.0,
    ),
    load=LoadParams(
        load_multiplier=1.0,
        ac_active=True,
        is_weekend=False,
    ),
)

SPRING_MILD = Scenario(
    name="spring_mild",
    description="Mild spring day with moderate irradiance.",
    weather=WeatherParams(
        cloud_factor=0.2,
        temp_min_c=14.0,
        temp_max_c=26.0,
        humidity_min_pct=30.0,
        humidity_max_pct=60.0,
    ),
    load=LoadParams(
        load_multiplier=0.9,
        ac_active=False,
        is_weekend=False,
    ),
)

# Ordered list for iteration
ALL_SCENARIOS = [
    SUNNY_SUMMER,
    CLOUDY_WINTER,
    HIGH_DEMAND,
    LOW_DEMAND_WEEKEND,
    PARTLY_CLOUDY,
    SPRING_MILD,
]

SCENARIO_MAP = {s.name: s for s in ALL_SCENARIOS}
