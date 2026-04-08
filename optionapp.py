import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime as dt
import plotly.graph_objects as go
from scipy.stats import norm
from streamlit_autorefresh import st_autorefresh

# -----------------------------
# Page Configuration
# -----------------------------
st.set_page_config(
    page_title="Nifty Options Terminal",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Nifty Options Trading Terminal")
st.caption("Quantitative Analysis · Real-Time Greeks · Risk Management")

# -----------------------------
# Sidebar Configuration
# -----------------------------
with st.sidebar:
    st.header("⚙️ Configuration")
    
    instrument = st.selectbox(
        "Instrument", 
        ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"],
        index=0
    )
    
    expiry = st.selectbox(
        "Expiry",
        ["Current Week", "Next Week", "Current Month", "Next Month"],
        index=2
    )
    
    st.divider()
    
    st.subheader("📈 Risk Parameters")
    risk_free_rate = st.number_input("Risk-Free Rate (%)", value=6.5, step=0.1) / 100
    st.caption("Source: RBI 10-Year G-Sec Yield")
    
    col1, col2 = st.columns(2)
    with col1:
        lot_size = st.number_input("Lot Size", value=75, step=1)
    with col2:
        capital = st.number_input("Capital (₹)", value=100000, step=50000)
    
    st.divider()
    
    st.subheader("📊 Auto-Refresh")
    refresh_interval = st.slider("Refresh (seconds)", 5, 60, 15)
    count = st_autorefresh(interval=refresh_interval * 1000, limit=None, key="refresh")

# -----------------------------
# Data Fetching Functions
# -----------------------------
@st.cache_data(ttl=15)
def fetch_spot_price(symbol):
    """Fetch current spot price from NSE."""
    try:
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers)
        response = session.get(url, headers=headers)
        data = response.json()
        return data['records']['underlyingValue']
    except:
        # Fallback to broker API if available
        return 24500.0  # Placeholder

@st.cache_data(ttl=15)
def fetch_option_chain(symbol):
    """Fetch complete option chain from NSE API."""
    url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'en-US,en;q=0.9'}
    
    session = requests.Session()
    session.get("https://www.nseindia.com", headers=headers)
    response = session.get(url, headers=headers)
    data = response.json()
    
    records = data['records']['data']
    spot = data['records']['underlyingValue']
    
    # Parse into DataFrame
    rows = []
    for record in records:
        strike = record['strikePrice']
        expiry_date = record['expiryDate']
        
        # CE data
        ce = record.get('CE', {})
        pe = record.get('PE', {})
        
        rows.append({
            'strike': strike,
            'expiry': expiry_date,
            'ce_oi': ce.get('openInterest', 0),
            'ce_ltp': ce.get('lastPrice', 0),
            'ce_iv': ce.get('impliedVolatility', 0),
            'ce_volume': ce.get('totalTradedVolume', 0),
            'pe_oi': pe.get('openInterest', 0),
            'pe_ltp': pe.get('lastPrice', 0),
            'pe_iv': pe.get('impliedVolatility', 0),
            'pe_volume': pe.get('totalTradedVolume', 0),
        })
    
    df = pd.DataFrame(rows)
    return df, spot

# -----------------------------
# Greeks Calculation
# -----------------------------
def black_scholes_price(S, K, T, r, sigma, option_type):
    """Calculate option price using Black-Scholes."""
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == 'call':
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    return price

def calculate_greeks(S, K, T, r, sigma, option_type):
    """Calculate all Greeks for an option."""
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    delta = norm.cdf(d1) if option_type == 'call' else norm.cdf(d1) - 1
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    vega = S * norm.pdf(d1) * np.sqrt(T) / 100
    theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) 
             - r * K * np.exp(-r * T) * norm.cdf(d2 if option_type == 'call' else -d2)) / 365
    rho = K * T * np.exp(-r * T) * norm.cdf(d2 if option_type == 'call' else -d2) / 100
    
    # Theoretical price
    theo_price = black_scholes_price(S, K, T, r, sigma, option_type)
    
    return {
        'delta': round(delta, 4),
        'gamma': round(gamma, 4),
        'vega': round(vega, 2),
        'theta': round(theta, 2),
        'rho': round(rho, 2),
        'theo_price': round(theo_price, 2)
    }

