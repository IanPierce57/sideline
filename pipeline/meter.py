"""What a segment costs (added Nov 7, 2026).

Wraps the Claude client for one segment and adds up every call's token use by pipeline
step, then prices it. Nothing about the calls changes; this only reads `response.usage`.
The run's meta gets a `usage` section, and the terminal shows the total.

Prices are per million tokens, from Anthropic's pricing page (checked Nov 7, 2026). Cache
reads on Sonnet 5.5 are 0.05x the input price; a 5-minute cache write is 1.25x, a 1-hour
write 2x. If Anthropic changes prices, update PRICES."""

import threading

PRICES = {   # input, output, 5-minute cache write, 1-hour cache write, cache read
    "claude-sonnet-5-5": {"in": 2.00, "out": 10.00, "w5m": 2.50, "w1h": 4.00, "read": 0.10},
    "claude-haiku-5-5": {"in": 0.10, "out": 0.50, "w5m": 0.125, "w1h": 0.20, "read": 0.01},
    "claude-opus-5-5": {"in": 4.00, "out": 20.00, "w5m": 5.00, "w1h": 8.00, "read": 0.20},
}


class Meter:
    def __init__(self):
        self.step = "setup"
        self.steps = {}
        self._lock = threading.Lock()

    def add(self, model: str, usage) -> None:
        if usage is None:
            return
        created = getattr(usage, "cache_creation", None)
        w1h = getattr(created, "ephemeral_1h_input_tokens", 0) or 0 if created else 0
        w5m = (getattr(usage, "cache_creation_input_tokens", 0) or 0) - w1h
        row = {"calls": 1, "input": getattr(usage, "input_tokens", 0) or 0, "output": getattr(usage, "output_tokens", 0) or 0,
               "cache_read": getattr(usage, "cache_read_input_tokens", 0) or 0, "cache_write_5m": max(0, w5m),
               "cache_write_1h": w1h}
        p = next((v for k, v in PRICES.items() if (model or "").startswith(k)), PRICES["claude-sonnet-5-5"])
        row["usd"] = (row["input"] * p["in"] + row["output"] * p["out"] + row["cache_read"] * p["read"]
                      + row["cache_write_5m"] * p["w5m"] + row["cache_write_1h"] * p["w1h"]) / 1e6
        with self._lock:
            total = self.steps.setdefault(self.step, {k: 0 for k in row})
            for k, v in row.items():
                total[k] += v

    def report(self) -> dict:
        steps = {k: dict(v, usd=round(v["usd"], 4)) for k, v in self.steps.items()}
        return {"total_usd": round(sum(v["usd"] for v in self.steps.values()), 4), "by_step": steps}

    def wrap(self, client):
        """Count every call this client makes: create, stream, and the beta stream."""
        meter = self

        def counted_create(original):
            def create(*args, **kwargs):
                reply = original(*args, **kwargs)
                meter.add(kwargs.get("model", ""), getattr(reply, "usage", None))
                return reply
            return create

        def counted_stream(original):
            def stream(*args, **kwargs):
                manager = original(*args, **kwargs)

                class Counted:
                    def __enter__(self):
                        self.inner = manager.__enter__()
                        final = self.inner.get_final_message

                        def get_final_message():
                            message = final()
                            meter.add(kwargs.get("model", ""), getattr(message, "usage", None))
                            return message
                        self.inner.get_final_message = get_final_message
                        return self.inner

                    def __exit__(self, *exc):
                        return manager.__exit__(*exc)
                return Counted()
            return stream

        client.messages.create = counted_create(client.messages.create)
        client.messages.stream = counted_stream(client.messages.stream)
        client.beta.messages.create = counted_create(client.beta.messages.create)
        client.beta.messages.stream = counted_stream(client.beta.messages.stream)
        return client
