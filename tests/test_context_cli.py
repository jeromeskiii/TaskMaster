import contextlib
import io
from taskmaster import cli

def test_context_cli_subparsers():
    parser = cli.build_parser()
    # Parse "context stats" args and verify they map correctly
    args = parser.parse_args(["context", "stats"])
    assert args.command == "context"
    assert args.context_command == "stats"

def test_context_cli_args_parsing():
    parser = cli.build_parser()
    
    # Test compress subcommand
    args = parser.parse_args(["context", "compress", "some_file.txt", "--max-chars", "1000"])
    assert args.command == "context"
    assert args.context_command == "compress"
    assert args.file == "some_file.txt"
    assert args.max_chars == 1000

    # Test compress without file
    args = parser.parse_args(["context", "compress", "--max-chars", "500"])
    assert args.file is None
    assert args.max_chars == 500

    # Test retrieve subcommand
    args = parser.parse_args(["context", "retrieve", "some-handle"])
    assert args.command == "context"
    assert args.context_command == "retrieve"
    assert args.handle == "some-handle"

    # Test prune subcommand
    args = parser.parse_args(["context", "prune", "--max-age-days", "5.5"])
    assert args.command == "context"
    assert args.context_command == "prune"
    assert args.max_age_days == 5.5

def test_cmd_context_dispatch_compress(capsys):
    from unittest.mock import patch, MagicMock
    from taskmaster.context_budget_manager.models import CompressionResult, ContentType
    
    with patch("taskmaster.context_budget_manager.core.ContextBudgetManager") as MockCBM:
        mock_instance = MockCBM.return_value
        dummy_result = CompressionResult(
            handle="test-handle",
            content_type=ContentType.TEXT,
            original_tokens=100,
            compressed_tokens=50,
            compression_ratio=0.5,
            compressed_text="dummy text",
            metadata={}
        )
        mock_instance.compress.return_value = dummy_result

        parser = cli.build_parser()
        args = parser.parse_args(["context", "compress", "--max-chars", "200"])

        with patch("sys.stdin.read", return_value="hello world"):
            result = cli._cmd_context(args)

        assert result == 0
        mock_instance.compress.assert_called_once_with("hello world", max_chars=200)
        captured = capsys.readouterr()
        assert "dummy text" in captured.out
        assert "handle=test-handle" in captured.out
        assert "type=text" in captured.out

def test_cmd_context_dispatch_retrieve(capsys):
    from unittest.mock import patch
    
    with patch("taskmaster.context_budget_manager.core.ContextBudgetManager") as MockCBM:
        mock_instance = MockCBM.return_value
        mock_instance.retrieve.return_value = "original text content"

        parser = cli.build_parser()
        args = parser.parse_args(["context", "retrieve", "handle-xyz"])

        result = cli._cmd_context(args)

        assert result == 0
        mock_instance.retrieve.assert_called_once_with("handle-xyz")
        captured = capsys.readouterr()
        assert "original text content" in captured.out.strip()

def test_cmd_context_dispatch_stats(capsys):
    from unittest.mock import patch
    
    with patch("taskmaster.context_budget_manager.core.ContextBudgetManager") as MockCBM:
        mock_instance = MockCBM.return_value
        mock_instance.stats.return_value = {"num_records": 42}

        parser = cli.build_parser()
        args = parser.parse_args(["context", "stats"])

        result = cli._cmd_context(args)

        assert result == 0
        mock_instance.stats.assert_called_once()
        captured = capsys.readouterr()
        assert "{'num_records': 42}" in captured.out.strip()

def test_cmd_context_dispatch_prune(capsys):
    from unittest.mock import patch
    
    with patch("taskmaster.context_budget_manager.core.ContextBudgetManager") as MockCBM:
        mock_instance = MockCBM.return_value
        mock_instance.prune.return_value = 5

        parser = cli.build_parser()
        args = parser.parse_args(["context", "prune", "--max-age-days", "2.5"])

        result = cli._cmd_context(args)

        assert result == 0
        mock_instance.prune.assert_called_once_with(2.5 * 86400.0)
        captured = capsys.readouterr()
        assert "Successfully pruned 5 context payload(s)." in captured.out.strip()


def test_seconds_per_day_constant():
    assert hasattr(cli, "SECONDS_PER_DAY")
    assert cli.SECONDS_PER_DAY == 86400.0


def test_cmd_context_dispatch_error(capsys):
    from unittest.mock import patch
    with patch("taskmaster.context_budget_manager.core.ContextBudgetManager") as MockCBM:
        MockCBM.return_value.stats.side_effect = Exception("DB Connection Refused")
        parser = cli.build_parser()
        args = parser.parse_args(["context", "stats"])
        
        result = cli._cmd_context(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "cbm error: DB Connection Refused" in captured.err



