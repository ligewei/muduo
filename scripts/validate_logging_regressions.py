"""Negative controls for the two independently based logging PR revisions."""

from pathlib import Path
import subprocess
import sys


BASE = "f1fc77e0c13b80e5086ff457362c8a86d1b609d4"
BIN = Path("build-review/bin").resolve()


def restore(path):
    Path(path).write_bytes(subprocess.check_output(["git", "show", f"{BASE}:{path}"]))


def rebuild(target):
    subprocess.run(
        ["cmake", "--build", "build-review", "--parallel", "2", "--target", target],
        check=True,
    )


def expect_regression(label, *args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=15)
    print(f"{label}: exit {result.returncode}", flush=True)
    print(result.stdout, end="")
    print(result.stderr, end="")
    if result.returncode == 0:
        raise RuntimeError(f"Negative control unexpectedly passed: {label}")
    # Require an actual test failure, not a loader or sanitizer startup failure.
    if ("AsyncLogging_unittest.cc:" not in result.stderr
            and "Logging_unittest:" not in result.stderr
            and "error: in" not in result.stdout):
        raise RuntimeError(f"Negative control failed outside its assertions: {label}")


if sys.argv[1] == "pull_request_fix_bug":
    source = "muduo/base/AsyncLogging.cc"
    restore(source)
    restore("muduo/base/AsyncLogging.h")
    rebuild("asynclogging_unittest")
    for scenario in ("startup", "inflight"):
        expect_regression(f"upstream {scenario}", str(BIN / "asynclogging_unittest"), scenario)

    text = Path(source).read_text()
    text = text.replace("while (running_)", "do", 1)
    text = text.replace("  }\n  output.flush();\n}", "  } while (running_);\n}")
    Path(source).write_text(text)
    rebuild("asynclogging_unittest")
    for scenario in ("empty", "inflight"):
        expect_regression(f"original do-while {scenario}", str(BIN / "asynclogging_unittest"), scenario)
else:
    logging = Path("muduo/base/Logging.cc")
    logging.write_text(logging.read_text().replace(
        '  stream_ << " - " << basename_ << \':\' << line_;\n'
        '  stream_.appendEndOfLine();',
        '  stream_ << " - " << basename_ << \':\' << line_ << \'\\n\';',
    ))
    rebuild("logging_unittest")
    expect_regression(
        "truncated record without its newline",
        str(BIN / "logging_unittest"),
    )

    restore("muduo/base/LogStream.h")
    rebuild("logstream_test")
    expect_regression(
        "upstream all-or-nothing append",
        str(BIN / "logstream_test"), "--run_test=testFixedBufferTruncation",
    )

    # Reconstruct #310's full-capacity append with the original buffer sizes;
    # this isolates its missing debugString() terminator space from resizing.
    source = Path("muduo/base/LogStream.h")
    text = source.read_text().replace(
        "    // FIXME: append partially\n", ""
    ).replace(
        "      cur_ += len;\n    }\n",
        "      cur_ += len;\n    }\n"
        "    else\n    {\n"
        "      size_t n = static_cast<size_t>(avail());\n"
        "      memcpy(cur_, buf, n);\n"
        "      cur_ += n;\n    }\n", 1,
    )
    source.write_text(text)
    rebuild("logstream_test")
    expect_regression(
        "original full-capacity append",
        str(BIN / "logstream_test"), "--run_test=testFixedBufferTruncation",
    )
