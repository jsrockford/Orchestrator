import os
import stat

import pytest

from src.orchestrator.control_channel import ControlChannel


def test_setup_pipe_creates_fifo(tmp_path):
    pipe_path = tmp_path / "control.fifo"
    channel = ControlChannel(pipe_path=pipe_path)

    channel.setup_pipe()

    try:
        assert pipe_path.exists()
        mode = pipe_path.stat().st_mode
        assert stat.S_ISFIFO(mode)
        assert channel._fd is not None  # noqa: SLF001
    finally:
        channel.cleanup()


def test_check_for_commands_reads_line(tmp_path):
    pipe_path = tmp_path / "control.fifo"
    channel = ControlChannel(pipe_path=pipe_path)
    channel.setup_pipe()

    try:
        fd = os.open(pipe_path, os.O_WRONLY | os.O_NONBLOCK)
        try:
            os.write(fd, b"PAUSE\n")
        finally:
            os.close(fd)

        commands = channel.check_for_commands()
        assert len(commands) == 1
        cmd = commands[0]
        assert cmd.name == "PAUSE"
        assert cmd.args == []
        assert cmd.raw == "PAUSE"
    finally:
        channel.cleanup()


def test_check_for_commands_no_data_returns_empty(tmp_path):
    pipe_path = tmp_path / "control.fifo"
    channel = ControlChannel(pipe_path=pipe_path)
    channel.setup_pipe()
    try:
        assert channel.check_for_commands() == []
    finally:
        channel.cleanup()


def test_partial_command_buffers_until_newline(tmp_path):
    pipe_path = tmp_path / "control.fifo"
    channel = ControlChannel(pipe_path=pipe_path)
    channel.setup_pipe()
    try:
        fd = os.open(pipe_path, os.O_WRONLY | os.O_NONBLOCK)
        try:
            os.write(fd, b"PA")
        finally:
            os.close(fd)

        assert channel.check_for_commands() == []

        fd2 = os.open(pipe_path, os.O_WRONLY | os.O_NONBLOCK)
        try:
            os.write(fd2, b"USE\n")
        finally:
            os.close(fd2)

        commands = channel.check_for_commands()
        assert len(commands) == 1
        assert commands[0].name == "PAUSE"
    finally:
        channel.cleanup()


def test_multiple_writers_enqueue_commands(tmp_path):
    pipe_path = tmp_path / "control.fifo"
    channel = ControlChannel(pipe_path=pipe_path)
    channel.setup_pipe()
    try:
        writers = [
            os.open(pipe_path, os.O_WRONLY | os.O_NONBLOCK),
            os.open(pipe_path, os.O_WRONLY | os.O_NONBLOCK),
        ]
        try:
            os.write(writers[0], b"STATUS\n")
            os.write(writers[1], b"RESUME\n")
        finally:
            for fd in writers:
                os.close(fd)

        commands = channel.check_for_commands()
        assert [cmd.name for cmd in commands] == ["STATUS", "RESUME"]
    finally:
        channel.cleanup()


@pytest.mark.parametrize(
    ("line", "expected_name", "expected_args"),
    [
        ("resume", "RESUME", []),
        ("TEXT gemini hello there", "TEXT", ["gemini", "hello", "there"]),
        ("KEY qwen Up Enter", "KEY", ["qwen", "Up", "Enter"]),
        ("TEXT all: guidance", "TEXT", ["all:", "guidance"]),
        ("KEY gemini Escape", "KEY", ["gemini", "Escape"]),
    ],
)
def test_parse_command_variants(line, expected_name, expected_args):
    channel = ControlChannel(pipe_path="/tmp/ignore")
    command = channel._parse_command(line)  # noqa: SLF001
    assert command.name == expected_name
    assert command.args == expected_args
    assert command.raw == line.strip()


def test_parse_command_rejects_blank():
    channel = ControlChannel(pipe_path="/tmp/ignore")
    with pytest.raises(ValueError):
        channel._parse_command("   ")  # noqa: SLF001
