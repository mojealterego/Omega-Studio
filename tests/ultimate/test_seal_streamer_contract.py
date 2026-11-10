"""Public integrity and large-file stream contracts shared with GitHub mirror."""
from pathlib import Path
import pytest
from omega_actions.ultimate.seal import graph_invariants, seal_python_source, verify_seal
from omega_actions.ultimate.streamer import WindowedReader, copy_file


def test_graph_topology_and_authenticated_seal():
    assert graph_invariants(3, [(0,1),(1,2),(2,0)])['beta1'] == 1
    original = 'def add(a, b):\n    return a + b\n'
    sealed = seal_python_source(original, secret=b'omega-private-key')
    assert verify_seal(original, sealed, secret=b'omega-private-key')
    assert not verify_seal(original.replace('+', '-'), sealed, secret=b'omega-private-key')


def test_windowed_reader_and_atomic_copy(tmp_path):
    source = tmp_path/'source.bin'
    source.write_bytes(bytes(range(256))*40)
    with WindowedReader(source, window_size=4096) as reader:
        assert reader.read_at(4090, 20) == source.read_bytes()[4090:4110]
        digest = reader.digest()
    target = tmp_path/'copy.bin'
    result = copy_file(source, target, chunk_size=4096)
    assert result['sha256'] == digest
    assert target.read_bytes() == source.read_bytes()
    with pytest.raises(ValueError):
        copy_file(source, source)
