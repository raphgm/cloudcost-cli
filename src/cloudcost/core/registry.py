from typing import Protocol, Dict, Type, Any
import pyarrow as pa

class SourcePlugin(Protocol):
    def extract(self, context: Any) -> pa.Table:
        ...

class TransformPlugin(Protocol):
    def transform(self, table: pa.Table, context: Any) -> pa.Table:
        ...

class DestinationPlugin(Protocol):
    def load(self, table: pa.Table, target: Any, context: Any) -> None:
        ...

class PluginRegistry:
    def __init__(self):
        self.sources: Dict[str, Type[SourcePlugin]] = {}
        self.transforms: Dict[str, Type[TransformPlugin]] = {}
        self.destinations: Dict[str, Type[DestinationPlugin]] = {}

    def register_source(self, name: str):
        def decorator(cls: Type[SourcePlugin]):
            self.sources[name] = cls
            return cls
        return decorator

    def register_transform(self, name: str):
        def decorator(cls: Type[TransformPlugin]):
            self.transforms[name] = cls
            return cls
        return decorator

    def register_destination(self, name: str):
        def decorator(cls: Type[DestinationPlugin]):
            self.destinations[name] = cls
            return cls
        return decorator

    def get_source(self, name: str) -> Type[SourcePlugin]:
        if name not in self.sources:
            raise ValueError(f"Source plugin '{name}' not found")
        return self.sources[name]

    def get_transform(self, name: str) -> Type[TransformPlugin]:
        if name not in self.transforms:
            raise ValueError(f"Transform plugin '{name}' not found")
        return self.transforms[name]

    def get_destination(self, name: str) -> Type[DestinationPlugin]:
        if name not in self.destinations:
            raise ValueError(f"Destination plugin '{name}' not found")
        return self.destinations[name]

registry = PluginRegistry()
