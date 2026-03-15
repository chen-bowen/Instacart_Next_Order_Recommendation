#!/usr/bin/env python3
"""
Upload eval_corpus.json to the Hugging Face Hub.

Usage:
  uv run python scripts/upload_corpus_to_hf.py --repo-id YOUR_USERNAME/instacart-eval-corpus

By default uploads to a dataset repo. Use --repo-type model to add to a model repo instead.
Authenticate with: huggingface-cli login or HF_TOKEN in .env.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from dotenv import load_dotenv
from huggingface_hub import HfApi

from src.constants import (
    DEFAULT_CONFIG_UPLOAD_CORPUS,
    DEFAULT_CORPUS_PATH,
    DEFAULT_DOTENV_PATH,
    DEFAULT_PROCESSED_DIR,
    EVAL_CORPUS_FILENAME,
    PROJECT_ROOT,
)
from src.utils import resolve_corpus_with_hf_fallback, resolve_processed_dir

load_dotenv(DEFAULT_DOTENV_PATH)


def load_config(config_path: Path | None = None) -> dict:
    """Load upload config from YAML. Returns repo_id, corpus_path, repo_type, private."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_UPLOAD_CORPUS
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    corpus_path = raw.get("corpus_path")
    if corpus_path and not Path(str(corpus_path)).is_absolute():
        corpus_path = PROJECT_ROOT / corpus_path
    return {
        "repo_id": raw.get("repo_id"),
        "corpus_path": Path(corpus_path) if corpus_path else None,
        "repo_type": raw.get("repo_type", "dataset"),
        "private": bool(raw.get("private", False)),
    }


def resolve_corpus_path(corpus_path: Path | None, processed_dir: Path | None) -> Path:
    """Resolve path to eval_corpus.json, auto-resolving from processed/ if needed."""
    if corpus_path and corpus_path.is_file():
        return corpus_path
    if corpus_path and corpus_path.is_dir():
        candidate = corpus_path / EVAL_CORPUS_FILENAME
        if candidate.is_file():
            return candidate
    # Auto-resolve from processed/; if not found, download from HF
    try:
        resolved, _ = resolve_processed_dir(
            processed_dir or DEFAULT_PROCESSED_DIR, DEFAULT_PROCESSED_DIR
        )
        candidate = resolved / EVAL_CORPUS_FILENAME
    except FileNotFoundError:
        candidate = DEFAULT_CORPUS_PATH
    return resolve_corpus_with_hf_fallback(candidate)


def main() -> None:
    """CLI entrypoint: load config, create HF repo if needed, upload eval_corpus.json."""
    parser = argparse.ArgumentParser(
        description="Upload eval_corpus.json to the Hugging Face Hub."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=f"Path to YAML config (default: {DEFAULT_CONFIG_UPLOAD_CORPUS.relative_to(PROJECT_ROOT)})",
    )
    parser.add_argument(
        "--repo-id",
        type=str,
        default=None,
        help="Override repo_id from config (e.g. USER/instacart-eval-corpus)",
    )
    parser.add_argument(
        "--corpus-path",
        type=Path,
        default=None,
        help="Path to eval_corpus.json (default: auto-resolve from processed/)",
    )
    parser.add_argument(
        "--repo-type",
        type=str,
        choices=["dataset", "model"],
        default=None,
        help="HF repo type: dataset (default) or model",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    repo_id = args.repo_id or cfg["repo_id"]
    if not repo_id:
        raise SystemExit(
            "repo_id is required. Set it in configs/upload_corpus.yaml or pass "
            "--repo-id YOUR_USERNAME/instacart-eval-corpus"
        )

    corpus_path = resolve_corpus_path(
        args.corpus_path or cfg["corpus_path"],
        DEFAULT_PROCESSED_DIR,
    )
    repo_type = args.repo_type or cfg["repo_type"]

    api = HfApi()
    api.create_repo(
        repo_id=repo_id,
        repo_type=repo_type,
        private=cfg["private"],
        exist_ok=True,
    )
    api.upload_file(
        path_or_fileobj=str(corpus_path),
        path_in_repo=EVAL_CORPUS_FILENAME,
        repo_id=repo_id,
        repo_type=repo_type,
    )
    base = "https://huggingface.co/datasets" if repo_type == "dataset" else "https://huggingface.co"
    print(f"Uploaded {corpus_path} to {base}/{repo_id}")


if __name__ == "__main__":
    main()
