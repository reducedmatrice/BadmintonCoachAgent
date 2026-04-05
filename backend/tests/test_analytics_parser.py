"""Tests for analytics structured log parsing."""

from __future__ import annotations

import json

from app.analytics.parser import (
    parse_manager_structured_log_file,
    parse_manager_structured_log_line,
    parse_manager_structured_log_text,
)


def test_parse_manager_structured_log_line_normalizes_fields():
    line = (
        '2026-04-05 12:30:45,123 INFO [ManagerStructured] '
        '{"event":"channel_run_completed","channel":"feishu","thread_id":"thread-1",'
        '"route":{"assistant_id":"lead_agent","agent_name":"badminton-coach","streaming":1},'
        '"latency_ms":842.7,"response_length":12,"artifact_count":1,"error":"false","error_type":"",'
        '"token_usage":{"prompt_tokens":120,"completion_tokens":48},'
        '"memory_hits":{"coach_profile":true,"review_log":false,"memory_json":true,"weather":false}}'
    )

    parsed = parse_manager_structured_log_line(
        line,
        source_file="logs/gateway.log",
        line_number=9,
    )

    assert parsed is not None
    assert parsed["source_file"] == "logs/gateway.log"
    assert parsed["source_line_number"] == 9
    assert parsed["created_at"] == "2026-04-05T12:30:45.123"
    assert parsed["assistant_id"] == "lead_agent"
    assert parsed["agent_name"] == "badminton-coach"
    assert parsed["error"] is False
    assert parsed["input_tokens"] == 120
    assert parsed["output_tokens"] == 48
    assert parsed["total_tokens"] == 168

    route = json.loads(parsed["route_json"])
    memory_hits = json.loads(parsed["memory_hits_json"])

    assert route["streaming"] is True
    assert memory_hits["status"] == "hit"
    assert parsed["raw_json"].startswith('{"artifact_count":1')


def test_parse_manager_structured_log_text_skips_invalid_json_and_non_structured_lines():
    text = "\n".join(
        [
            "INFO normal line without marker",
            'INFO [ManagerStructured] {"event":"channel_run_completed","route":{"assistant_id":"lead_agent"}}',
            'INFO [ManagerStructured] {"event":"channel_run_completed",invalid}',
        ]
    )

    parsed_records = parse_manager_structured_log_text(text, source_file="logs/gateway.log")

    assert len(parsed_records) == 1
    assert parsed_records[0]["assistant_id"] == "lead_agent"
    assert parsed_records[0]["input_tokens"] is None
    assert parsed_records[0]["error"] is False


def test_parse_manager_structured_log_file_reads_from_disk(tmp_path):
    log_path = tmp_path / "gateway.log"
    log_path.write_text(
        'INFO [ManagerStructured] {"event":"channel_run_completed","error":true,"route":{"agent_name":"coach"}}\n',
        encoding="utf-8",
    )

    parsed_records = parse_manager_structured_log_file(log_path)

    assert len(parsed_records) == 1
    assert parsed_records[0]["source_file"] == log_path.as_posix()
    assert parsed_records[0]["agent_name"] == "coach"
    assert parsed_records[0]["error"] is True
