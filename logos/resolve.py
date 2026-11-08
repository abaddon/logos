"""Name resolution: one module per file, its imports and its definitions.

The resolver runs after parsing and before the checker. It turns a parsed file
into a ``Module``: the module's own types, functions and tests keyed by name,
plus the modules it imports. Loading an import is a graph walk, so a cycle is
reported with the whole chain, and each module is loaded at most once per
``resolve`` call. An import is never transitive: a module sees the definitions
of the modules it names, not the ones they name.

Module vocabulary
-----------------
Only module-level forms are resolved here: ``mod``, ``use``, ``fn``, ``test``,
``type``, ``extern`` and the ``expect-error`` directive. Forms inside a ``fn``
or a ``test`` belong to the checker, so the resolver leaves them alone; the
module-level vocabulary grows with the language, one task at a time. A form
outside that vocabulary is E0002, reported at the form's path.

Names
-----
A module's name comes from its ``mod`` form, which must exist, carry a name,
and appear once. ``fn`` and ``type`` share one namespace, because both insert
their bare name into a path: ``math/add`` is one address, whether it holds a
function or a type. ``test`` has its own namespace, because a test inserts
``test/<name>``: ``(fn add ...)`` and ``(test add ...)`` coexist. An imported
definition is visible unqualified, so repeating its name locally, or importing
two definitions of one name, is E0003. The diagnostic points at the form that
introduced the second copy: the later definition, or the ``use`` that imported
it.

Errors
------
E0002 unknown node, E0003 duplicate definition, E0004 circular import,
E0005 name not found. The last covers a module the loader cannot supply and a
loaded module that declares a different name; the other codes the compiler
uses live in :mod:`logos.diag`.

Build set
---------
``program`` resolves several files as one build: the modules named on the
command line answer each other's ``use`` before the file system is asked, and
a name in no set falls back to a ``<name>.logos`` beside the file that asked.
Two roots that declare one module name are E0003 at the second, because one
name cannot be two files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from logos.diag import CIRCULAR, DUPLICATE, NOT_FOUND, UNKNOWN_NODE, LogosError, diag
from logos.lexer import ATOM, Token
from logos.nodes import Node
from logos.parser import parse

#: ``loader(name, asker)`` returns the parsed tree of another module.
#:
#: ``asker`` is the path of the file that wrote the ``use``, so a loader can
#: answer from that file's own directory rather than from the build's roots;
#: it is ``""`` when the tree that asked has no source path.
Loader = Callable[[str, str], Node]


@dataclass(slots=True)
class Module:
    """One resolved module.

    ``types``, ``fns`` and ``tests`` hold this module's own definitions, keyed
    by name; ``imports`` holds the modules ``use`` named, keyed by module name.
    Imported definitions are therefore not copied into ``fns``: a consumer
    that needs a name searches this module, then ``imports``.

    ``externs`` holds the C declarations ``(extern fn ...)`` wrote, keyed by
    name. They share the ``fn``/``type`` namespace — one linker symbol, one
    spelling — but they are not bodies: nothing lowers them, so they are kept
    apart from ``fns`` and the backend emits a ``declare`` instead of a
    ``define``.
    """

    name: str
    root: Node
    types: dict[str, Node]
    fns: dict[str, Node]
    tests: dict[str, Node]
    imports: dict[str, "Module"] = field(default_factory=dict)
    externs: dict[str, Node] = field(default_factory=dict)


def resolve(root: Node, loader: Loader, file: str = "") -> Module:
    """Resolve ``root`` and everything it imports.

    ``loader`` supplies the parsed tree of another module, given the module
    name and the path of the file that asked for it, and is called at most
    once per module name. A name it cannot supply raises E0005; a parse
    diagnostic raised by it propagates unchanged.

    The loader owns the file-name-equals-module-name rule: it decides which
    file answers a name, and may reject a name it cannot map to a file. The
    resolver checks the contract it is handed instead, that the tree the loader
    returns declares the name ``(use ...)`` asked for, and raises E0005 when it
    does not.

    ``file`` names the source ``root`` was parsed from, when the caller knows
    it. It is used only to locate a file that has no ``(mod ...)`` form at all,
    so that diagnostic carries ``file:line:column`` instead of no location.
    """
    return _Resolver(loader, file).module(root, None, "")


def program(roots: list[Node]) -> list[Module]:
    """Resolve several parsed files as one build set, in the order given.

    The set answers every ``use`` before the file system does: a module named
    on the command line is loaded from its root, not from a sibling file. A
    name in no set is looked for as ``<name>.logos`` beside the file that
    asked for it, which is the single-file rule; a name nobody can supply is
    E0005 at the ``use``. Because the loader is told which file asked, one
    root's directory never answers another root's import.

    Two roots that declare one module name are E0003 at the second, naming
    both files: one name cannot answer for two trees.
    """
    table: dict[str, Node] = {}
    origins: dict[str, str] = {}
    for root in roots:
        form = _module_form(root)
        if form is None:
            # ``resolve`` reports the missing ``(mod ...)`` below.
            continue
        name = form.name
        if name is None:
            # ``resolve`` reports the nameless ``(mod ...)`` below.
            continue
        first = table.get(name)
        if first is not None:
            raise diag(
                DUPLICATE,
                form.path,
                f"duplicate module '{name}': {_origin(first, origins[name])} "
                f"and {_origin(root, root.file)}",
            )
        table[name] = root
        origins[name] = root.file

    loader = _set_loader(table)
    #: The file that answered each module name anywhere in this build. One
    #: registry for every root, so a name answered by two files is refused
    #: whichever root was listed first.
    files: dict[str, str] = {}
    return [
        _Resolver(loader, root.file, files).module(root, None, "")
        for root in roots
    ]


def reachable(modules: list[Module]) -> list[Module]:
    """Every module ``modules`` and their imports reach, each once, stable order.

    The result starts with the roots in the order given, then each root's
    imports depth first in source order. One name is one module, so a diamond
    — two modules importing the same third — is one entry here: a build set
    lowers its functions once, and a second copy would be a second definition
    of the same symbol.

    This is the import closure a build set is lowered from. It lives here
    because it is a fact about the resolved graph, not about the driver, and
    a later build path reuses it unchanged.
    """
    seen: dict[str, Module] = {}
    order: list[Module] = []

    def walk(current: Module) -> None:
        if current.name in seen:
            return
        seen[current.name] = current
        order.append(current)
        for imported in current.imports.values():
            walk(imported)

    for module in modules:
        walk(module)
    return order


def _set_loader(table: dict[str, Node]) -> Loader:
    """A loader that answers from ``table``, then from the asker's directory.

    A sibling file is parsed at most once: a diamond import asks for one name
    twice, and both answers have to be the same tree, so the module graph holds
    one node for one file.
    """

    trees: dict[str, Node] = {}

    def loader(name: str, asker: str) -> Node:
        tree = table.get(name)
        if tree is not None:
            return tree
        if not asker:
            raise FileNotFoundError(name)
        sibling = Path(asker).parent / f"{name}.logos"
        key = str(sibling)
        cached = trees.get(key)
        if cached is not None:
            return cached
        if sibling.is_file():
            tree = parse(sibling.read_text(encoding="utf-8"), key)
            trees[key] = tree
            return tree
        raise FileNotFoundError(name)

    return loader


def _same_file(first: str, second: str) -> bool:
    """Whether two module origins name one file, by path rather than by name."""
    return Path(first).resolve() == Path(second).resolve()


def _origin(root: Node, file: str) -> str:
    """Name a root in a duplicate-module message: its file, or its path."""
    return file or root.path or "<unknown>"


class _Resolver:
    def __init__(
        self,
        loader: Loader,
        file: str = "",
        files: dict[str, str] | None = None,
    ) -> None:
        self.loader = loader
        self.file = file
        self.done: dict[str, Module] = {}
        self.active: list[str] = []
        #: The tree each (module name, asking directory) was answered with, so
        #: one import site is loaded once and two directories still get their
        #: own answer.
        self.asked: dict[tuple[str, str], Node] = {}
        #: The file that answered each module name so far. ``program`` shares
        #: one of these across its roots; a single load is a set of one.
        self.files: dict[str, str] = files if files is not None else {}

    def module(self, root: Node, expected: str | None, origin: str) -> Module:
        """Resolve a parsed file, which must declare the expected name."""
        form = _module_form(root)
        if form is None:
            if expected is not None:
                raise diag(
                    UNKNOWN_NODE,
                    origin,
                    f"module '{expected}' has no (mod ...) form",
                )
            raise _missing_module(root, self.file)
        declared = form.name
        if declared is None:
            raise diag(UNKNOWN_NODE, form.path, "mod needs a name")
        if expected is not None and declared != expected:
            raise diag(
                NOT_FOUND,
                origin,
                f"module '{expected}' declares itself '{declared}'",
            )
        self._claim(declared, form, root.file)

        self.active.append(declared)
        try:
            module = self._build(root, form, declared)
        finally:
            self.active.pop()
        self.done[declared] = module
        return module

    def _claim(self, name: str, form: Node, file: str) -> None:
        """Record the file that answers ``name``; a second one is E0003.

        A module name is an address: ``(use util)`` has exactly one answer, and
        a build where ``util`` is two files would lower one body under the
        other file's name — silently, because both declare the same symbols.
        The comparison is on the resolved path, so one file reached twice
        through a diamond is the same module and not a duplicate.
        """
        first = self.files.get(name)
        if first is None or not first:
            self.files[name] = file
            return
        if not file or _same_file(first, file):
            return
        raise diag(
            DUPLICATE,
            form.path,
            f"duplicate module '{name}': {first} and {file}",
        )

    def _build(self, root: Node, form: Node, name: str) -> Module:
        module = Module(name, root, {}, {}, {}, {}, {})
        # ``defs`` is the module's fn/type namespace as it grows, imported
        # names included, so a later definition or import can be checked
        # against everything visible at that point.
        defs: dict[str, Node] = {}
        tests: dict[str, Node] = {}

        for item in root.items:
            if not isinstance(item, Node):
                continue
            kind = item.kind
            if kind == "mod":
                if item is not form:
                    _duplicate_module(item)
            elif kind == "use":
                self._import(module, item, defs)
            elif kind in ("fn", "type"):
                _define(module, item, kind, defs)
            elif kind == "extern":
                _define_extern(module, item, defs)
            elif kind == "test":
                _define_test(module, item, tests)
            elif kind == "expect-error":
                continue
            else:
                raise diag(UNKNOWN_NODE, item.path, f"unknown node '{kind}'")
        return module

    def _import(self, module: Module, node: Node, defs: dict[str, Node]) -> None:
        name = _module_argument(node)
        if name in module.imports:
            return
        if name in self.active:
            raise diag(CIRCULAR, node.path, "circular import: " + _cycle(self.active, name))

        # The loader is asked once per (module name, asking directory), not
        # once per name: two files in different directories may ask for one
        # name and be answered by two different files, which is exactly the
        # silent collapse ``_claim`` refuses. Reusing the first answer by name
        # would hide it.
        key = (name, str(Path(module.root.file).parent) if module.root.file else "")
        root = self.asked.get(key)
        if root is None:
            try:
                root = self.loader(name, module.root.file)
            except (KeyError, OSError):
                raise diag(NOT_FOUND, node.path, f"unknown module '{name}'") from None
            if not isinstance(root, Node):
                raise diag(NOT_FOUND, node.path, f"unknown module '{name}'")
            self.asked[key] = root
        imported = self.done.get(name)
        if imported is None or not _same_file(imported.root.file, root.file):
            imported = self.module(root, name, node.path)

        _merge(imported, defs, node.path)
        module.imports[name] = imported


def _missing_module(root: Node, file: str) -> LogosError:
    """The E0002 for a file that never declares a module.

    The root's own position is the one location that always exists, so a caller
    that names its source gets ``file:line:column``; a caller that does not gets
    the bare message, as before.
    """
    if not file:
        return diag(UNKNOWN_NODE, "", "missing (mod ...) form")
    return diag(
        UNKNOWN_NODE,
        "",
        "missing (mod ...) form",
        file=file,
        line=root.line,
        col=root.col,
    )


def _module_form(root: Node) -> Node | None:
    """The file's ``mod`` form, whether or not it carries a name."""
    for item in root.items:
        if isinstance(item, Node) and item.kind == "mod":
            return item
    return None


