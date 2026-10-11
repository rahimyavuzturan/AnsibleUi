"""Yonetici onizlemesi icin depo ozeti ve belge goruntusu.

Bu servis, ``app.ansible`` icindeki saf ayristirici ve IR katmanini gercek bir
depo uzerinde calistirip arayuzun gosterebilecegi sekilde duzlestirir.

Kapsam notu: bu modul **gecici bir onizlemedir**. Kalici API sozlesmesi
``docs/09-api-contract.md`` icinde tanimlidir ve WP-30/WP-32 ile gelecektir.
Buradaki uclar o sozlesmenin yerine gecmez.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.ansible.ir import DocumentKind, IrDocument, Node, build_ir
from app.ansible.roundtrip import parse_document
from app.core.errors import AnsibleUIError
from app.core.paths import ALLOWED_ROOTS, resolve_within_repo

_YAML_SUFFIXES = (".yml", ".yaml")


class RepoMissingError(AnsibleUIError):
    """Yapilandirilan depo yolu bulunamadi."""

    code = "repo_not_found"
    status_code = 503


class ParamView(BaseModel):
    """Arayuzde tek bir form alani."""

    name: str
    value: str
    locked: bool
    lock_reason: str = ""
    templated: bool = False


class NodeView(BaseModel):
    """Arayuzde tek bir kart."""

    id: str
    type: str
    name: str
    pointer: str
    line_start: int
    line_end: int
    role_name: str | None = None
    tasks_from: str | None = None
    include_target: str | None = None
    module: str | None = None
    register_var: str | None = None
    locked: bool = False
    lock_reason: str = ""
    params: list[ParamView] = Field(default_factory=list)
    keywords: list[ParamView] = Field(default_factory=list)
    children: list[NodeView] = Field(default_factory=list)


class DocumentView(BaseModel):
    """Bir dosyanin tam onizlemesi."""

    path: str
    kind: str
    editable: bool
    parse_error: str | None = None
    text: str
    line_count: int
    node_count: int
    nodes: list[NodeView] = Field(default_factory=list)


class DocumentEntry(BaseModel):
    """Gezginde tek bir satir."""

    path: str
    name: str
    directory: str
    kind: str
    editable: bool
    node_count: int


class RepoSummary(BaseModel):
    """Yonetici panosundaki sayilar."""

    repo_name: str
    file_count: int
    kind_counts: dict[str, int]
    node_count: int
    role_call_count: int
    distinct_role_count: int
    include_tasks_count: int
    param_count: int
    locked_param_count: int
    raw_node_count: int
    broken_files: list[str]
    top_roles: list[dict[str, Any]]
    documents: list[DocumentEntry]


# ---------------------------------------------------------------------------
# Yardimcilar
# ---------------------------------------------------------------------------


def _line_of(text: str, offset: int) -> int:
    """Karakter konumunu 1 tabanli satir numarasina cevirir."""
    return text.count("\n", 0, max(offset, 0)) + 1


def _stringify(value: Any) -> str:
    """Bir parametre degerini arayuzde gosterilecek metne cevirir."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "~"
    if isinstance(value, (list, tuple)):
        return "\n".join(f"- {_stringify(item)}" for item in value)
    if isinstance(value, dict):
        return "\n".join(f"{key}: {_stringify(item)}" for key, item in value.items())
    return str(value)


def _to_node_view(node: Node, path: str, text: str) -> NodeView:
    """IR dugumunu arayuz goruntusune cevirir."""
    return NodeView(
        id=f"{path}#{node.pointer}",
        type=str(node.type),
        name=node.name or str(node.type),
        pointer=node.pointer,
        line_start=_line_of(text, node.span.start),
        line_end=_line_of(text, max(node.span.end - 1, node.span.start)),
        role_name=node.role_name,
        tasks_from=node.tasks_from,
        include_target=node.include_target,
        module=node.module,
        register_var=node.register,
        locked=node.is_locked,
        lock_reason=node.lock_reason,
        params=[
            ParamView(
                name=ref.name,
                value=_stringify(ref.value),
                locked=ref.is_locked,
                lock_reason=ref.lock_reason,
                templated=ref.is_templated,
            )
            for ref in node.params.values()
        ],
        keywords=[
            ParamView(name=key, value=_stringify(value), locked=False)
            for key, value in node.keywords.items()
        ],
        children=[_to_node_view(child, path, text) for child in node.children],
    )


