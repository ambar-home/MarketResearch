"""
Nifty 100 SMA Crossover Scanner
--------------------------------
Uses Zerodha Kite Connect to:
  1. Load API credentials
  2. Download Nifty 100 stock list
  3. Map symbols to NSE instrument tokens
  4. Fetch daily OHLC history
  5. Calculate SMA 6 and SMA 30
  6. Detect bullish / bearish crossovers
  7. Rank by most recent crossover date
  8. Print a pandas DataFrame and save CSV

Dependencies (only these):
  pip install kiteconnect pandas requests
"""

from datetime import datetime, timedelta
from io import StringIO
import sys
import time

import pandas as pd
import requests
from kiteconnect import KiteConnect


# =============================================================================
# SETTINGS (edit these)
# =============================================================================

# One-time login token from Kite login redirect URL (?request_token=...)
# Paste a FRESH token here, or pass it as:
#   python "nifty 100_sma_scanner.py" YOUR_REQUEST_TOKEN
REQUEST_TOKEN = "kAsalQlHej15vm9RTrRAz8H3FuZKf0Yv"

CREDENTIALS_FILE = "credentials.txt"
OUTPUT_CSV = "nifty 100_sma_signals.csv"

# How much daily history to download (need enough bars for SMA 30 + older crossovers)
LOOKBACK_DAYS = 400

# Small pause between API calls to stay polite with rate limits
SLEEP_SECONDS = 0.35


# =============================================================================
# STEP 1: Read API Key and API Secret from credentials.txt
# =============================================================================

def read_credentials(filepath: str) -> tuple[str, str]:
    """
    Expects a file like:
      api_key=xxxx
      api_secret=yyyy
    """
    api_key = None
    api_secret = None

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip().lower()
            value = value.strip()

            if key == "api_key":
                api_key = value
            elif key == "api_secret":
                api_secret = value

    if not api_key or not api_secret:
        raise ValueError(
            f"Could not find api_key and api_secret in {filepath}. "
            "Use lines like: api_key=... and api_secret=..."
        )

    return api_key, api_secret


# =============================================================================
# STEP 2: Login to Kite Connect
# =============================================================================

def create_kite_client(api_key: str, api_secret: str, request_token: str) -> KiteConnect:
    """Exchange request_token for access_token and return a ready Kite client."""
    kite = KiteConnect(api_key=api_key)

    print("Login URL (open this if you need a new request_token):")
    print(kite.login_url())
    print()

    if not request_token or request_token.strip().lower() in {"", "paste_here", "your_request_token"}:
        request_token = input("Paste request_token from redirect URL: ").strip()

    print("Generating Kite session...")
    try:
        session = kite.generate_session(request_token, api_secret=api_secret)
    except Exception as exc:
        raise SystemExit(
            f"Login failed: {exc}\n"
            "Request tokens expire quickly and can be used only once.\n"
            "Open the login URL above, log in, copy the new request_token, and run again."
        ) from exc

    kite.set_access_token(session["access_token"])
    print("Login successful.\n")
    return kite


# =============================================================================
# STEP 3: Download Nifty 100 constituents
# =============================================================================

def download_nifty100() -> pd.DataFrame:
    """
    Download official Nifty 100 list from NSE archives.
    Returns a DataFrame with at least: Symbol, Company Name
    """
    url = "https://archives.nseindia.com/content/indices/ind_nifty100list.csv"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/csv,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/",
    }

    print("Downloading Nifty 100 constituents...")
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    nifty100 = pd.read_csv(StringIO(response.text))

    # Normalize expected column names (NSE CSV usually has these)
    # Typical columns: Company Name, Industry, Symbol, Series, ISIN Code
    if "Symbol" not in nifty100.columns:
        raise ValueError(f"Unexpected Nifty 100 CSV columns: {list(nifty100.columns)}")

    # Some CSVs use "Company Name", keep a clean company column
    if "Company Name" in nifty100.columns:
        nifty100 = nifty100.rename(columns={"Company Name": "Company"})
    elif "Company" not in nifty100.columns:
        nifty100["Company"] = nifty100["Symbol"]

    nifty100["Symbol"] = nifty100["Symbol"].astype(str).str.strip().str.upper()
    nifty100["Company"] = nifty100["Company"].astype(str).str.strip()

    print(f"Found {len(nifty100)} Nifty 100 stocks.\n")
    return nifty100[["Symbol", "Company"]].copy()


# =============================================================================
# STEP 4: Map symbols to NSE instrument tokens
# =============================================================================

def map_symbols_to_tokens(kite: KiteConnect, symbols: list[str]) -> dict[str, int]:
    """
    Download NSE instrument master from Kite and map EQ symbols -> instrument_token.
    """
    print("Downloading NSE instrument list from Kite...")
    instruments = kite.instruments("NSE")
    instruments_df = pd.DataFrame(instruments)

    # Keep only equity cash market symbols (EQ series)
    eq = instruments_df[
        (instruments_df["tradingsymbol"].isin(symbols))
        & (instruments_df["instrument_type"] == "EQ")
        & (instruments_df["segment"] == "NSE")
    ].copy()

    # If duplicates appear, keep first
    eq = eq.drop_duplicates(subset=["tradingsymbol"], keep="first")

    token_map = dict(zip(eq["tradingsymbol"], eq["instrument_token"]))

    missing = [s for s in symbols if s not in token_map]
    if missing:
        print(f"Warning: could not map {len(missing)} symbols: {missing}")

    print(f"Mapped {len(token_map)} / {len(symbols)} symbols to instrument tokens.\n")
    return token_map


