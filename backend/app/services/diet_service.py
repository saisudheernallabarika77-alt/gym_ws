"""
Fitora - Diet chart generation.

Builds a goal-appropriate calorie/macro target and a concrete Indian
(Andhra-leaning) meal chart that ships with the member's entry pass.

Formulas: Mifflin-St Jeor BMR -> TDEE via activity factor -> goal adjustment.
Macros follow standard sports-nutrition splits per goal.
"""
from __future__ import annotations
from typing import Any

ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}

# goal -> (calorie delta %, protein g/kg, fat % of calories)
GOAL_TUNING: dict[str, tuple[float, float, float]] = {
    "weight_loss":      (-0.20, 2.0, 0.25),
    "muscle_gain":      (+0.15, 1.8, 0.25),
    "strength":         (+0.10, 2.0, 0.28),
    "general_fitness":  (0.00, 1.6, 0.27),
    "endurance":        (+0.05, 1.5, 0.25),
    "rehabilitation":   (0.00, 1.7, 0.28),
}

GOAL_LABEL = {
    "weight_loss": "Weight Loss",
    "muscle_gain": "Muscle Gain",
    "strength": "Strength",
    "general_fitness": "General Fitness",
    "endurance": "Endurance",
    "rehabilitation": "Rehabilitation",
}


