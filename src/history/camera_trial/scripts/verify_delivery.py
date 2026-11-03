"""Read-only checks of delivered archives, checksums, metadata and notebook syntax."""
from pathlib import Path
import ast
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((OUT / 'manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest['source_sha256'].items():
        assert digest(ROOT / name) == expected, 'Source changed after packaging: ' + name
    for name, expected in manifest['compiled_sources_sha256'].items():
        assert digest(ROOT / name) == digest(OUT / 'build_sources' / name) == expected
    payload = ROOT / 'board' / 'camera_stage2'
    assert json.loads((payload / 'manifest.json').read_text(encoding='utf-8')) == manifest
    for name, info in manifest['deployment_files'].items():
        assert digest(payload / name) == info['sha256'], 'Deployment changed: ' + name
    hwh = ET.parse(OUT / 'camera_stage2.hwh')
    instances = {m.attrib.get('INSTANCE') for m in hwh.iter('MODULE')}
    required = {'axi_gpio_control', 'axi_gpio_counts', 'axi_gpio_diag', 'axi_gpio_clock'}
    assert required <= instances, 'Missing GPIO instances in HWH: ' + str(required - instances)
    code_cells = {}
    for nb in sorted((ROOT / 'board').glob('*.ipynb')):
        data = json.loads(nb.read_text(encoding='utf-8'))
        cells = [c for c in data['cells'] if c['cell_type'] == 'code']
        for c in cells:
            ast.parse(''.join(c['source']))
            assert c['execution_count'] is None and c['outputs'] == []
        code_cells[nb.name] = len(cells)
    assert code_cells['01_摄像头启动与显示.ipynb'] == 5
    assert code_cells['00_解压摄像头部署包.ipynb'] == 1
    zip_checks = {}
    for archive_path in (ROOT / 'board' / 'camera_stage2_board.zip', ROOT / 'camera_stage2_source.zip'):
        with zipfile.ZipFile(archive_path) as archive:
            assert archive.testzip() is None
            names = archive.namelist()
            assert not any('reference/vendor/' in name or '__pycache__' in name for name in names)
            zip_checks[archive_path.name] = dict(entries=len(names), bytes=archive_path.stat().st_size)
            if archive_path.name.endswith('_board.zip'):
                for name, info in manifest['deployment_files'].items():
                    assert hashlib.sha256(archive.read('camera_stage2/' + name)).hexdigest() == info['sha256']
    timing = (OUT / 'timing_summary.rpt').read_text(encoding='utf-8', errors='replace')
    assert 'All user specified timing constraints are met.' in timing
    assert re.search(r'checking no_clock \(0\)', timing)
    assert re.search(r'checking unconstrained_internal_endpoints \(0\)', timing)
    cdc = (OUT / 'cdc.rpt').read_text(encoding='utf-8', errors='replace')
    assert not re.search(r'CDC-\d+\s+Critical', cdc), 'Critical CDC findings remain'
    drc = (OUT / 'drc.rpt').read_text(encoding='utf-8', errors='replace')
    assert 'REQP-1839' not in drc, 'BRAM asynchronous control warning remains'
    result = dict(passed=True, source_id=manifest['source_id'], notebook_code_cells=code_cells,
        archives=zip_checks, gpio_instances=sorted(required), implementation_timing='passed',
        cdc_critical_findings=0, bram_async_control_warnings=0,
        physical_camera='not yet observed; requires human observation')
    (OUT / 'delivery_check.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
