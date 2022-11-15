from typing import Any, Generator, Optional

from napari.layers import Layer
from napari.utils.events import Event
from pydantic import Field

from .utils.parent_aware import (
    NestedParentAwareEventedModel,
    NestedParentAwareEventedModelList,
    ParentAwareEventedDict,
    ParentAwareEventedModel,
)


# do not inherit from napari.utils.tree to avoid conflicts with pydantic-based models
class Group(NestedParentAwareEventedModel["Group"]):
    class ArrayList(NestedParentAwareEventedModelList["Group", "Array"]):
        def __init__(self) -> None:
            super().__init__(basetype=Array, lookup={str: lambda array: array.name})

    class GroupList(NestedParentAwareEventedModelList["Group", "Group"]):
        def __init__(self) -> None:
            super().__init__(basetype=Group, lookup={str: lambda group: group.name})

    name: str
    arrays: ArrayList = Field(default_factory=ArrayList, allow_mutation=False)
    children: GroupList = Field(default_factory=GroupList, allow_mutation=False)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.arrays.set_parent(self)
        self.children.set_parent(self)
        self.events.add(loaded=Event, visible=Event)

    @staticmethod
    def from_group(group: "Group") -> "Group":
        new_group = Group(name=group.name)
        new_group.arrays.extend(Array.from_array(array) for array in group.arrays)
        new_group.children.extend(Group.from_group(child) for child in group.children)
        return new_group

    def show(self) -> None:
        for array in self.iter_arrays(recursive=True):
            if array.loaded:
                array.show()

    def hide(self) -> None:
        for array in self.iter_arrays(recursive=True):
            if array.loaded:
                array.hide()

    def iter_arrays(self, recursive: bool = False) -> Generator["Array", None, None]:
        yield from self.arrays
        if recursive:
            for child in self.children:
                yield from child.iter_arrays(recursive=recursive)

    def iter_children(self, recursive: bool = False) -> Generator["Group", None, None]:
        yield from self.children
        if recursive:
            for child in self.children:
                yield from child.iter_children(recursive=recursive)

    def __hash__(self) -> int:
        return id(self)

    def __repr__(self) -> str:
        return self.name

    def _emit_loaded_event(self, source_array_event: Event) -> None:
        self.events.loaded(value=self.loaded, source_array_event=source_array_event)
        if self.parent is not None:
            self.parent._emit_loaded_event(source_array_event)

    def _emit_visible_event(self, source_array_event: Event) -> None:
        self.events.visible(value=self.visible, source_array_event=source_array_event)
        if self.parent is not None:
            self.parent._emit_visible_event(source_array_event)

    @property
    def loaded(self) -> Optional[bool]:
        n = 0
        n_loaded = 0
        for array in self.iter_arrays(recursive=True):
            n += 1
            if array.loaded:
                n_loaded += 1
        if n_loaded == 0:
            return False
        if n_loaded == n:
            return True
        return None

    @property
    def visible(self) -> Optional[bool]:
        n_loaded = 0
        n_visible = 0
        for array in self.iter_arrays(recursive=True):
            if array.loaded:
                n_loaded += 1
            if array.visible:
                n_visible += 1
        if n_visible == 0:
            return False
        if n_visible == n_loaded:
            return True
        return None


class Array(ParentAwareEventedModel[Group]):
    # avoid parameterized generics in type annotations for pydantic
    class ArrayGroupingGroupsDict(ParentAwareEventedDict["Array", str, str]):
        def __init__(self) -> None:
            super().__init__(basetype=str)

    name: str
    layer: Optional[Layer] = None
    loaded_layer: Optional[Layer] = Field(default=None, allow_mutation=False)
    array_grouping_groups: ArrayGroupingGroupsDict = Field(
        default_factory=ArrayGroupingGroupsDict, allow_mutation=False
    )

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.array_grouping_groups.set_parent(self)
        self.events.add(loaded=Event, visible=Event)
        self.events.name.connect(self._on_name_event)
        self.events.layer.connect(self._on_layer_event)
        self.events.loaded.connect(self._on_loaded_event)
        self.events.visible.connect(self._on_visible_event)

    @staticmethod
    def from_array(array: "Array") -> "Array":
        new_array = Array(
            name=array.name, layer=array.layer, loaded_layer=array.loaded_layer
        )
        new_array.array_grouping_groups.update(array.array_grouping_groups)
        return new_array

    def show(self) -> None:
        assert self.layer is not None
        self.layer.visible = True

    def hide(self) -> None:
        assert self.layer is not None
        self.layer.visible = False

    def __hash__(self) -> int:
        return id(self)

    def __repr__(self) -> str:
        return self.name

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "layer" and self.layer is not None:
            self.layer.events.name.disconnect(self._on_layer_name_event)
            self.layer.events.visible.disconnect(self._on_layer_visible_event)
        super().__setattr__(name, value)
        if name == "layer" and self.layer is not None:
            self.layer.events.name.connect(self._on_layer_name_event)
            self.layer.events.visible.connect(self._on_layer_visible_event)

    def _on_name_event(self, event: Event) -> None:
        if self.layer is not None:
            self.layer.name = self.name

    def _on_layer_event(self, event: Event) -> None:
        if self.layer is not None:
            self.name = self.layer.name
        self._emit_loaded_event(event)
        self._emit_visible_event(event)

    def _on_layer_name_event(self, event: Event) -> None:
        assert self.layer is not None
        self.name = self.layer.name

    def _on_layer_visible_event(self, event: Event) -> None:
        assert self.layer is not None
        self._emit_visible_event(event)

    def _on_loaded_event(self, event: Event) -> None:
        if self.parent is not None:
            self.parent._emit_loaded_event(event)

    def _on_visible_event(self, event: Event) -> None:
        if self.parent is not None:
            self.parent._emit_visible_event(event)

    def _emit_loaded_event(self, source_event: Event) -> None:
        self.events.loaded(value=self.loaded, source_event=source_event)

    def _emit_visible_event(self, source_event: Event) -> None:
        self.events.visible(value=self.visible, source_event=source_event)

    @property
    def loaded(self) -> bool:
        return self.layer is not None

    @property
    def visible(self) -> bool:
        return self.layer is not None and self.layer.visible
