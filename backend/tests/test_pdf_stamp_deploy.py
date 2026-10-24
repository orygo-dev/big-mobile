"""Exercise deployment publication and rollback without touching a real server."""
import os
from pathlib import Path
import re
import subprocess

import pytest

pytestmark = pytest.mark.skipif(os.name == 'nt', reason='Linux deployment smoke test')


@pytest.mark.parametrize('script_name,failure', [
    ('update-pdf-stamp.sh', ''), ('update-pdf-stamp.sh', 'build'), ('update-pdf-stamp.sh', 'health'),
    ('update-stamp-layout.sh', ''), ('update-stamp-layout.sh', 'build'),
])
def test_staged_build_keeps_old_site_on_failure(tmp_path, script_name, failure):
    repo = Path(__file__).resolve().parents[2]
    script = (repo / 'deploy' / script_name).read_text()
    root = tmp_path / 'project'; root.mkdir()
    source = tmp_path / 'download'; source.mkdir()
    binaries = tmp_path / 'bin'; binaries.mkdir()
    files = re.search(r'files=\(\n(.*?)\n\)', script, re.S).group(1).split()
    for file in files:
        for base, text in [(root, 'old ' + file), (source, 'new ' + file)]:
            target = base / file; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(text)
    (root / 'frontend/node_modules/pdfjs-dist').mkdir(parents=True)
    if not (root / 'frontend/package.json').exists(): (root / 'frontend/package.json').write_text('{}')
    build = root / 'frontend/build'; (build / 'assets').mkdir(parents=True)
    (build / 'index.html').write_text('old HTML'); (build / 'assets/old.js').write_text('old JS')
    protected = build / '.user.ini'; protected.write_text('protected aaPanel configuration'); protected.chmod(0o444)
    def executable(path, text):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text('#!/usr/bin/env bash\nset -eu\n' + text); path.chmod(0o755)
    executable(root / '.venv/bin/python', 'exit 0\n')
    executable(binaries / 'curl', '''
if [[ "$*" == *"--location"* ]]; then
  while [ "$#" -gt 0 ]; do
    if [[ "$1" == https://raw.githubusercontent.com/* ]]; then file="${1#*/big-mobile/}"; file="${file#*/}"; fi
    if [ "$1" = -o ]; then target="$2"; fi
    shift
  done
  cp "$DOWNLOAD/$file" "$target"
elif [[ "$*" == *"--write-out"* ]]; then printf '401'
elif [ "$FAILURE" = health ]; then exit 22
else printf '{"status":"ready","database":"ready"}'
fi
''')
    executable(binaries / 'npm', '''
if [[ "$*" == *" run build "* ]]; then
  if [ "$FAILURE" = build ]; then exit 8; fi
  output="${@: -1}"
  mkdir -p "$output/assets"; printf 'new JS' > "$output/assets/new.js"; printf 'new HTML' > "$output/index.html"
fi
''')
    executable(binaries / 'systemctl', 'printf "%s\\n" "$*" >> "$CALL_LOG"\n')
    executable(binaries / 'journalctl', 'exit 0\n')
    executable(binaries / 'sleep', 'exit 0\n')
    script = script.replace('root=/www/wwwroot/big.rebornpartner.xyz', 'root=' + str(root))
    result = subprocess.run(['bash'], input=script, text=True, capture_output=True, timeout=30,
                            env={**os.environ, 'PATH': str(binaries) + os.pathsep + os.environ['PATH'],
                                 'DOWNLOAD': str(source), 'FAILURE': failure, 'CALL_LOG': str(tmp_path / 'calls')})
    assert protected.read_text() == 'protected aaPanel configuration'
    assert (build / 'assets/old.js').read_text() == 'old JS'
    if failure:
        assert result.returncode != 0, result.stdout + result.stderr
        assert (build / 'index.html').read_text() == 'old HTML'
        for file in files:
            assert (root / file).read_text() == 'old ' + file
        if failure == 'build': assert not (tmp_path / 'calls').exists()
        else: assert (tmp_path / 'calls').read_text().count('restart big-mobile') == 2
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert (build / 'index.html').read_text() == 'new HTML'
        assert (build / 'assets/new.js').read_text() == 'new JS'
        if script_name == 'update-pdf-stamp.sh': assert (tmp_path / 'calls').read_text().count('restart big-mobile') == 1
        else: assert not (tmp_path / 'calls').exists()
