import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.services.process_orchestrator import ProcessOrchestrator, ProcessResult


class ProcessOrchestratorTests(unittest.TestCase):
    @patch("src.services.process_orchestrator.load_conceptos_admin")
    @patch("src.services.process_orchestrator.sync_conceptos_from_admin")
    def test_run_executes_full_sequence_and_returns_result(
        self,
        mock_sync: MagicMock,
        mock_load_admin: MagicMock,
    ) -> None:
        matrix_path = Path("data/output/MATRIZ_FBL1N_TEST.xlsx")
        audit_path = Path("data/output/CONCEPT_AUDIT_TEST.xlsx")
        pivot_path = Path("data/output/PIVOT_MARGEN_TEST.xlsx")

        margen = MagicMock()
        output = MagicMock()
        output.latest_or_raise.return_value = matrix_path

        audit = MagicMock()
        audit.generate.return_value = (MagicMock(), audit_path)

        pivot = MagicMock()
        pivot.generate.return_value = (MagicMock(), pivot_path)

        sharepoint = MagicMock()
        sharepoint.health_check.return_value = {
            "configured": True,
            "missing": [],
        }

        orchestrator = ProcessOrchestrator(
            margen_module=margen,
            audit_service=audit,
            pivot_service=pivot,
            sharepoint_service=sharepoint,
            output_service=output,
        )
        orchestrator.generate_concept_audit = MagicMock(return_value=audit_path)
        orchestrator.generate_pivot = MagicMock(return_value=pivot_path)

        result = orchestrator.run()

        mock_sync.assert_called_once()
        mock_load_admin.assert_called_once()
        margen.run.assert_called_once()
        orchestrator.generate_concept_audit.assert_called_once_with(matrix_path)
        orchestrator.generate_pivot.assert_called_once_with(matrix_path)
        sharepoint.health_check.assert_called_once()

        self.assertIsInstance(result, ProcessResult)
        self.assertTrue(result.success)
        self.assertEqual(result.matrix_file, matrix_path)
        self.assertEqual(result.audit_file, audit_path)
        self.assertEqual(result.pivot_file, pivot_path)
        self.assertTrue(result.sharepoint_ready)
        self.assertEqual(result.errors, [])
        self.assertIsInstance(result.start_time, datetime)
        self.assertIsInstance(result.end_time, datetime)
        self.assertGreaterEqual(result.duration_ms, 0.0)

    @patch("src.services.process_orchestrator.load_conceptos_admin")
    @patch("src.services.process_orchestrator.sync_conceptos_from_admin")
    def test_run_collects_errors_without_raising(
        self,
        mock_sync: MagicMock,
        mock_load_admin: MagicMock,
    ) -> None:
        margen = MagicMock()
        margen.run.side_effect = RuntimeError("pipeline falló")
        output = MagicMock()
        sharepoint = MagicMock()
        sharepoint.health_check.return_value = {
            "configured": False,
            "missing": ["CLIENT_ID"],
        }

        orchestrator = ProcessOrchestrator(
            margen_module=margen,
            output_service=output,
            sharepoint_service=sharepoint,
            audit_service=MagicMock(),
            pivot_service=MagicMock(),
        )

        result = orchestrator.run()

        mock_sync.assert_called_once()
        mock_load_admin.assert_called_once()
        self.assertFalse(result.success)
        self.assertIsNone(result.matrix_file)
        self.assertIsNone(result.audit_file)
        self.assertIsNone(result.pivot_file)
        self.assertFalse(result.sharepoint_ready)
        self.assertTrue(any("create_matrix" in error for error in result.errors))
        sharepoint.health_check.assert_called_once()

    def test_check_sharepoint_returns_ready_flag(self) -> None:
        sharepoint = MagicMock()
        sharepoint.health_check.return_value = {
            "configured": True,
            "missing": [],
        }
        orchestrator = ProcessOrchestrator(
            sharepoint_service=sharepoint,
            margen_module=MagicMock(),
            audit_service=MagicMock(),
            pivot_service=MagicMock(),
            output_service=MagicMock(),
        )
        self.assertTrue(orchestrator.check_sharepoint())


if __name__ == "__main__":
    unittest.main()