def compute_bmr(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
    """Mifflin-St Jeor."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + (5 if (gender or "").lower().startswith("m") else -161)


def compute_targets(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: str,
    goal: str,
    activity: str = "moderate",
) -> dict[str, Any]:
    bmr = compute_bmr(weight_kg, height_cm, age, gender)
    tdee = bmr * ACTIVITY_FACTORS.get(activity, 1.55)
    delta, protein_per_kg, fat_pct = GOAL_TUNING.get(goal, GOAL_TUNING["general_fitness"])

    calories = max(1200, round(tdee * (1 + delta)))
    protein_g = round(weight_kg * protein_per_kg)
    fats_g = round(calories * fat_pct / 9)
    carbs_g = max(50, round((calories - protein_g * 4 - fats_g * 9) / 4))

    bmi = weight_kg / ((height_cm / 100) ** 2)
    bmi_band = ("Underweight" if bmi < 18.5 else
                "Normal" if bmi < 25 else
                "Overweight" if bmi < 30 else "Obese")

    return {
        "bmr": round(bmr, 1),
        "tdee": round(tdee, 1),
        "target_calories": calories,
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fats_g": fats_g,
        "water_litres": round(max(2.5, weight_kg * 0.035), 1),
        "bmi": round(bmi, 1),
        "bmi_band": bmi_band,
        "activity_level": activity,
    }


# ------------------------------------------------------------------ meal sets
_MEALS: dict[str, dict[str, list[str]]] = {
    "weight_loss": {
        "Early Morning (6:00 AM)": [
            "Warm water with lemon + 5 soaked almonds",
            "Green tea (unsweetened) + 2 walnuts",
        ],
        "Breakfast (8:00 AM)": [
            "3 egg whites + 1 whole egg omelette with vegetables + 1 multigrain roti",
            "Vegetable upma (1 cup) + 1 cup low-fat curd",
            "2 idli with sambar (no coconut chutney) + 1 boiled egg",
        ],
        "Mid-Morning (11:00 AM)": [
            "1 apple or guava", "Buttermilk (1 glass, no sugar)", "Handful of roasted chana",
        ],
        "Lunch (1:30 PM)": [
            "1 cup brown rice + dal (1 cup) + mixed vegetable curry + salad + curd",
            "2 jowar roti + palak paneer (low oil) + cucumber salad",
            "1 cup rice + 150g grilled fish curry + sambar + salad",
        ],
        "Evening (5:00 PM)": [
            "Green tea + 2 whole wheat biscuits", "Sprouts salad (1 cup)",
            "Roasted makhana (1 cup)",
        ],
        "Post Workout (8:00 PM)": [
            "1 scoop whey protein in water", "3 boiled egg whites", "1 glass low-fat milk",
        ],
        "Dinner (9:00 PM)": [
            "2 multigrain roti + grilled chicken (120g) + sauteed vegetables",
            "Vegetable clear soup + paneer tikka (100g) + salad",
            "1 cup quinoa khichdi + curd + salad",
        ],
    },
    "muscle_gain": {
        "Early Morning (6:00 AM)": [
            "1 banana + 6 soaked almonds", "1 glass full-fat milk + 2 dates",
        ],
        "Breakfast (8:00 AM)": [
            "4 whole eggs + 3 slices brown bread + peanut butter + 1 banana",
            "3 paratha with paneer stuffing + curd + 1 glass milk",
            "Oats (80g) cooked in milk + whey scoop + banana + nuts",
        ],
        "Mid-Morning (11:00 AM)": [
            "Peanut butter sandwich (2 slices) + 1 glass milk",
            "Boiled chana (1.5 cups) + 1 banana",
            "Mass-gainer shake or 1 scoop whey + oats",
        ],
        "Lunch (1:30 PM)": [
            "2 cups rice + chicken curry (200g) + dal + curd + salad",
            "3 roti + 200g fish fry + dal + vegetable curry + curd",
            "2 cups rice + rajma (1.5 cups) + paneer bhurji (150g) + curd",
        ],
        "Evening (5:00 PM)": [
            "Sprouts chaat (1.5 cups) + 1 glass milk",
            "4 boiled eggs + 1 banana", "Peanut chikki + milk",
        ],
        "Post Workout (8:00 PM)": [
            "1.5 scoop whey protein + 1 banana",
            "5 boiled egg whites + 2 slices brown bread",
        ],
        "Dinner (9:30 PM)": [
            "3 roti + chicken breast (200g) + dal + vegetables",
            "2 cups rice + mutton curry (180g) + curd + salad",
            "3 roti + paneer (200g) + dal + vegetable curry",
        ],
        "Before Bed (11:00 PM)": [
            "1 glass full-fat milk + 1 tsp turmeric",
            "Casein shake or 1 cup curd with nuts",
        ],
    },
    "strength": {
        "Early Morning (6:00 AM)": ["6 soaked almonds + 1 banana", "Black coffee + 2 dates"],
        "Breakfast (8:00 AM)": [
            "4 whole eggs + 2 brown bread slices + 1 cup oats",
            "3 idli + sambar + 2 boiled eggs + 1 glass milk",
        ],
        "Mid-Morning (11:00 AM)": ["1 glass milk + peanut butter toast", "Boiled chana (1 cup)"],
        "Lunch (1:30 PM)": [
            "1.5 cups rice + chicken (200g) + dal + curd + salad",
            "3 roti + fish curry (180g) + dal + vegetables",
        ],
        "Evening (5:00 PM)": ["Sprouts (1 cup) + 1 glass milk", "3 boiled eggs"],
        "Post Workout (8:00 PM)": ["1 scoop whey + 1 banana", "4 egg whites + brown bread"],
        "Dinner (9:30 PM)": [
            "3 roti + paneer/chicken (180g) + dal + vegetables",
            "1.5 cups rice + mutton/fish (180g) + curd + salad",
        ],
        "Before Bed (11:00 PM)": ["1 glass milk", "1 cup curd with nuts"],
    },
    "general_fitness": {
        "Early Morning (6:30 AM)": ["Warm water + 5 almonds", "Green tea + 2 walnuts"],
        "Breakfast (8:00 AM)": [
            "2 idli + sambar + 1 boiled egg", "Vegetable upma + curd",
            "Oats with milk + banana + nuts",
        ],
        "Mid-Morning (11:00 AM)": ["1 seasonal fruit", "Buttermilk (1 glass)"],
        "Lunch (1:30 PM)": [
            "1 cup rice + dal + vegetable curry + curd + salad",
            "2 roti + chicken/paneer curry (150g) + salad",
        ],
        "Evening (5:00 PM)": ["Tea + roasted chana", "Sprouts salad"],
        "Post Workout (7:30 PM)": ["1 glass milk or 1 scoop whey", "2 boiled eggs"],
        "Dinner (9:00 PM)": [
            "2 roti + vegetable curry + dal + salad",
            "1 cup rice + fish/paneer (150g) + curd",
        ],
    },
    "endurance": {
        "Early Morning (5:30 AM)": ["1 banana + 1 glass water", "2 dates + black coffee"],
        "Breakfast (8:00 AM)": [
            "Oats (60g) with milk + banana + honey",
            "3 idli + sambar + 1 boiled egg",
        ],
        "Mid-Morning (11:00 AM)": ["Fruit bowl + curd", "Coconut water + handful of nuts"],
        "Lunch (1:30 PM)": [
            "1.5 cups rice + dal + vegetables + curd + salad",
            "3 roti + chicken (150g) + dal + salad",
        ],
        "Evening (5:00 PM)": ["Banana + peanut butter toast", "Sprouts + buttermilk"],
        "Post Workout (8:00 PM)": ["1 scoop whey + banana", "Milk + 2 dates"],
        "Dinner (9:00 PM)": [
            "2 roti + dal + vegetable curry + curd",
            "1 cup rice + fish (150g) + salad",
        ],
    },
    "rehabilitation": {
        "Early Morning (7:00 AM)": ["Warm water with turmeric + 5 almonds", "Green tea + walnuts"],
        "Breakfast (8:30 AM)": [
            "2 idli + sambar + 1 boiled egg", "Vegetable dalia + curd",
        ],
        "Mid-Morning (11:00 AM)": ["Papaya or orange", "Buttermilk with ginger"],
        "Lunch (1:30 PM)": [
            "1 cup rice + dal + soft vegetable curry + curd",
            "2 roti + paneer (120g) + vegetables + salad",
        ],
        "Evening (5:00 PM)": ["Vegetable soup", "Sprouts (soft cooked) + buttermilk"],
        "Post Workout (7:30 PM)": ["1 glass milk with turmeric", "2 boiled eggs"],
        "Dinner (8:45 PM)": [
            "2 roti + dal + steamed vegetables + curd",
            "Khichdi (1.5 cups) + curd + salad",
        ],
    },
}

_TIPS: dict[str, list[str]] = {
    "weight_loss": [
        "Keep a 400-500 kcal daily deficit - faster cuts burn muscle, not just fat.",
        "Finish dinner at least 2 hours before sleeping.",
        "Avoid sugar, fried snacks, soft drinks and packaged juices completely.",
        "Walk 8,000-10,000 steps on top of your gym session.",
        "Weigh yourself once a week, same time, empty stomach - not daily.",
    ],
    "muscle_gain": [
        "Eat every 2.5-3 hours; never train fasted.",
        "Hit your protein target every single day - it is non-negotiable.",
        "Add 300-400 kcal above maintenance; more than that is fat, not muscle.",
        "Sleep 7-8 hours - muscle is built during recovery, not in the gym.",
        "Track your lifts weekly; if the weight is not going up, eat more.",
    ],
    "strength": [
        "Prioritise compound lifts: squat, deadlift, bench, overhead press.",
        "Keep protein at 2g per kg bodyweight daily.",
        "Carb-load 90 minutes before heavy sessions.",
        "Deload every 5-6 weeks to avoid joint burnout.",
    ],
    "general_fitness": [
        "Aim for 4-5 gym sessions a week with 1 full rest day.",
        "Half your plate should be vegetables at lunch and dinner.",
        "Drink water through the day, not all at once.",
        "Limit outside food to once a week.",
    ],
    "endurance": [
        "Carbs fuel endurance - do not cut them.",
        "Hydrate before, during and after every session.",
        "Add electrolytes for sessions over 60 minutes.",
        "Include 2 strength sessions a week to protect your joints.",
    ],
    "rehabilitation": [
        "Follow your physiotherapist's load limits strictly.",
        "Anti-inflammatory foods help: turmeric, ginger, omega-3 rich fish.",
        "Never train through sharp pain - stop and report it.",
        "Progress slowly; consistency beats intensity during recovery.",
    ],
}

_AVOID = [
    "Deep-fried snacks (samosa, mirchi bajji, pakoda)",
    "Sugary drinks, packaged fruit juices and energy drinks",
    "Bakery items - puffs, cream biscuits, cakes",
    "Excess white rice at night",
    "Alcohol and smoking",
]


def build_diet_chart(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: str,
    goal: str,
    activity: str = "moderate",
    target_weight_kg: float | None = None,
) -> dict[str, Any]:
    goal = goal if goal in GOAL_TUNING else "general_fitness"
    targets = compute_targets(weight_kg, height_cm, age, gender, goal, activity)
    meals = _MEALS.get(goal, _MEALS["general_fitness"])

    chart = {
        slot: {"options": options, "pick": options[0]}
        for slot, options in meals.items()
    }

    weeks_estimate = None
    if target_weight_kg and target_weight_kg != weight_kg:
        diff = abs(weight_kg - target_weight_kg)
        rate = 0.5 if goal == "weight_loss" else 0.25   # kg per week
        weeks_estimate = round(diff / rate)

    return {
        "goal": goal,
        "goal_label": GOAL_LABEL[goal],
        **targets,
        "current_weight_kg": weight_kg,
        "target_weight_kg": target_weight_kg,
        "estimated_weeks_to_target": weeks_estimate,
        "chart": chart,
        "tips": _TIPS.get(goal, _TIPS["general_fitness"]),
        "avoid": _AVOID,
        "disclaimer": (
            "This chart is a general guideline generated from your height, weight, age and goal. "
            "Consult a doctor or registered dietitian before starting, especially if you have "
            "a medical condition, allergy or are on medication."
        ),
    }
