"""CoinMarketCap AI Agent Hub data layer for the ETH Rapid Reversal skill.

The BNB Hack provides the **CoinMarketCap AI Agent Hub** as the data layer for
Track 2. The Agent Hub exposes one underlying dataset through several surfaces:

    +-------------------+--------------------------------------------+
    | Surface           | How an agent / skill reaches it            |
    +-------------------+--------------------------------------------+
    | REST (CMC Pro)    | HTTPS GET to api.coinmarketcap.com with    |
    |                   | X-CMC_PRO_API_KEY  <-- this skill uses this|
    | MCP server        | MCP tools (quotes, ohlcv, listings, f&g,  |
    |                   | fear-and-greed, derivatives, social)       |
    | x402 (pay-per-req)| HTTP 402 -> agent pays per data request    |
    | CMC CLI           | `cmc` CLI commands in a shell/agent loop   |
    | IDE integration   | Agent Hub plugin for Cursor / VS Code      |
    +-------------------+--------------------------------------------+

This module is the **single data dependency** of the strategy. `data_loader.py`
implements the REST surface (the Python-accessible interface to the same data
the Agent Hub serves over MCP / x402 / CLI); every field the strategy touches
is listed in `AGENT_HUB_FIELDS` so the mapping is explicit and auditable.

To swap in the MCP / x402 / CLI surface, replace the body of the `load_*`
functions in `data_loader.py` with the equivalent tool call — the strategy and
backtest engine are surface-agnostic and consume plain pandas objects.
"""
from __future__ import annotations

from dataclasses import dataclass

# Each row: the strategy field, the CMC Agent Hub concept that produces it, and
# which surfaces expose it. Every entry is consumed by backtest/engine.py.
AGENT_HUB_FIELDS = [
    ("OHLCV 5m / 15m / 1h", "Cryptocurrency OHLCV historical", "REST / MCP / x402 / CLI"),
    ("Fear & Greed Index", "Fear & Greed historical", "REST / MCP / x402 / CLI"),
    ("Funding rate (8h)", "Derivatives funding-rate historical", "REST / MCP / x402 / CLI"),
    ("Open interest (1h)", "Derivatives open-interest historical", "REST / MCP / x402 / CLI"),
    ("Social mentions (1h)", "Social stats / mentions historical", "REST / MCP / x402 / CLI"),
]


@dataclass
class HubBundle:
    """All data the strategy needs for one symbol/window, bundled."""
    df_5m: "object"
    df_15m: "object"
    fear_greed: "object"
    funding: "object"
    open_interest: "object"
    social: "object"


def load_all(symbol: str = "ETH", days: int = 30) -> HubBundle:
    """Load every Agent Hub field the engine needs, as pandas objects.

    This is the one call `run_backtest.py` and `sweep.py` make against the data
    layer. Routing the call through here keeps the Agent Hub dependency in a
    single, auditable place.
    """
    from .data_loader import (
        load_cmc_fear_greed,
        load_cmc_funding_rate,
        load_cmc_ohlcv,
        load_cmc_open_interest,
        load_cmc_social_mentions,
    )
    return HubBundle(
        df_5m=load_cmc_ohlcv(symbol, "5m", days),
        df_15m=load_cmc_ohlcv(symbol, "15m", days),
        fear_greed=load_cmc_fear_greed(days),
        funding=load_cmc_funding_rate(symbol, days),
        open_interest=load_cmc_open_interest(symbol, days),
        social=load_cmc_social_mentions(symbol, days),
    )


def field_map() -> str:
    """Human-readable mapping of strategy fields -> Agent Hub surfaces."""
    lines = ["Strategy field -> CMC Agent Hub concept (surfaces)",
             "-" * 66]
    for field, concept, surfaces in AGENT_HUB_FIELDS:
        lines.append(f"{field:24} | {concept:42} | {surfaces}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(field_map())
