import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
PY = sys.executable


def run_collect(*args):
    cmd = [PY, str(SCRIPTS / 'collect_stickers.py'), *args]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_collect_single_thread_and_trim_to_target(tmp_path):
    sources = []
    for idx in range(5):
        path = tmp_path / f'source_{idx}.gif'
        path.write_bytes(b'GIF89a' + bytes([idx]) * (12000 + idx))
        sources.append(str(path))
    out_dir = tmp_path / 'out'
    result = run_collect(*sources, '--out-dir', str(out_dir), '--prefix', '测试', '--target-count', '3', '--workers', '4')
    assert result.returncode == 0
    assert 'EFFECTIVE_WORKERS=1' in result.stdout
    assert 'WORKERS_IGNORED=4' in result.stdout
    assert 'FINAL_COUNT=3' in result.stdout
    kept = list(out_dir.iterdir())
    assert len(kept) == 3


def test_collect_dedupes_and_reports_need_more(tmp_path):
    a = tmp_path / 'a.gif'
    b = tmp_path / 'b.gif'
    c = tmp_path / 'c.gif'
    a.write_bytes(b'GIF89a' + b'x' * 12000)
    b.write_bytes(b'GIF89a' + b'x' * 12000)
    c.write_bytes(b'GIF89a' + b'y' * 500)  # low quality
    out_dir = tmp_path / 'out'
    result = run_collect(str(a), str(b), str(c), '--out-dir', str(out_dir), '--prefix', '测试', '--target-count', '2')
    assert result.returncode == 2
    assert 'DUPLICATES=1' in result.stdout
    assert 'LOW_QUALITY=1' in result.stdout
    assert 'NEED_MORE=1' in result.stdout


def test_collect_can_disable_semantic_plan(tmp_path):
    source = tmp_path / 'single.gif'
    source.write_bytes(b'GIF89a' + b'z' * 15000)
    out_dir = tmp_path / 'out'
    result = run_collect(str(source), '--out-dir', str(out_dir), '--prefix', '测试', '--target-count', '1', '--no-semantic-plan')
    assert result.returncode == 0
    assert '__SEMANTIC_BATCH__:' not in result.stdout