def _iter_yaml_files(repo_root: Path) -> list[Path]:
    """Duzenlemeye acik koklerdeki tum YAML dosyalarini bulur."""
    files: list[Path] = []
    for root_name in ALLOWED_ROOTS:
        root = repo_root / root_name
        if not root.is_dir():
            continue
        for suffix in _YAML_SUFFIXES:
            files.extend(root.rglob(f"*{suffix}"))
    return sorted(files)


def _read(path: Path) -> str:
    """Dosyayi satir sonlarini bozmadan okur."""
    return path.read_bytes().decode("utf-8", errors="replace")


def _relative(repo_root: Path, path: Path) -> str:
    return "/".join(path.relative_to(repo_root).parts)


# ---------------------------------------------------------------------------
# Genel API
# ---------------------------------------------------------------------------


def require_repo(repo_root: Path) -> Path:
    """Depo yolunun var oldugunu dogrular."""
    if not repo_root.is_dir():
        raise RepoMissingError(
            "Ansible deposu bulunamadi. ANSIBLEUI_REPO_PATH ayarini kontrol edin.",
            details={"path": str(repo_root)},
        )
    return repo_root


@lru_cache(maxsize=4)
def scan_repository(repo_root: Path) -> RepoSummary:
    """Depoyu bastan sona ayristirip ozet cikarir.

    Sonuc onbelleklenir; demo sirasinda her istekte 477 dosya yeniden
    ayristirilmaz.
    """
    require_repo(repo_root)

    kinds: Counter[str] = Counter()
    roles: Counter[str] = Counter()
    documents: list[DocumentEntry] = []
    broken: list[str] = []

    node_count = 0
    role_calls = 0
    include_tasks = 0
    param_count = 0
    locked_params = 0
    raw_nodes = 0

    for path in _iter_yaml_files(repo_root):
        rel = _relative(repo_root, path)
        document = parse_document(_read(path))
        ir = build_ir(document)

        kinds[str(ir.kind)] += 1
        if ir.kind is DocumentKind.UNPARSED:
            broken.append(rel)

        local_nodes = 0
        for node in ir.walk():
            local_nodes += 1
            node_count += 1
            param_count += len(node.params)
            locked_params += len(node.locked_params)
            if node.role_name:
                role_calls += 1
                roles[node.role_name] += 1
            if node.include_target:
                include_tasks += 1
            if str(node.type) == "raw":
                raw_nodes += 1

        documents.append(
            DocumentEntry(
                path=rel,
                name=path.name,
                directory=str(Path(rel).parent).replace("\\", "/"),
                kind=str(ir.kind),
                editable=ir.is_editable,
                node_count=local_nodes,
            )
        )

    return RepoSummary(
        repo_name=repo_root.name,
        file_count=len(documents),
        kind_counts=dict(kinds),
        node_count=node_count,
        role_call_count=role_calls,
        distinct_role_count=len(roles),
        include_tasks_count=include_tasks,
        param_count=param_count,
        locked_param_count=locked_params,
        raw_node_count=raw_nodes,
        broken_files=broken,
        top_roles=[{"name": name, "count": count} for name, count in roles.most_common(12)],
        documents=documents,
    )


def build_document_view(repo_root: Path, raw_path: str) -> DocumentView:
    """Tek bir dosyanin IR goruntusunu uretir.

    ``raw_path`` kullanicidan gelir; ``resolve_within_repo`` ile dogrulanir
    (path traversal korumasi, OWASP A01).
    """
    require_repo(repo_root)
    absolute = resolve_within_repo(repo_root, raw_path)

    if not absolute.is_file():
        raise RepoMissingError("Dosya bulunamadi", details={"path": raw_path})

    text = _read(absolute)
    document = parse_document(text)
    ir: IrDocument = build_ir(document)
    rel = _relative(repo_root, absolute)

    return DocumentView(
        path=rel,
        kind=str(ir.kind),
        editable=ir.is_editable,
        parse_error=ir.parse_error,
        text=text,
        line_count=text.count("\n") + 1,
        node_count=sum(1 for _ in ir.walk()),
        nodes=[_to_node_view(node, rel, text) for node in ir.nodes],
    )