def add_greeks_to_chain(df, spot, r, T):
    """Add Greeks columns to option chain DataFrame."""
    # Calculate days to expiry
    df['dte'] = (pd.to_datetime(df['expiry']) - pd.Timestamp.now()).dt.days
    df['T'] = df['dte'] / 365
    
    # Calculate Greeks for CE
    ce_greeks = df.apply(
        lambda row: calculate_greeks(spot, row['strike'], row['T'], r, 
                                     row['ce_iv'] / 100, 'call') 
        if row['ce_iv'] > 0 else {'delta': 0, 'gamma': 0, 'vega': 0, 'theta': 0, 'rho': 0},
        axis=1
    )
    
    # Calculate Greeks for PE
    pe_greeks = df.apply(
        lambda row: calculate_greeks(spot, row['strike'], row['T'], r, 
                                     row['pe_iv'] / 100, 'put')
        if row['pe_iv'] > 0 else {'delta': 0, 'gamma': 0, 'vega': 0, 'theta': 0, 'rho': 0},
        axis=1
    )
    
    # Add to DataFrame
    df['ce_delta'] = [g['delta'] for g in ce_greeks]
    df['ce_gamma'] = [g['gamma'] for g in ce_greeks]
    df['ce_vega'] = [g['vega'] for g in ce_greeks]
    df['ce_theta'] = [g['theta'] for g in ce_greeks]
    df['ce_theo'] = [g['theo_price'] for g in ce_greeks]
    
    df['pe_delta'] = [g['delta'] for g in pe_greeks]
    df['pe_gamma'] = [g['gamma'] for g in pe_greeks]
    df['pe_vega'] = [g['vega'] for g in pe_greeks]
    df['pe_theta'] = [g['theta'] for g in pe_greeks]
    df['pe_theo'] = [g['theo_price'] for g in pe_greeks]
    
    return df

# -----------------------------
# Market Metrics
# -----------------------------
def calculate_metrics(df):
    """Calculate key market metrics."""
    total_ce_oi = df['ce_oi'].sum()
    total_pe_oi = df['pe_oi'].sum()
    pcr = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 0
    
    # Max OI strikes
    max_ce_oi_row = df.loc[df['ce_oi'].idxmax()] if df['ce_oi'].max() > 0 else None
    max_pe_oi_row = df.loc[df['pe_oi'].idxmax()] if df['pe_oi'].max() > 0 else None
    
    # Max Pain calculation
    df['max_pain'] = (df['ce_oi'] * (df['strike'] - df['strike'].median())**2 + 
                      df['pe_oi'] * (df['strike'] - df['strike'].median())**2)
    max_pain_strike = df.loc[df['max_pain'].idxmin(), 'strike'] if len(df) > 0 else 0
    
    return {
        'total_ce_oi': total_ce_oi,
        'total_pe_oi': total_pe_oi,
        'pcr': pcr,
        'max_ce_oi_strike': max_ce_oi_row['strike'] if max_ce_oi_row is not None else 0,
        'max_pe_oi_strike': max_pe_oi_row['strike'] if max_pe_oi_row is not None else 0,
        'max_pain': max_pain_strike
    }

