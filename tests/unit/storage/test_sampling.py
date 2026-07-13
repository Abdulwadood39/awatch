from monitorit.awatch.capture.sampling import should_sample_request


def test_always_sample_errors():
    assert should_sample_request(
        status_code=500,
        duration_ms=1,
        slow_threshold_ms=1000,
        success_sample_rate=0.0,
    )


def test_sample_rate_zero_skips_success():
    assert not should_sample_request(
        status_code=200,
        duration_ms=1,
        slow_threshold_ms=1000,
        success_sample_rate=0.0,
    )


def test_slow_always_kept():
    assert should_sample_request(
        status_code=200,
        duration_ms=5000,
        slow_threshold_ms=1000,
        success_sample_rate=0.0,
    )
