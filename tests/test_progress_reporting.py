"""Progress stays below completion and reports elapsed work (UI-002)."""
import time

from openlargeprint.sidecar.progress import JobProgress


def test_progress_does_not_finish_before_export():
    events = []
    with JobProgress("job", events.append, interval=.01) as progress:
        progress.update(2, 2, "extracting", "Extracting digital text")
        time.sleep(.04)
        progress.update(2, 2, "exporting", "Writing large-print PDF")
    assert len(events) >= 3
    assert all(event.percent < 100 for event in events)
    assert any(event.elapsed_seconds > 0 for event in events)
    assert events[-1].stage == "exporting"
    count = len(events)
    time.sleep(.02)
    assert len(events) == count
