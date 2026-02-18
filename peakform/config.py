"""Static user profile and configuration constants for PeakForm."""

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List

# ---------------------------------------------------------------------------
# User Profile
# ---------------------------------------------------------------------------

USER_NAME = "Ben"
USER_DOB = date(1990, 6, 13)
USER_HEIGHT_CM = 175.26
GOAL_WEIGHT_LBS = 160.0
GOAL_RATE_PCT_PER_WEEK = 1.55  # % of body weight per week

# Key timeline milestones
MILESTONE_AESTHETIC = date(2026, 5, 1)
MILESTONE_EUROPE_TRIP_START = date(2026, 6, 1)
MILESTONE_14ER_SEASON = date(2026, 6, 15)

# Tracking restart date (3-month gap ended here)
TRACKING_RESTART = date(2026, 2, 16)
TRACKING_GAP_START = date(2025, 11, 8)
TRACKING_GAP_END = date(2026, 2, 15)

# ---------------------------------------------------------------------------
# Nutrition baseline targets (as of Feb 16 2026 from MacroFactor)
# Note: always use live targets from Nutrition Program Settings sheet when
# available — these are fallback defaults.
# ---------------------------------------------------------------------------

FALLBACK_CALORIE_TARGET = 1377
FALLBACK_PROTEIN_TARGET_G = 153
FALLBACK_CARBS_TARGET_G = 87
FALLBACK_FAT_TARGET_G = 45
FALLBACK_EXPENDITURE_KCAL = 2009

# ---------------------------------------------------------------------------
# Nutrition thresholds
# ---------------------------------------------------------------------------

FIBER_TARGET_G = 25
PROTEIN_PRESERVATION_MIN_G = 140  # below this: muscle preservation concern
CARBS_UNDERFUEL_MIN_G = 80        # below this while running >30mi: underfueling
CALORIE_ADHERENCE_WINDOW_KCAL = 100  # ±100 kcal = "on target"
CALORIE_VARIANCE_CONCERN_STDEV = 300  # std dev > 300 = inconsistent

# ---------------------------------------------------------------------------
# Running thresholds
# ---------------------------------------------------------------------------

TRAIL_RUN_ASCENT_FT = 500         # total ascent > 500ft → trail/mountain run
MILEAGE_OVERREACH_PCT = 0.10      # >10% above 4-week avg → injury risk flag
BODY_BATTERY_DRAIN_CONCERN = 15   # avg drain > 15 → recovery debt
GROUND_CONTACT_CONCERN_MS = 5     # trending up > 5ms over 3 weeks → flag

# Running activity type strings (as they appear in Garmin CSV)
RUNNING_ACTIVITY_TYPES = {"Running", "Treadmill Running", "Trail Running"}
STRENGTH_ACTIVITY_TYPES = {
    "Strength Training", "Gym", "Indoor Rowing", "Cycling", "Indoor Cycling"
}

# ---------------------------------------------------------------------------
# Feb 2026 strength program — expected muscle groups
# ---------------------------------------------------------------------------

FEB_2026_PROGRAM = {
    "Lower Body + Core": [
        "Goblet Squat",
        "Romanian Deadlift",
        "Walking Lunge",
        "Glute Bridge",
        "Banded Clamshell",
        "Step-Up",
        "Forearm Plank",
        "Dead Bug",
    ],
    "Upper Body + Core": [
        "Dumbbell Bench Press",
        "Bent-Over Row",
        "Overhead Press",
        "Band Pull-Apart",
        "Biceps Curl",
        "Push-Up",
        "Pallof Press",
        "Double Leg Raise",
    ],
    "Morning Calisthenics": [
        "Kneeling Push-Up",
        "Sit-Up",
        "Bodyweight Squat",
    ],
}

# Muscle groups most critical to monitor (running injury prevention)
PRIORITY_MUSCLE_GROUPS = ["Glutes", "Hips", "Core", "Hamstrings"]

# ---------------------------------------------------------------------------
# Established meal rotation (verified macros)
# ---------------------------------------------------------------------------

@dataclass
class MealEntry:
    name: str
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    servings_per_batch: int = 1
    notes: str = ""


MEAL_ROTATION: List[MealEntry] = [
    MealEntry(
        name="Yogurt PB Protein Bowl",
        kcal=352,
        protein_g=51,
        carbs_g=30,
        fat_g=3,
        servings_per_batch=1,
        notes="Breakfast / snack",
    ),
    MealEntry(
        name="Vegetarian Creole Jambalaya",
        kcal=641,
        protein_g=31,
        carbs_g=100,
        fat_g=10,
        servings_per_batch=7,
        notes="Higher carb — good on heavy run days",
    ),
    MealEntry(
        name="Tofu Broccoli Parm",
        kcal=474,
        protein_g=35,
        carbs_g=60,
        fat_g=12,
        servings_per_batch=7,
        notes="Balanced — good default dinner",
    ),
    MealEntry(
        name="Pre-Run Snack (rice cake + PB + honey)",
        kcal=175,
        protein_g=4,
        carbs_g=20,
        fat_g=9,
        servings_per_batch=1,
        notes="Pre-run fuel",
    ),
    MealEntry(
        name="Banana Bread (oats/banana/egg/cinnamon)",
        kcal=135,
        protein_g=5,
        carbs_g=22,
        fat_g=3,
        servings_per_batch=1,
        notes="Light snack / morning option",
    ),
]
