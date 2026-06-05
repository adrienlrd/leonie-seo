"""Daily GEO agent automation scheduling.

Orchestration layer on top of ``app.learning.scheduler.run_learning_cycle``.
It does NOT introduce a second agent: it only decides *when* the existing
continuous-improvement learning cycle runs for each shop.
"""
