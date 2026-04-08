# Nifty Options Terminal – Quant‑Based Trading Dashboard

A professional, real‑time options trading terminal for **NIFTY**, **BANKNIFTY**, **FINNIFTY**, and **MIDCPNIFTY**. Built with Streamlit, it provides live option chains, Greeks (Delta, Gamma, Vega, Theta, Rho), open interest analysis, volatility smile, max pain, put‑call ratio, and actionable trade recommendations.

## Features

- **Live Data** – Fetches real‑time option chain from NSE India API.
- **Greeks Suite** – Calculates Delta, Gamma, Vega, Theta, Rho for every strike.
- **Market Metrics** – PCR, Max OI strikes, Max Pain, support/resistance levels.
- **Visual Analytics** – Interactive OI charts, volatility smile, Greeks heatmap.
- **Trade Recommendations** – Automated sentiment & directional signals based on PCR, OI clustering, and Max Pain.
- **Auto‑Refresh** – Configurable interval (5‑60 seconds) to keep data fresh.
- **Broker Ready** – Can be extended with Zerodha Kite, Fyers, Upstox for live order execution.

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/nifty-options-terminal.git
   cd nifty-options-terminal