# =============================================================================
# STEP 5: Fetch daily historical data
# =============================================================================

def fetch_daily_history(
    kite: KiteConnect,
    instrument_token: int,
    lookback_days: int = LOOKBACK_DAYS,
) -> pd.DataFrame:
    """Fetch daily candles and return a DataFrame indexed by date."""
    to_date = datetime.now().date()
    from_date = to_date - timedelta(days=lookback_days)

    candles = kite.historical_data(
        instrument_token=instrument_token,
        from_date=from_date,
        to_date=to_date,
        interval="day",
        continuous=False,
        oi=False,
    )

    if not candles:
        return pd.DataFrame()

    df = pd.DataFrame(candles)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    df = df.sort_values("date").reset_index(drop=True)
    return df


# =============================================================================
# STEP 6 + 7: SMA calculation and crossover detection
# =============================================================================

def add_sma_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add SMA 6 and SMA 30 on the daily close."""
    out = df.copy()
    out["SMA_6"] = out["close"].rolling(window=6, min_periods=6).mean()
    out["SMA_30"] = out["close"].rolling(window=30, min_periods=30).mean()
    return out


def find_latest_crossover(df: pd.DataFrame) -> dict | None:
    """
    Detect SMA6 vs SMA30 crossovers and return the most recent one.

    Bullish: SMA6 crosses ABOVE SMA30
    Bearish: SMA6 crosses BELOW SMA30
    """
    data = add_sma_columns(df)
    data = data.dropna(subset=["SMA_6", "SMA_30"]).reset_index(drop=True)

    if len(data) < 2:
        return None

    # Previous day vs current day relationship
    prev_diff = data["SMA_6"].shift(1) - data["SMA_30"].shift(1)
    curr_diff = data["SMA_6"] - data["SMA_30"]

    bullish = (prev_diff <= 0) & (curr_diff > 0)
    bearish = (prev_diff >= 0) & (curr_diff < 0)

    events = []
    for idx in data.index[bullish]:
        row = data.loc[idx]
        events.append(
            {
                "Signal Type": "Bullish Crossover",
                "Crossover Date": row["date"].date(),
                "Close": round(float(row["close"]), 2),
                "SMA 6": round(float(row["SMA_6"]), 2),
                "SMA 30": round(float(row["SMA_30"]), 2),
            }
        )

    for idx in data.index[bearish]:
        row = data.loc[idx]
        events.append(
            {
                "Signal Type": "Bearish Crossover",
                "Crossover Date": row["date"].date(),
                "Close": round(float(row["close"]), 2),
                "SMA 6": round(float(row["SMA_6"]), 2),
                "SMA 30": round(float(row["SMA_30"]), 2),
            }
        )

    if not events:
        return None

    # Most recent crossover only
    events.sort(key=lambda x: x["Crossover Date"], reverse=True)
    return events[0]


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    # Allow: python "nifty 100_sma_scanner.py" <request_token>
    request_token = sys.argv[1] if len(sys.argv) > 1 else REQUEST_TOKEN

    # --- Credentials + login ---
    api_key, api_secret = read_credentials(CREDENTIALS_FILE)
    kite = create_kite_client(api_key, api_secret, request_token)

    # --- Nifty 100 list ---
    nifty100 = download_nifty100()
    symbols = nifty100["Symbol"].tolist()
    company_map = dict(zip(nifty100["Symbol"], nifty100["Company"]))

    # --- Symbol -> token map ---
    token_map = map_symbols_to_tokens(kite, symbols)

    # --- Scan each stock ---
    rows = []
    total = len(token_map)
    print("Fetching history and scanning for SMA crossovers...")

    for i, (symbol, token) in enumerate(token_map.items(), start=1):
        print(f"[{i}/{total}] {symbol}")
        try:
            hist = fetch_daily_history(kite, token)
            if hist.empty:
                print(f"  -> no history, skipping")
                continue

            signal = find_latest_crossover(hist)
            if signal is None:
                print(f"  -> no crossover found in lookback window")
                continue

            rows.append(
                {
                    "Symbol": symbol,
                    "Company": company_map.get(symbol, symbol),
                    "Signal Type": signal["Signal Type"],
                    "Crossover Date": signal["Crossover Date"],
                    "Close": signal["Close"],
                    "SMA 6": signal["SMA 6"],
                    "SMA 30": signal["SMA 30"],
                }
            )
            print(f"  -> {signal['Signal Type']} on {signal['Crossover Date']}")
        except Exception as exc:
            print(f"  -> error: {exc}")

        time.sleep(SLEEP_SECONDS)

    if not rows:
        print("\nNo crossover signals found.")
        return

    # --- Rank by most recent crossover date ---
    result = pd.DataFrame(rows)
    result = result.sort_values(
        by=["Crossover Date", "Symbol"],
        ascending=[False, True],
    ).reset_index(drop=True)

    result.insert(0, "Rank", range(1, len(result) + 1))

    # Nice column order for output
    result = result[
        [
            "Rank",
            "Symbol",
            "Company",
            "Signal Type",
            "Crossover Date",
            "Close",
            "SMA 6",
            "SMA 30",
        ]
    ]

    print("\n===== Nifty 100 SMA 6/30 Crossover Signals =====\n")
    print(result.to_string(index=False))

    result.to_csv(OUTPUT_CSV, index=False)
    print(f"\nSaved results to: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
