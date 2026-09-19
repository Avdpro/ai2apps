from ai2apps.download_progress import DownloadProgress


def test_download_measurement_excludes_resume_bytes_and_survives_verification():
    meter = DownloadProgress()
    base = dict(stage='downloading_package', fileName='runtime.ai2service', bytesTotal=4096)
    assert meter.update({**base, 'bytesCompleted': 1024}, now=0)['download']['bytesPerSecond'] is None
    sample = meter.update({**base, 'bytesCompleted': 2048}, now=1)['download']
    assert sample['bytesPerSecond'] == 1024
    assert sample['etaSeconds'] == 2
    assert meter.update({'stage': 'verifying_package'}, now=2)['download'] == sample
    assert meter.update({**base, 'bytesCompleted': 0}, now=3)['download']['bytesPerSecond'] is None


def test_checkpoint_speed_uses_aggregate_bytes_across_file_changes():
    meter = DownloadProgress()
    base = dict(stage='downloading_checkpoint', distributionId='model', totalBytesTotal=4096)
    meter.update({**base, 'fileName': 'a', 'totalBytesCompleted': 0}, now=0)
    result = meter.update({**base, 'fileName': 'b', 'totalBytesCompleted': 2048}, now=2)['download']
    assert result['bytesPerSecond'] == 1024
    assert result['etaSeconds'] == 2
    assert result['fileName'] == 'b'
    for now in range(3, 9):
        result = meter.update({**base, 'fileName': 'b', 'totalBytesCompleted': 2048}, now=now)['download']
    assert result['bytesPerSecond'] == 0
    assert result['etaSeconds'] is None
