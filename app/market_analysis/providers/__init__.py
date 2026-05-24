"""Data providers for the market analysis pipeline.

Each provider enriches a list of keywords with metrics from one source
(free APIs, DataForSEO, Google Ads, ...). Providers are composable and
must never raise — they fail silently and return signals unchanged when
their backing source is unavailable.
"""
