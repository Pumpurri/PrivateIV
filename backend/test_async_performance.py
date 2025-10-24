"""
Performance test: Sequential vs Async API calls
Tests fetching stock prices from FMP API using both methods
"""
import os
import time
import asyncio
import requests
import aiohttp
from dotenv import load_dotenv

load_dotenv()

# Same batches as production
BATCHES = [
    'AAPL,MSFT,GOOGL,AMZN,META,NVDA,IBM,ADBE,CRM,ORCL,NOW,PLTR,SAP,CSCO,TSLA,INTC,AMD,QCOM,AVGO,V',
    'MA,PYPL,SQ,HOOD,NFLX,SPOT,EA,U,TTWO,NET,SNOW,CRWD,MDB,RIVN,LCID,NKLA,UBER,LYFT,SNAP,PINS',
    'AI,PATH,WMT,HD,COST,PEP,KO,NKE,F,GM,TM,BRK.B,GS,MS,C,JPM,JNJ,PFE,LLY,ABBV',
    'MRK,XOM,CVX,NEE,DUK,FDX,UPS,BA,LMT,GE,MMM,HON,T,VZ,TMUS,DIS,CMCSA,ADP,BK,SCHW',
]

API_KEY = 'lU7kZOh9e7xeHd8HBzYL00jZzaPovqYO'

if not API_KEY:
    print("ERROR: FMP_API environment variable not found!")
    print("Make sure you have a .env file with FMP_API=your_key")
    exit(1)


def fetch_sequential():
    """Current implementation - sequential requests"""
    print("\n=== SEQUENTIAL (Current Method) ===")
    start = time.time()

    results = []
    for i, symbols in enumerate(BATCHES, 1):
        batch_start = time.time()
        url = f'https://financialmodelingprep.com/api/v3/quote/{symbols}/?apikey={API_KEY}'

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            results.append(data)
            batch_time = time.time() - batch_start
            print(f"  Batch {i}: {batch_time:.3f}s ({len(data)} stocks)")
        except requests.exceptions.RequestException as e:
            print(f"  Batch {i}: ERROR - {e}")

    total_time = time.time() - start
    print(f"  TOTAL: {total_time:.3f}s")
    return total_time, results


async def fetch_batch_async(session, symbols, batch_num):
    """Fetch a single batch asynchronously"""
    url = f'https://financialmodelingprep.com/api/v3/quote/{symbols}/?apikey={API_KEY}'

    batch_start = time.time()
    try:
        async with session.get(url, timeout=10) as response:
            response.raise_for_status()
            data = await response.json()
            batch_time = time.time() - batch_start
            print(f"  Batch {batch_num}: {batch_time:.3f}s ({len(data)} stocks)")
            return data
    except Exception as e:
        print(f"  Batch {batch_num}: ERROR - {e}")
        return None


async def fetch_async():
    """Async implementation - parallel requests"""
    print("\n=== ASYNC (Parallel Method) ===")
    start = time.time()

    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_batch_async(session, symbols, i)
            for i, symbols in enumerate(BATCHES, 1)
        ]
        # All requests fire at once!
        results = await asyncio.gather(*tasks)

    total_time = time.time() - start
    print(f"  TOTAL: {total_time:.3f}s")
    return total_time, results


def main():
    print("="*60)
    print("Stock Price Fetch Performance Test")
    print("="*60)
    print(f"API: Financial Modeling Prep")
    print(f"Batches: {len(BATCHES)}")
    print(f"Total stocks: ~80")

    # Test sequential
    seq_time, seq_results = fetch_sequential()

    # Wait a bit to avoid rate limiting
    print("\nWaiting 2 seconds before async test...")
    time.sleep(2)

    # Test async
    async_time, async_results = asyncio.run(fetch_async())

    # Results
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    print(f"Sequential: {seq_time:.3f}s")
    print(f"Async:      {async_time:.3f}s")
    print(f"Speedup:    {seq_time/async_time:.2f}x faster")
    print(f"Saved:      {seq_time - async_time:.3f}s ({(1 - async_time/seq_time)*100:.1f}% reduction)")
    print("="*60)


if __name__ == "__main__":
    main()
