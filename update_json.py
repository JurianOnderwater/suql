import json
import random

with open("RestaurantReviews.json") as f:
    orig = json.load(f)


MAX_REVIEWS = 20
locations = [
    "Washington DC",
    "Los Angeles",
    "Cincinatti",
    "Mumbai",
    "Oslo",
    "Amsterdam",
    "Stockholm",
]
open_times = ["breakfast", "dinner"]
pricing = ["$", "$$", "$$$"]
ratings = ["0", "0.5", "1", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "5"]

reformatted: dict[str, dict] = {}
for review in orig:
    if not reformatted.get(review["Restaurant"]):
        reformatted[review["Restaurant"]] = {
            "Location": random.choice(locations),
            "Price": random.choice(pricing),
            "Open": random.choice(open_times),
            "Rating": random.choice(ratings),
            "Reviews": [review["Review"]],
        }
    else:
        reviews = reformatted[review["Restaurant"]]["Reviews"]
        if len(reviews) < MAX_REVIEWS:
            reformatted[review["Restaurant"]]["Reviews"].append(review["Review"])
rere = [{"Name": k, **v} for k, v in reformatted.items()]
with open("structured.json", "w") as f:
    json.dump(rere, f)
