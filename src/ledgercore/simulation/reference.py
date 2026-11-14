"""Independent executable specification. No imports from posting, ORM, jobs or schedules.

The reference processes a chronological simulation stream, maintaining its own simple
schedule capacities and receivable lots. It does not use observed API responses.
"""

from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext


def money(value):
    return int(value.to_integral_value(rounding=ROUND_HALF_UP))


def reference_schedule(loan):
    with localcontext() as ctx:
        ctx.prec = 60
        p, n = loan["principal_paise"], loan["tenure_periods"]
        periodic = Decimal(loan["annual_rate"]) / (
            52 if loan["frequency"] == "weekly" else 12
        )
        first = date.fromisoformat(loan["first_due_date"])
        flat_total = money(Decimal(p) * periodic * n)
        emi = money(
            Decimal(p) / n
            if not periodic
            else Decimal(p) * periodic / (1 - (1 + periodic) ** (-n))
        )
        remaining, result = p, []
        for index in range(n):
            if loan["frequency"] == "weekly":
                due = first + timedelta(days=7 * index)
            else:
                y, m = divmod(first.year * 12 + first.month - 1 + index, 12)
                due = date(y, m + 1, min(first.day, monthrange(y, m + 1)[1]))
            if loan["interest_method"] == "flat":
                principal = p // n if index < n - 1 else p - (p // n) * (n - 1)
                interest = (
                    flat_total // n
                    if index < n - 1
                    else flat_total - (flat_total // n) * (n - 1)
                )
            else:
                interest = money(Decimal(remaining) * periodic)
                principal = (
                    min(remaining, max(0, emi - interest))
                    if index < n - 1
                    else remaining
                )
            remaining -= principal
            result.append(
                {
                    "instalment_number": index + 1,
                    "due_date": due.isoformat(),
                    "principal_due_paise": principal,
                    "interest_due_paise": interest,
                }
            )
        return result


class ReferenceBook:
    def __init__(self, loans):
        self.states = {}
        self.keys, self.sources = {}, {}
        self.expected = {}
        self.journals = len(loans)
        self.penalty_evaluations = self.penalty_zero_days = 0
        for loan in loans:
            rows = reference_schedule(loan)
            self.states[loan["id"]] = {
                "rows": rows,
                "principal": [r["principal_due_paise"] for r in rows],
                "interest": [],
                "penalty": [],
                "recognized": set(),
                "interest_total": 0,
                "penalty_total": 0,
                "collected": defaultdict(int),
                "last_occurred": "",
            }

    def start_day(self, day):
        for state in self.states.values():
            for i, row in enumerate(state["rows"]):
                if row["due_date"] <= day and i not in state["recognized"]:
                    state["recognized"].add(i)
                    interest = row["interest_due_paise"]
                    if interest:
                        state["interest"].append([row["due_date"], i, interest])
                        state["interest_total"] += interest
                        self.journals += 1
                if row["due_date"] < day:
                    # Daily opening balance: start_day precedes ALL deliveries on day D.
                    penalty = money(Decimal(state["principal"][i]) * Decimal("0.0005"))
                    self.penalty_evaluations += 1
                    if penalty:
                        state["penalty"].append([day, i, penalty])
                        state["penalty_total"] += penalty
                        self.journals += 1
                    else:
                        self.penalty_zero_days += 1

    def deliver(self, event):
        state = self.states[event["loan_id"]]
        payload = {
            k: event[k]
            for k in (
                "loan_id",
                "source",
                "external_event_id",
                "amount_paise",
                "occurred_at",
                "business_date",
            )
        }
        key = (event["actor"], event["idempotency_key"])
        source = (event["source"], event["external_event_id"])
        allocations = []
        if event["actor"] not in ("demo-officer", "demo-manager"):
            result = {"status": 403, "behavior": "authorization_denied"}
        elif (
            type(event["amount_paise"]) is not int
            or not 1 <= event["amount_paise"] <= 100000000000
        ):
            result = {"status": 422, "behavior": "invalid_amount"}
        elif key in self.keys and self.keys[key][0] != payload:
            result = {"status": 409, "behavior": "idempotency_collision"}
        elif key in self.keys or source in self.sources:
            previous_payload, previous_id = (
                self.keys[key] if key in self.keys else self.sources[source]
            )
            if previous_payload != payload:
                result = {"status": 409, "behavior": "source_conflict"}
            else:
                original = self.expected[previous_id]
                result = {
                    "status": 201,
                    "behavior": "duplicate",
                    "canonical_delivery_id": previous_id,
                    "allocations": original["allocations"],
                }
                self.keys[key] = (payload, previous_id)
        else:
            outstanding = sum(state["principal"]) + sum(
                x[2] for x in state["penalty"] + state["interest"]
            )
            amount = event["amount_paise"]
            if amount > outstanding:
                result = {"status": 400, "behavior": "overpayment_rejected"}
            else:
                remaining = amount
                allocated = defaultdict(int)
                for component in ("penalty", "interest"):
                    for lot in sorted(
                        state[component], key=lambda lot: (lot[0], lot[1])
                    ):
                        value = min(lot[2], remaining)
                        lot[2] -= value
                        remaining -= value
                        if value:
                            allocated[(lot[1] + 1, component)] += value
                            state["collected"][component] += value
                for index in range(len(state["principal"])):
                    value = min(state["principal"][index], remaining)
                    state["principal"][index] -= value
                    remaining -= value
                    if value:
                        allocated[(index + 1, "principal")] += value
                        state["collected"]["principal"] += value
                assert remaining == 0
                allocations = [
                    {"instalment_number": i, "component": c, "amount_paise": v}
                    for (i, c), v in allocated.items()
                ]
                result = {
                    "status": 201,
                    "behavior": "accepted_new",
                    "allocations": allocations,
                    "out_of_order": event["occurred_at"] < state["last_occurred"],
                }
                state["last_occurred"] = max(
                    state["last_occurred"], event["occurred_at"]
                )
                self.keys[key], self.sources[source] = (
                    (payload, event["delivery_id"]),
                    (payload, event["delivery_id"]),
                )
                self.journals += 1
        self.expected[event["delivery_id"]] = result
        return result

    def summary(self):
        return {
            loan_id: {
                "principal_paise": sum(state["principal"]),
                "interest_paise": sum(lot[2] for lot in state["interest"]),
                "penalty_paise": sum(lot[2] for lot in state["penalty"]),
                "recognized_interest_paise": state["interest_total"],
                "recognized_penalty_paise": state["penalty_total"],
                "collected": dict(state["collected"]),
                "principal_by_instalment": state["principal"],
            }
            for loan_id, state in self.states.items()
        }
