"""Pinned pricing constants for the cost engine.

Prices are integer MICRO-UNITS (1/10,000 of a cent), so money math is
float-free per the capstone brief: store money as integers, never floats.

Basis: US cents per 1,000 tokens / calls, converted to micro-units by
multiplying by 10,000.

    cents_per_1k * 10_000 == micro_units_per_1k

Rules the cost engine must encode (from the brief, section 3):
  * cached input tokens are cheaper than fresh input
  * reasoning tokens are billed as output tokens
  * token categories cannot simply be added together -- each is priced
    with its own per-1k rate, then summed
"""

PRICING = {
    # cents per 1k tokens
    "cached_input_per_1k": 0.10,
    "input_per_1k": 0.30,
    "output_per_1k": 0.60,
    "reasoning_per_1k": 0.60,  # billed as output, at output's rate
    # cents per 1k api calls
    "api_call_per_1k": 2.00,
}

# 1 cent == 10,000 micro-units. Converts a "cents per 1k" float into an
# integer micro-units-per-1k value so cost math never touches floats.
CENTS_TO_MICRO = 10_000
