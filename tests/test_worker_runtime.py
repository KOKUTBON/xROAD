from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.workers.tasks.ingestion import run_job_logic as run_ingestion_job_logic  # noqa: E402
from services.workers.tasks.published_refresh import run_job_logic  # noqa: E402
from services.workers.tasks.reports import run_report_logic  # noqa: E402


class WorkerRuntimeTests(unittest.TestCase):
    def test_run_job_logic_executes_service_and_commits_session(self) -> None:
        class FakeSession:
            def __init__(self) -> None:
                self.committed = 0
                self.closed = 0

            def commit(self) -> None:
                self.committed += 1

            def close(self) -> None:
                self.closed += 1

        fake_session = FakeSession()
        job = SimpleNamespace(id="job-1")
        with (
            patch("services.workers.tasks.published_refresh.SessionLocal", return_value=fake_session),
            patch(
                "services.workers.tasks.published_refresh.get_ingestion_job",
                return_value=job,
            ),
            patch(
                "services.workers.tasks.published_refresh.execute_published_refresh_job",
                return_value={"job_id": "job-1", "status": "completed"},
            ) as execute_mock,
        ):
            payload = run_job_logic("job-1")

        execute_mock.assert_called_once_with(fake_session, job)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(fake_session.committed, 1)
        self.assertEqual(fake_session.closed, 1)

    def test_run_ingestion_job_logic_executes_service_and_commits_session(self) -> None:
        class FakeSession:
            def __init__(self) -> None:
                self.committed = 0
                self.closed = 0

            def commit(self) -> None:
                self.committed += 1

            def close(self) -> None:
                self.closed += 1

        fake_session = FakeSession()
        job = SimpleNamespace(id="job-1")
        with (
            patch("services.workers.tasks.ingestion.SessionLocal", return_value=fake_session),
            patch(
                "services.workers.tasks.ingestion.get_ingestion_job",
                return_value=job,
            ),
            patch(
                "services.workers.tasks.ingestion.execute_ingestion_job",
                return_value={"job_id": "job-1", "status": "completed"},
            ) as execute_mock,
        ):
            payload = run_ingestion_job_logic("job-1")

        execute_mock.assert_called_once_with(fake_session, job)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(fake_session.committed, 1)
        self.assertEqual(fake_session.closed, 1)

    def test_run_report_logic_executes_service_and_commits_session(self) -> None:
        class FakeSession:
            def __init__(self) -> None:
                self.committed = 0
                self.closed = 0

            def commit(self) -> None:
                self.committed += 1

            def close(self) -> None:
                self.closed += 1

        fake_session = FakeSession()
        report = SimpleNamespace(id="report-1")
        with (
            patch("services.workers.tasks.reports.SessionLocal", return_value=fake_session),
            patch("services.workers.tasks.reports.get_report", return_value=report),
            patch(
                "services.workers.tasks.reports.execute_report_generation",
                return_value={"report": {"report_id": "report-1", "status": "generated"}},
            ) as execute_mock,
            patch("services.workers.tasks.reports.get_settings", return_value=SimpleNamespace()),
        ):
            payload = run_report_logic("report-1")

        execute_mock.assert_called_once()
        self.assertEqual(payload["report"]["status"], "generated")
        self.assertEqual(fake_session.committed, 1)
        self.assertEqual(fake_session.closed, 1)