# -----------------------------
# Trade Recommendations
# -----------------------------
def generate_recommendations(df, spot, metrics):
    """Generate trading recommendations based on data."""
    recommendations = []
    
    # PCR-based sentiment
    if metrics['pcr'] > 1.2:
        rec = "🚨 BEARISH SENTIMENT: High PCR (>1.2) indicates excessive put buying. Consider Put writing or Call buying strategies."
        recommendations.append(rec)
    elif metrics['pcr'] < 0.8:
        rec = "🚨 BULLISH SENTIMENT: Low PCR (<0.8) indicates excessive call buying. Consider Call writing or Put buying strategies."
        recommendations.append(rec)
    
    # Support/Resistance from Max OI
    if metrics['max_ce_oi_strike'] > spot:
        rec = f"📉 RESISTANCE: Maximum Call OI at {metrics['max_ce_oi_strike']} - Strong resistance level."
        recommendations.append(rec)
    if metrics['max_pe_oi_strike'] < spot:
        rec = f"📈 SUPPORT: Maximum Put OI at {metrics['max_pe_oi_strike']} - Strong support level."
        recommendations.append(rec)
    
    # Max Pain
    if abs(metrics['max_pain'] - spot) / spot > 0.02:
        rec = f"🎯 MAX PAIN: Market may drift towards {metrics['max_pain']} (Max Pain level)."
        recommendations.append(rec)
    
    return recommendations

# -----------------------------
# Visualization Functions
# -----------------------------
def plot_oi_chain(df, spot):
    """Create Open Interest chart for calls and puts."""
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['strike'], y=df['ce_oi'], name='Call OI',
        mode='lines+markers', line=dict(color='green', width=2),
        marker=dict(size=6)
    ))
    
    fig.add_trace(go.Scatter(
        x=df['strike'], y=df['pe_oi'], name='Put OI',
        mode='lines+markers', line=dict(color='red', width=2),
        marker=dict(size=6)
    ))
    
    fig.add_vline(x=spot, line_dash="dash", line_color="blue",
                  annotation_text=f"Spot: {spot}", annotation_position="top right")
    
    fig.update_layout(
        title="Open Interest by Strike Price",
        xaxis_title="Strike Price (₹)",
        yaxis_title="Open Interest",
        hovermode='x unified',
        template='plotly_dark'
    )
    return fig

def plot_iv_smile(df):
    """Create IV smile chart."""
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['strike'], y=df['ce_iv'] * 100, name='Call IV',
        mode='lines+markers', line=dict(color='green', width=2)
    ))
    
    fig.add_trace(go.Scatter(
        x=df['strike'], y=df['pe_iv'] * 100, name='Put IV',
        mode='lines+markers', line=dict(color='red', width=2)
    ))
    
    fig.update_layout(
        title="Volatility Smile",
        xaxis_title="Strike Price (₹)",
        yaxis_title="Implied Volatility (%)",
        hovermode='x unified',
        template='plotly_dark'
    )
    return fig

def plot_greeks_heatmap(df):
    """Create Greeks heatmap (Delta, Gamma, Vega)."""
    greeks_data = df[['strike', 'ce_delta', 'ce_gamma', 'ce_vega', 'pe_delta', 'pe_gamma', 'pe_vega']].copy()
    return greeks_data

