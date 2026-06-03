from __future__ import annotations

import json
from pathlib import Path

from taskmaster.cli import build_parser


def test_embed_subcommand_registered():
    parser = build_parser()
    args = parser.parse_args(["embed", "--rebuild"])
    assert args.command == "embed"
    assert args.rebuild is True


def test_recommend_subcommand_registered():
    parser = build_parser()
    args = parser.parse_args(["recommend", "postgres", "--max", "3"])
    assert args.command == "recommend"
    assert args.task == "postgres"
    assert args.max == 3


def test_compose_subcommand_registered():
    parser = build_parser()
    args = parser.parse_args(["compose", "a", "b", "--json"])
    assert args.command == "compose"
    assert args.skills == ["a", "b"]
    assert args.json is True
