# Workers

This directory contains the async worker runtime for product-facing backend jobs.

Current responsibilities:

- worker bootstrap and Redis-backed Celery configuration
- health-check tasks for ops visibility
- executable upload ingestion tasks for approved crash CSV and exposure connector jobs
- published-refresh backend jobs
- report-generation jobs

Primary task names:

- `services.workers.tasks.ingestion.run_job`
- `services.workers.tasks.published_refresh.run_job`
- `services.workers.tasks.reports.run_report`