# -----------------------------
# Main Application
# -----------------------------
def main():
    # Fetch data
    with st.spinner("Fetching live market data..."):
        df, spot = fetch_option_chain(instrument)
    
    # Calculate days to expiry (using first expiry date)
    if len(df) > 0:
        first_expiry = df['expiry'].iloc[0]
        dte = (pd.to_datetime(first_expiry) - pd.Timestamp.now()).days
        T = max(dte / 365, 0.01)
        
        # Add Greeks
        df = add_greeks_to_chain(df, spot, risk_free_rate, T)
        
        # Calculate metrics
        metrics = calculate_metrics(df)
        
        # Generate recommendations
        recommendations = generate_recommendations(df, spot, metrics)
    
    # Layout: Top metrics row
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("📍 Spot Price", f"₹{spot:,.2f}")
    with col2:
        st.metric("📊 Put-Call Ratio", f"{metrics['pcr']:.2f}")
    with col3:
        st.metric("🔮 Max Pain", f"₹{metrics['max_pain']:,.0f}")
    with col4:
        st.metric("📈 Call OI (Total)", f"{metrics['total_ce_oi']:,.0f}")
    with col5:
        st.metric("📉 Put OI (Total)", f"{metrics['total_pe_oi']:,.0f}")
    
    # Charts row
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(plot_oi_chain(df, spot), use_container_width=True)
    with col2:
        st.plotly_chart(plot_iv_smile(df), use_container_width=True)
    
    # Greeks DataTable
    st.subheader("📐 Options Chain with Greeks")
    
    # Format display columns
    display_df = df[[
        'strike', 'expiry', 'dte',
        'ce_oi', 'ce_ltp', 'ce_iv', 'ce_delta', 'ce_gamma', 'ce_vega', 'ce_theta',
        'pe_oi', 'pe_ltp', 'pe_iv', 'pe_delta', 'pe_gamma', 'pe_vega', 'pe_theta'
    ]].copy()
    
    display_df.columns = [
        'Strike', 'Expiry', 'DTE',
        'Call OI', 'Call LTP', 'Call IV%', 'Call Δ', 'Call Γ', 'Call ν', 'Call Θ',
        'Put OI', 'Put LTP', 'Put IV%', 'Put Δ', 'Put Γ', 'Put ν', 'Put Θ'
    ]
    
    # Highlight ATM strikes
    atm_strike = df.iloc[(df['strike'] - spot).abs().argsort()[:3]]['strike'].values
    
    def highlight_atm(row):
        if row['Strike'] in atm_strike:
            return ['background-color: rgba(255, 165, 0, 0.2)'] * len(row)
        return [''] * len(row)
    
    st.dataframe(
        display_df.style.apply(highlight_atm, axis=1).format({
            'Call OI': '{:,.0f}', 'Put OI': '{:,.0f}',
            'Call LTP': '{:.2f}', 'Put LTP': '{:.2f}',
            'Call IV%': '{:.2f}%', 'Put IV%': '{:.2f}%',
            'Call Δ': '{:.4f}', 'Call Γ': '{:.4f}', 'Call ν': '{:.2f}', 'Call Θ': '{:.2f}',
            'Put Δ': '{:.4f}', 'Put Γ': '{:.4f}', 'Put ν': '{:.2f}', 'Put Θ': '{:.2f}'
        }),
        height=400,
        use_container_width=True
    )
    
    # Trade Recommendations
    st.subheader("🎯 Quantitative Trade Recommendations")
    if recommendations:
        for rec in recommendations:
            st.info(rec)
    else:
        st.info("No strong signals detected. Market sentiment appears neutral.")
    
    # Greeks Heatmap (expandable)
    with st.expander("📊 Advanced Greeks Analysis"):
        st.dataframe(plot_greeks_heatmap(df), use_container_width=True)
        
        # Greeks statistics
        col1, col2 = st.columns(2)
        with col1:
            st.write("**ATM Call Greeks**")
            atm_idx = (df['strike'] - spot).abs().idxmin()
            st.write(f"Delta: {df.loc[atm_idx, 'ce_delta']:.4f}")
            st.write(f"Gamma: {df.loc[atm_idx, 'ce_gamma']:.4f}")
            st.write(f"Vega: ₹{df.loc[atm_idx, 'ce_vega']:.2f} per 1% IV change")
            st.write(f"Theta: ₹{df.loc[atm_idx, 'ce_theta']:.2f} per day")
        with col2:
            st.write("**ATM Put Greeks**")
            st.write(f"Delta: {df.loc[atm_idx, 'pe_delta']:.4f}")
            st.write(f"Gamma: {df.loc[atm_idx, 'pe_gamma']:.4f}")
            st.write(f"Vega: ₹{df.loc[atm_idx, 'pe_vega']:.2f} per 1% IV change")
            st.write(f"Theta: ₹{df.loc[atm_idx, 'pe_theta']:.2f} per day")
    
    # Footer
    st.divider()
    st.caption(f"🔄 Data auto-refreshes every {refresh_interval} seconds | {instrument} Options Chain | Powered by NSE API")

if __name__ == "__main__":
    main()
