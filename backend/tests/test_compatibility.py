from omega_actions.compatibility import inspect_workflow

def test_detects_real_host_requirements_and_unsupported_actions():
    src={'name':'Digital-Life-like','jobs':{'python':{'runs-on':'ubuntu-latest','services':{'postgres':{'image':'postgres:16'}},
       'steps':[{'uses':'actions/setup-python@v5','with':{'python-version':'3.12'}},
                {'run':'python -m pip install -e .'},
                {'uses':'docker/build-push-action@v6'}]}}}
    result=inspect_workflow(src)
    assert result['job_count']==1
    assert 'docker/build-push-action@v6' in result['unsupported_actions']
    assert '3.12' in result['python_versions']
    assert result['requires_network']
    assert result['requires_containers']
    assert result['fully_offline_verified'] is False