def _module_argument(node: Node) -> str:
    """The one module name a ``use`` form names."""
    if len(node.items) == 2:
        argument = node.items[1]
        if isinstance(argument, Token) and argument.kind == ATOM:
            return argument.value
    raise diag(UNKNOWN_NODE, node.path, "use takes one module name")


def _duplicate_module(node: Node) -> None:
    name = node.name
    if name is None:
        raise diag(UNKNOWN_NODE, node.path, "mod needs a name")
    raise diag(DUPLICATE, node.path, f"duplicate module '{name}'")


def _define(module: Module, node: Node, kind: str, defs: dict[str, Node]) -> None:
    name = node.name
    if name is None:
        raise diag(UNKNOWN_NODE, node.path, f"{kind} needs a name")
    if name in defs:
        raise diag(DUPLICATE, node.path, f"duplicate definition '{name}'")
    defs[name] = node
    table = module.types if kind == "type" else module.fns
    table[name] = node


def _define_extern(module: Module, node: Node, defs: dict[str, Node]) -> None:
    """Record one ``(extern fn name ...)`` declaration.

    Only the spine is checked here: the ``fn`` marker and a name. The return
    type and the parameters are types, and types are the checker's work — a
    malformed one there carries a location inside the declaration, which the
    resolver cannot supply. The name shares the ``fn``/``type`` namespace,
    because all three are one spelling.
    """
    name = node.name
    if name is None:
        raise diag(
            UNKNOWN_NODE,
            node.path,
            "extern needs (extern fn name :ret ((p :type) ...))",
        )
    if name in defs:
        raise diag(DUPLICATE, node.path, f"duplicate definition '{name}'")
    defs[name] = node
    module.externs[name] = node


def _define_test(module: Module, node: Node, tests: dict[str, Node]) -> None:
    name = node.name
    if name is None:
        raise diag(UNKNOWN_NODE, node.path, "test needs a name")
    if name in tests:
        raise diag(DUPLICATE, node.path, f"duplicate definition '{name}'")
    tests[name] = node
    module.tests[name] = node


def _merge(imported: Module, defs: dict[str, Node], path: str) -> None:
    """Make the imported module's definitions visible, refusing collisions."""
    for table in (imported.types, imported.fns, imported.externs):
        for name in table:
            if name in defs:
                raise diag(DUPLICATE, path, f"duplicate definition '{name}'")
            defs[name] = table[name]


def _cycle(active: list[str], name: str) -> str:
    """Spell the cycle that importing ``name`` would close."""
    return " -> ".join(active[active.index(name) :] + [name])
