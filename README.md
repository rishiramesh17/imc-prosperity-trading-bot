# IMC Prosperity Tutorial Round 1

This workspace contains a self-contained round-1 baseline for the IMC Prosperity tutorial products:

- `EMERALDS`: fixed-fair-value market making around 10,000
- `TOMATOES`: signal-driven market making using wall-mid, microprice, EMA smoothing, and inventory skew

## Layout

- `submission/trader.py`: upload-ready single-file trader
- `research/backtest.py`: lightweight local backtester for the tutorial capsule
- `datamodel.py`: local stub so the trader can be imported and tested offline
- `data/tutorial_round_1/`: extracted tutorial capsule

## Strategy

The bot uses the standard take-make-clear loop:

1. Take obviously stale prices that are better than the current fair value.
2. Make inside the spread with one-tick-improved quotes when possible.
3. Clear inventory aggressively once position gets too large.

Fair values:

- `EMERALDS`: hardcoded `10000`
- `TOMATOES`: `mid + 0.8 * (wall_mid - mid) + 0.9 * (microprice - mid)`, then smoothed with an EMA

## Backtest

Run:

```bash
python3 research/backtest.py --data-dir data/tutorial_round_1
```

The backtester is an approximation. It handles:

- immediate fills when your order crosses the visible book
- passive fills when you improve the touch and the historical tape shows that touch traded
- passive fills when the next book snapshot moves through your quote

That is useful for parameter sanity checks, but the official IMC simulator remains the final source of truth.

## Upload

Upload `submission/trader.py` to the IMC Prosperity platform.

## GitHub

This folder is ready to be turned into its own repository. I can initialize local git state here, but creating a remote GitHub repository still requires your GitHub auth or your own `gh repo create` / web flow.
