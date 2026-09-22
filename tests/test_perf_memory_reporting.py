"""Peak-memory reporting used by the benchmark and acceptance runs (PERF-002)."""

from openlargeprint.qa.benchmark import get_current_ram_mb


def test_peak_memory_reporting_returns_real_numbers():
    """The reported peak must be a real measurement, not a silent zero (PERF-002).

    The Windows implementation calls GetProcessMemoryInfo through ctypes. An
    untyped process handle gets truncated to 32 bits, the call fails, and the
    function returns 0.0 while still looking healthy, which makes every
    performance report meaningless. A zero is therefore asserted against.
    """
    # Touch memory so a working-set measurement has something to report.
    ballast = bytearray(8 * 1024 * 1024)
    ballast[1::4096] = b"1" * len(ballast[1::4096])
    assert ballast[0] == 0 and ballast[1] == ord("1")

    peak_mb = get_current_ram_mb()

    assert isinstance(peak_mb, float)
    assert peak_mb > 1.0, f"peak memory reporting returned {peak_mb} MB"
