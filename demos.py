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
            slug="announcements",
            title="Check an announcement",
            primitive="Noul",
            description="Check whether a message gives readers the details they need.",
            lesson="Ask for each detail independently. A value near 0.5 signals uncertainty, "
            "not a confident yes or no. This is a completeness check, not fact verification.",
            experiment="Replace an exact room with 'the usual place'. "
            "Is the location still clearly specified?",
            questions={
                "has_date": Noul(
                    instructions="The announcement explicitly specifies a calendar date for the event."
                ),
                "has_location": Noul(
                    instructions="The announcement explicitly specifies a physical location "
                    "or online meeting address for the event."
                ),
                "has_action": Noul(
                    instructions="The announcement explicitly tells readers what action to take."
                ),
            },
            examples=(
                Example(
                    "Complete",
                    "Join our robotics workshop on March 12, 2027 at 3 pm in Engineering Room 204. "
                    "Register using the course portal before March 10.",
                ),
                Example(
                    "Ambiguous",
                    "The workshop is happening soon at the usual place. You know what to do!",
                ),
                Example("Missing details", "We are planning a robotics workshop. More details soon."),
            ),
        ),
        Demo(
            slug="nothing-fits",
            title="Know when nothing fits",
            primitive="Choice + companion Noul",
            description="See why picking the best available category can still be the wrong action.",
            lesson="Choice must select an available option. An independent companion Noul checks "
            "whether any of those options actually applies.",
            experiment="Ask for a recipe. Watch the Choice answer alongside the fit probability.",
            questions={
                "department": DEPARTMENT,
                "fits": Noul(
                    instructions="The message is a customer support request about at least one of: "
                    "billing (charges, invoices, refunds, subscription payments); technical support "
                    "(software bugs, outages, login issues, integrations); or sales "
                    "(pricing, purchasing, plan comparisons)."
                ),
            },
            examples=SUPPORT_EXAMPLES,
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
