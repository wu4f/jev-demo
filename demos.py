from dataclasses import dataclass

from typesafe_sdk import Choice, Noul, Score

Question = Choice | Noul | Score


@dataclass(frozen=True)
class Example:
    label: str
    text: str


@dataclass(frozen=True)
class Demo:
    slug: str
    title: str
    primitive: str
    description: str
    lesson: str
    experiment: str
    questions: dict[str, Question]
    examples: tuple[Example, ...]


DEPARTMENT = Choice(
    instructions="Which support team should handle this message?",
    criteria={
        "billing": "Charges, invoices, refunds, and subscription payments",
        "technical": "Software bugs, outages, login issues, and integration problems",
        "sales": "Product pricing, purchasing, and plan comparisons",
    },
)
URGENCY = Noul(
    instructions="The message describes an issue requiring immediate or time-sensitive attention."
)
SUPPORT_EXAMPLES = (
    Example(
        "Clear case",
        "Every API request has returned a 500 error for the last 20 minutes. "
        "Our checkout is down and customers cannot place orders. Please help immediately!",
    ),
    Example(
        "Ambiguous",
        "Our invoice looks wrong, and we also sometimes get an error when changing plans. "
        "Could someone look into it?",
    ),
    Example("Nothing fits", "What is your favorite hiking trail near the coast?"),
)

DEMOS = {
    demo.slug: demo
    for demo in (
        Demo(
            slug="support",
            title="Route a support ticket",
            primitive="Choice + Noul",
            description="Turn a customer message into a team assignment and an urgency signal.",
            lesson="Choice selects among named options. Noul estimates whether one statement is true.",
            experiment="Remove the deadline or describe two different problems. What changes?",
            questions={"department": DEPARTMENT, "is_urgent": URGENCY},
            examples=SUPPORT_EXAMPLES,
        ),
        Demo(
            slug="reviews",
            title="Unpack a product review",
            primitive="Score",
            description="Separate overall satisfaction, delivery, and product quality.",
            lesson="Each Score measures one dimension on descriptive levels, numbered from zero. "
            "A fractional score is a probability-weighted position, not a percentage.",
            experiment="Make delivery terrible but keep the product excellent. "
            "Do the separate scores capture the distinction?",
            questions={
                "satisfaction": Score(
                    instructions="How satisfied is the reviewer with the overall experience?",
                    criteria=[
                        "Dissatisfied; regrets the purchase",
                        "Mixed or neutral about the purchase",
                        "Satisfied; happy with the purchase",
                    ],
                ),
                "delivery": Score(
                    instructions="How was the delivery experience described by the reviewer?",
                    criteria=[
                        "Delivery was late, missing, or problematic",
                        "Delivery was acceptable with minor issues",
                        "Delivery was prompt and trouble-free",
                    ],
                ),
                "quality": Score(
                    instructions="How is the product's quality described by the reviewer?",
                    criteria=[
                        "Product is defective or poorly made",
                        "Product is usable with some shortcomings",
                        "Product is well-made and works reliably",
                    ],
                ),
            },
            examples=(
                Example(
                    "Mixed experience",
                    "The headphones sound fantastic and feel solid. Delivery took three weeks "
                    "and the tracking never updated. Still happy I bought them.",
                ),
                Example(
                    "Clear case",
                    "Arrived the next morning, works perfectly, and feels exceptionally well made. "
                    "I love this purchase.",
                ),
                Example("Missing evidence", "I bought headphones yesterday."),
            ),
        ),
        Demo(
            slug="trolley",
            title="Explore the trolley problem",
            primitive="Choice",
            description="See which action Jev favors in a fictional moral dilemma: "
            "pull the lever or do nothing.",
            lesson="Choice compares two preset actions. Its probabilities show how Jev weighs "
            "the options, not which action is morally correct or what it would actually do. "
            "This is a thought experiment; no real action is taken.",
            experiment="Change the number of people on each track or make the outcome uncertain. "
            "Run again and compare the distributions. Does Jev's preferred action change?",
            questions={
                "action": Choice(
                    instructions="In this fictional trolley problem, which of the two actions "
                    "would you choose? Weigh the consequences and ethical tradeoffs described "
                    "in the scenario. Treat these as the only available actions; do not assume "
                    "an unmentioned rescue option.",
                    criteria={
                        "pull_the_lever": "Pull the lever to divert the trolley onto the side track.",
                        "do_nothing": "Do not pull the lever; leave the trolley on its current track.",
                    },
                ),
            },
            examples=(
                Example(
                    "Classic dilemma",
                    "In a fictional thought experiment, a runaway trolley is heading toward "
                    "five people on the main track. You can pull a lever to divert it onto a "
                    "side track where one person stands. Nobody can leave the tracks. "
                    "There is no way to stop the trolley or warn anyone in time. "
                    "Pulling the lever means one person dies; doing nothing means five die. "
                    "Your only choices are to pull the lever or do nothing.",
                ),
                Example(
                    "Reverse the numbers",
                    "In a fictional thought experiment, a runaway trolley is heading toward "
                    "one person on the main track. You can pull a lever to divert it onto a "
                    "side track where five people stand. Nobody can leave the tracks. "
                    "There is no way to stop the trolley or warn anyone in time. "
                    "Pulling the lever means five people die; doing nothing means one dies. "
                    "Your only choices are to pull the lever or do nothing.",
                ),
                Example(
                    "Uncertain outcome",
                    "In a fictional thought experiment, a runaway trolley is heading toward "
                    "five people on the main track. You can pull a lever to divert it onto a "
                    "side track where one person stands. Nobody can leave the tracks. "
                    "There is no way to stop the trolley or warn anyone in time. "
                    "The lever has a 20% chance of diverting the trolley, in which case one "
                    "person dies. Otherwise it stays on the main track and five people die, "
                    "just as they would if you did nothing. "
                    "Your only choices are to pull the lever or do nothing.",
                ),
            ),
        ),
        Demo(
            slug="automation",
            title="Build an automation rule",
            primitive="Decisions + code",
            description="Use probabilities to route a ticket, request review, or flag it as urgent.",
            lesson="Jev supplies judgments. Your code owns the policy. "
            "Changing a threshold reuses the same answers and makes no additional API call.",
            experiment="Run an ambiguous message, then move the thresholds. "
            "Can you change the action without changing Jev's answer?",
            questions={"department": DEPARTMENT, "is_urgent": URGENCY},
            examples=SUPPORT_EXAMPLES,
        ),
    )
}
