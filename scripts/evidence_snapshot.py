"""Validate immutable v1 engine sources after the working tree moves forward."""
import hashlib
from pathlib import Path
import subprocess

V1_SOURCE_REF = '9d13c05'


def assert_sources(expected):
    prefix = Path('src/smaip')
    current = {str(p.relative_to(prefix)): hashlib.sha256(p.read_bytes()).hexdigest() for p in prefix.rglob('*.py')}
    if current == expected:
        return 'working-tree'
    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', V1_SOURCE_REF, '--', 'src/smaip'], text=True).splitlines()
    frozen = {}
    for name in names:
        if name.endswith('.py'):
            content = subprocess.check_output(['git', 'show', f'{V1_SOURCE_REF}:{name}'])
            frozen[str(Path(name).relative_to(prefix))] = hashlib.sha256(content).hexdigest()
    assert frozen == expected, 'source hashes differ from preserved v1 commit'
    return 'git:' + V1_SOURCE_REF
