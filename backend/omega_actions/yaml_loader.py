"""Safe GitHub-compatible YAML 1.2-ish loader with bounded input and duplicate rejection."""
import re
import yaml

class WorkflowLoader(yaml.SafeLoader):
    pass

WorkflowLoader.yaml_implicit_resolvers = {
    k: [(tag, pattern) for tag, pattern in values if tag != 'tag:yaml.org,2002:bool']
    for k, values in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
WorkflowLoader.add_implicit_resolver('tag:yaml.org,2002:bool', re.compile(r'^(?:true|false|True|False|TRUE|FALSE)$'), list('tTfF'))

def unique_mapping(loader, node):
    result = {}
    for key_node, val_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, (str, int, float, bool)):
            raise ValueError('Unsupported YAML mapping key')
        if key in result:
            raise ValueError(f'Duplicate YAML key: {key}')
        result[key] = loader.construct_object(val_node, deep=True)
    return result

WorkflowLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)

def load_yaml(source: str) -> dict:
    if len(source.encode('utf-8')) > 1024*1024:
        raise ValueError('Workflow exceeds 1 MiB')
    try: result = yaml.load(source, Loader=WorkflowLoader)
    except yaml.YAMLError as exc: raise ValueError(f'Invalid workflow YAML: {exc}') from exc
    if not isinstance(result, dict):
        raise ValueError('Workflow must be a YAML mapping')
    if len(str(result)) > 4*1024*1024:
        raise ValueError('Expanded workflow too large')
    return result
