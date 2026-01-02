"""
Test history read-only service.

This module provides read operations for test run history and related entities.
"""

from typing import List, Optional
from uuid import UUID

from services.database_service import DatabaseService
from models.test_suite_models import (
    TestRunHistory, TestCaseResult, TestAlert, TestRunWithResults, TestCaseResultWithAlerts
)
from telemetrics.logger import logger


class TestRunHistoryService(DatabaseService[TestRunHistory]):
    """Service for test run history read operations."""

    def __init__(self):
        super().__init__("test_run_history")

    async def get_test_run(self, run_id: UUID) -> Optional[TestRunHistory]:
        """Get a test run by ID."""
        result = await self.get_by_id(run_id)
        if result:
            return TestRunHistory(**result)
        return None

    async def get_test_runs_by_suite(
        self, suite_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[TestRunHistory]:
        """Get test runs for a test suite."""
        supabase_client = await self._get_client()

        try:
            results = await supabase_client.select(
                "test_run_history",
                filters={"test_suite_id": str(suite_id)},
                order_by="started_at.desc",
                limit=limit,
                offset=offset
            )

            if not results:
                return []

            return [TestRunHistory(**result) for result in results]
        except Exception as e:
            logger.error(f"Error fetching test runs for suite {suite_id}: {e}")
            raise

    async def get_test_runs_by_user(
        self, user_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[TestRunHistory]:
        """Get test runs for a user."""
        results = await self.get_all_by_user(user_id, limit, offset)
        return [TestRunHistory(**result) for result in results]

    async def get_test_run_with_results(self, run_id: UUID) -> Optional[TestRunWithResults]:
        """Get a test run with all its results."""
        # Get the test run
        test_run = await self.get_test_run(run_id)
        if not test_run:
            return None

        # Get test case results
        results_service = TestCaseResultService()
        test_case_results = await results_service.get_results_by_run(run_id)

        return TestRunWithResults(
            **test_run.model_dump(),
            test_case_results=test_case_results
        )


class TestCaseResultService(DatabaseService[TestCaseResult]):
    """Service for test case result read operations."""

    def __init__(self):
        super().__init__("test_case_results")

    async def get_result(self, result_id: UUID) -> Optional[TestCaseResult]:
        """Get a test case result by ID."""
        result = await self.get_by_id(result_id)
        if result:
            return TestCaseResult(**result)
        return None

    async def get_results_by_run(self, run_id: UUID) -> List[TestCaseResult]:
        """Get all results for a test run."""
        supabase_client = await self._get_client()

        try:
            results = await supabase_client.select(
                "test_case_results",
                filters={"test_run_id": str(run_id)},
                order_by="started_at"
            )

            if not results:
                return []

            return [TestCaseResult(**result) for result in results]
        except Exception as e:
            logger.error(f"Error fetching results for run {run_id}: {e}")
            raise

    async def get_results_by_case(self, case_id: UUID, limit: int = 100) -> List[TestCaseResult]:
        """Get results for a specific test case."""
        supabase_client = await self._get_client()

        try:
            results = await supabase_client.select(
                "test_case_results",
                filters={"test_case_id": str(case_id)},
                order_by="started_at.desc",
                limit=limit
            )

            if not results:
                return []

            return [TestCaseResult(**result) for result in results]
        except Exception as e:
            logger.error(f"Error fetching results for case {case_id}: {e}")
            raise

    async def get_result_with_alerts(self, result_id: UUID) -> Optional[TestCaseResultWithAlerts]:
        """Get a test case result with all its alerts."""
        # Get the result
        test_result = await self.get_result(result_id)
        if not test_result:
            return None

        # Get alerts
        alerts_service = TestAlertService()
        alerts = await alerts_service.get_alerts_by_result(result_id)

        return TestCaseResultWithAlerts(
            **test_result.model_dump(),
            alerts=alerts
        )


class TestAlertService(DatabaseService[TestAlert]):
    """Service for test alert read operations."""

    def __init__(self):
        super().__init__("test_alerts")

    async def get_alert(self, alert_id: UUID) -> Optional[TestAlert]:
        """Get a test alert by ID."""
        result = await self.get_by_id(alert_id)
        if result:
            return TestAlert(**result)
        return None

    async def get_alerts_by_result(self, result_id: UUID) -> List[TestAlert]:
        """Get all alerts for a test case result."""
        supabase_client = await self._get_client()

        try:
            results = await supabase_client.select(
                "test_alerts",
                filters={"test_case_result_id": str(result_id)},
                order_by="created_at"
            )

            if not results:
                return []

            return [TestAlert(**result) for result in results]
        except Exception as e:
            logger.error(f"Error fetching alerts for result {result_id}: {e}")
            raise

    async def get_alerts_by_severity(self, severity: str, limit: int = 100) -> List[TestAlert]:
        """Get alerts by severity level."""
        supabase_client = await self._get_client()

        try:
            results = await supabase_client.select(
                "test_alerts",
                filters={"severity": severity},
                order_by="created_at.desc",
                limit=limit
            )

            if not results:
                return []

            return [TestAlert(**result) for result in results]
        except Exception as e:
            logger.error(f"Error fetching alerts by severity {severity}: {e}")
            raise
