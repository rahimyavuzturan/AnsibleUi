"""Ansible belgelerinin ara temsili (IR).

Bu modul, ``roundtrip`` tarafindan cikarilan dugum agacini arayuzun
anlayabilecegi tipli bir goruntuye cevirir.

Temel ilkeler:

* IR bir **goruntudur**, gercegin kaynagi degil. Yazma islemi her zaman
  ``TextEdit`` ile orijinal metne uygulanir (bkz. ADR-0007).
* **Anlamadigini bozma.** Bir yapi tanimlanamiyorsa ``RAW`` olur ve aynen korunur.
* **Kismi kilitleme tercih edilir.** Bir gorevin tek bir parametresi forma
  uygun degilse yalnizca o parametre kilitlenir; gorev yine de tipli kalir.

Tasarim, referans deponun tamamina karsi olculen gercek dagilima dayanir:
``roles:`` girdisi 809, ``include_role`` 460, ``include_tasks`` 111,
``block`` 0, Jinja ifadesi (``{%``) 9 kez gecer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from app.ansible.roundtrip import NodeSpan, YamlDocument, escape_pointer_token

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = [
    "DocumentKind",
    "IrDocument",
    "Node",
    "NodeType",
    "ParamRef",
    "build_ir",
    "classify_document",
    "node_id",
]


# ---------------------------------------------------------------------------
# Siniflandirma
# ---------------------------------------------------------------------------


class DocumentKind(StrEnum):
    """Bir YAML dosyasinin ne oldugunu belirtir.

    Depoda yalnizca Ansible dosyalari yok: Azure Pipelines tanimlari,
    filebeat yapilandirmalari ve ``group_vars`` dosyalari da ayni uzantiyi
    kullanir. Bunlari ayirt etmeden duzenlemeye acmak yanlis olur.
    """

    PLAYBOOK = "playbook"
    """Oynatma listesi: kok bir dizi ve girdilerinde ``hosts`` var."""

    TASK_LIST = "task_list"
    """Gorev listesi: kok bir dizi, ``hosts`` yok. Rol gorev dosyalari."""

    PIPELINE = "pipeline"
    """Azure Pipelines tanimi. Ansible degil, salt-okunur."""

    VARS = "vars"
    """Degisken dosyasi (``group_vars`` vb.)."""

    CONFIG = "config"
    """Ansible ile ilgisi olmayan yapilandirma (filebeat gibi)."""

    EMPTY = "empty"
    """Bos veya yalnizca yorum iceren dosya."""

    UNPARSED = "unparsed"
    """Ayristirilamadi. Salt-okunur gosterilir."""


class NodeType(StrEnum):
    """IR dugum tipleri."""

    PLAY = "play"
    ROLE = "role"
    TASK_INCLUDE = "task_include"
    MODULE = "module"
    BLOCK = "block"
    RAW = "raw"


# Bir oynatmada gorev iceren bolumler.
_TASK_SECTIONS = ("pre_tasks", "tasks", "post_tasks", "handlers")

# Gorev seviyesinde modul OLMAYAN anahtarlar.
_TASK_KEYWORDS = frozenset(
    {
        "name",
        "when",
        "register",
        "vars",
        "tags",
        "become",
        "become_method",
        "become_user",
        "become_flags",
        "delegate_to",
        "delegate_facts",
        "ignore_errors",
        "ignore_unreachable",
        "failed_when",
        "changed_when",
        "notify",
        "listen",
        "until",
        "retries",
        "delay",
        "run_once",
        "no_log",
        "check_mode",
        "diff",
        "environment",
        "connection",
        "remote_user",
        "any_errors_fatal",
        "throttle",
        "timeout",
        "poll",
        "async",
        "args",
        "loop",
        "loop_control",
        "module_defaults",
        "collections",
        "debugger",
        "with_items",
        "with_dict",
        "with_nested",
        "with_fileglob",
        "with_together",
        "with_subelements",
        "with_sequence",
        "with_list",
        "with_first_found",
        "with_lines",
        "with_flattened",
        "with_indexed_items",
    }
)

# ``roles:`` girdisinde parametre SAYILMAYAN anahtarlar.
_ROLE_ENTRY_KEYWORDS = frozenset(
    {
        "role",
        "name",
        "when",
        "tags",
        "vars",
        "become",
        "become_user",
        "become_method",
        "delegate_to",
        "ignore_errors",
    }
)

_INCLUDE_ROLE_KEYS = ("include_role", "import_role")
_INCLUDE_TASKS_KEYS = ("include_tasks", "import_tasks")
_BLOCK_KEYS = ("block", "rescue", "always")

_PIPELINE_MARKERS = frozenset({"trigger", "steps", "stages", "jobs", "pool", "parameters"})
_VARS_MARKERS = frozenset({"ansible_user", "ansible_connection", "ansible_port"})


def classify_document(document: YamlDocument) -> DocumentKind:
    """Bir belgenin turunu icerigine bakarak belirler.

    Uzantiya veya klasore degil, yapiya bakar; ayni klasorde farkli turler
    bulunabilir.
    """
    if not document.is_parsed:
        return DocumentKind.UNPARSED

    data = document.data
    if data is None:
        return DocumentKind.EMPTY

    if isinstance(data, list):
        if any(isinstance(entry, dict) and "hosts" in entry for entry in data):
            return DocumentKind.PLAYBOOK
        return DocumentKind.TASK_LIST

    if isinstance(data, dict):
        keys = set(data.keys())
        if keys & _PIPELINE_MARKERS:
            return DocumentKind.PIPELINE
        # Ansible degisken adlari gecerli tanimlayici olmak zorundadir.
        # "filebeat.inputs" / "output.elasticsearch" gibi noktali anahtarlar
        # degisken degil, yabanci bir konfigurasyon formatidir.
        if any(not (isinstance(key, str) and key.isidentifier()) for key in keys):
            return DocumentKind.CONFIG
        if keys & _VARS_MARKERS or all(not isinstance(v, dict) for v in data.values()):
            return DocumentKind.VARS
        return DocumentKind.CONFIG

    return DocumentKind.CONFIG


# ---------------------------------------------------------------------------
# Kilitleme
# ---------------------------------------------------------------------------

_JINJA_STATEMENT = "{%"


def _lock_reason(value: Any) -> str:
    """Bir degerin neden forma uygun olmadigini aciklar; uygunsa bos dize.

    Yalnizca iki durum kilitlenir:

    * Jinja **ifadesi** (``{% if %}``, ``{% for %}``, ``{% filter %}``) iceren
      degerler: bunlar calisma aninda dallanir, tek bir deger olarak duzenlenemez.
    * Cok satirli degerler (gomulu PowerShell gibi): metin editorunde duzenlenir.

    Basit degisken ikamesi (``{{ item }}``) kilitlenmez; kullanici bunu metin
    olarak duzenleyebilir.
    """
    if isinstance(value, str):
        if _JINJA_STATEMENT in value:
            return "Deger Jinja kosul/dongu ifadesi iceriyor, form ile duzenlenemez"
        if "\n" in value:
            return "Deger cok satirli, metin editorunde duzenlenir"
        return ""

    if isinstance(value, dict):
        for item in value.values():
            reason = _lock_reason(item)
            if reason:
                return reason
        return ""

    if isinstance(value, list):
        for item in value:
            reason = _lock_reason(item)
            if reason:
                return reason
        return ""

    return ""


# ---------------------------------------------------------------------------
# Veri modeli
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ParamRef:
    """Duzenlenebilir tek bir parametre ve kaynak metindeki yeri."""

    name: str
    pointer: str
    value: Any
    lock_reason: str = ""

    @property
    def is_locked(self) -> bool:
        return bool(self.lock_reason)

    @property
    def is_templated(self) -> bool:
        """Deger Jinja degisken ikamesi iceriyor mu."""
        return isinstance(self.value, str) and "{{" in self.value


@dataclass(slots=True)
class Node:
    """IR dugumu: arayuzde tek bir kart veya canvas ogesi."""

    type: NodeType
    pointer: str
    span: NodeSpan
    name: str = ""
    """Gorunen ad. ``name:`` anahtari yoksa tipten turetilir."""

    role_name: str | None = None
    """``ROLE`` dugumleri icin cagrilan rolun adi."""

    tasks_from: str | None = None
    """``include_role`` icin alternatif gorev dosyasi."""

    include_target: str | None = None
    """``TASK_INCLUDE`` dugumleri icin hedef dosya."""

    module: str | None = None
    """``MODULE`` dugumleri icin modul adi."""

    params: dict[str, ParamRef] = field(default_factory=dict)
    """Duzenlenebilir parametreler."""

    keywords: dict[str, Any] = field(default_factory=dict)
    """``when``, ``loop``, ``register`` gibi Ansible anahtar kelimeleri."""

    children: list[Node] = field(default_factory=list)
    """Alt dugumler (oynatmanin gorevleri, block'un icerigi)."""

    lock_reason: str = ""
    """Dugumun tamami kilitliyse sebebi."""

    register: str | None = None
    """``register`` ile tanimlanan degisken adi. Bagimlilik grafi kullanir."""

    @property
    def is_locked(self) -> bool:
        return bool(self.lock_reason)

    @property
    def locked_params(self) -> list[str]:
        """Kilitli parametrelerin adlari."""
        return sorted(name for name, ref in self.params.items() if ref.is_locked)

    def walk(self) -> Iterator[Node]:
        """Kendisi dahil tum alt agaci dolasir."""
        yield self
        for child in self.children:
            yield from child.walk()


@dataclass(slots=True)
class IrDocument:
    """Bir dosyanin tipli goruntusu."""

    kind: DocumentKind
    nodes: list[Node] = field(default_factory=list)
    parse_error: str | None = None

    @property
    def is_editable(self) -> bool:
        """Bu belge gorsel duzenleyicide acilabilir mi."""
        return self.kind in (DocumentKind.PLAYBOOK, DocumentKind.TASK_LIST)

    def walk(self) -> Iterator[Node]:
        """Tum dugumleri, ic ice olanlar dahil dolasir."""
        for node in self.nodes:
            yield from node.walk()

    def find(self, pointer: str) -> Node | None:
        """Pointer'a karsilik gelen dugumu bulur."""
        for node in self.walk():
            if node.pointer == pointer:
                return node
        return None


def node_id(file_path: str, pointer: str) -> str:
    """Depo genelinde benzersiz dugum kimligi uretir.

    Bicim: ``playbooks/x.yml#/0/vars/paths``.
    """
    return f"{file_path}#{pointer}"


# ---------------------------------------------------------------------------
# Insa
# ---------------------------------------------------------------------------


def build_ir(document: YamlDocument) -> IrDocument:
    """Ayristirilmis bir belgeden IR uretir.

    Ayristirilamayan veya Ansible olmayan belgeler icin bos ama turu belirli
    bir ``IrDocument`` doner; cagiran taraf bunu salt-okunur gosterir.
    """
    kind = classify_document(document)
    ir = IrDocument(kind=kind, parse_error=document.parse_error)

    if kind not in (DocumentKind.PLAYBOOK, DocumentKind.TASK_LIST):
        return ir

    data = document.data
    if not isinstance(data, list):
        return ir

    for index, entry in enumerate(data):
        pointer = f"/{index}"
        ir.nodes.append(
            _build_entry(document, entry, pointer, is_play=kind is DocumentKind.PLAYBOOK)
        )

    return ir


def _span_of(document: YamlDocument, pointer: str) -> NodeSpan:
    """Pointer icin aralik dondurur; yoksa sifir uzunluklu bir aralik uretir."""
    located = document.spans.get(pointer)
    if located is not None:
        return located
    return NodeSpan(pointer=pointer, start=0, end=0, kind="missing")


def _build_entry(document: YamlDocument, entry: Any, pointer: str, *, is_play: bool) -> Node:
    """Kok seviyesindeki bir girdiyi dugume cevirir."""
    if is_play and isinstance(entry, dict) and "hosts" in entry:
        return _build_play(document, entry, pointer)
    return _build_task(document, entry, pointer)


def _build_play(document: YamlDocument, play: dict[str, Any], pointer: str) -> Node:
    """Bir oynatmayi ve icindeki gorevleri dugume cevirir."""
    node = Node(
        type=NodeType.PLAY,
        pointer=pointer,
        span=_span_of(document, pointer),
        name=str(play.get("name") or play.get("hosts") or "oynatma"),
    )

    for key in (
        "hosts",
        "vars_files",
        "vars",
        "gather_facts",
        "become",
        "become_method",
        "become_user",
        "serial",
        "any_errors_fatal",
        "collections",
        "tags",
    ):
        if key in play:
            node.keywords[key] = play[key]

    roles = play.get("roles")
    if isinstance(roles, list):
        for index, item in enumerate(roles):
            child_pointer = f"{pointer}/roles/{index}"
            node.children.append(_build_role_entry(document, item, child_pointer))

    for section in _TASK_SECTIONS:
        items = play.get(section)
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            child_pointer = f"{pointer}/{section}/{index}"
            node.children.append(_build_task(document, item, child_pointer))

    return node


def _build_role_entry(document: YamlDocument, entry: Any, pointer: str) -> Node:
    """``roles:`` listesindeki bir girdiyi dugume cevirir.

    Bu bicimde parametreler ``role:`` ile AYNI eslemenin kardesleridir::

        roles:
          - role: createCertStoreDsc
            private: false          # <- parametre
            public: true            # <- parametre
    """
    span = _span_of(document, pointer)

    if isinstance(entry, str):
        # Kisa bicim: yalnizca rol adi.
        return Node(
            type=NodeType.ROLE,
            pointer=pointer,
            span=span,
            name=entry,
            role_name=entry,
        )

    if not isinstance(entry, dict):
        return _raw_node(pointer, span, "Rol girdisi bir esleme veya metin degil")

    if "role" not in entry:
        # Depoda gercek bir ornek var: ``roles:`` listesine yanlislikla GOREV
        # yazilmis. Ansible bunu calistiramaz ("role definitions must contain
        # a role name"). Bozmadan koru ve sebebi acikca soyle.
        module_keys = [key for key in entry if key not in _ROLE_ENTRY_KEYWORDS]
        if module_keys:
            return _raw_node(
                pointer,
                span,
                "Bu girdi bir rol degil, gorev gibi gorunuyor "
                f"({', '.join(sorted(module_keys))}). Ansible 'roles:' bolumunde "
                "gorev calistiramaz.",
                name=str(entry.get("name", "")),
            )
        return _raw_node(
            pointer, span, "Rol girdisinde 'role' anahtari yok", name=str(entry.get("name", ""))
        )

    role_name = str(entry["role"])
    node = Node(
        type=NodeType.ROLE,
        pointer=pointer,
        span=span,
        name=str(entry.get("name") or role_name),
        role_name=role_name,
    )

    for key, value in entry.items():
        if key in _ROLE_ENTRY_KEYWORDS:
            if key not in ("role", "name"):
                node.keywords[key] = value
            continue
        _add_param(node, document, key, value, f"{pointer}/{escape_pointer_token(key)}")

    # Bazi girdilerde parametreler ayrica ic ice ``vars:`` altinda tutulur.
    nested = entry.get("vars")
    if isinstance(nested, dict):
        for key, value in nested.items():
            _add_param(
                node,
                document,
                key,
                value,
                f"{pointer}/vars/{escape_pointer_token(key)}",
            )

    return node


def _build_task(document: YamlDocument, task: Any, pointer: str) -> Node:
    """Tek bir gorevi dugume cevirir."""
    span = _span_of(document, pointer)

    if not isinstance(task, dict):
        return _raw_node(pointer, span, "Gorev bir esleme degil")

    if any(key in task for key in _BLOCK_KEYS):
        return _build_block(document, task, pointer, span)

    module_keys = [key for key in task if key not in _TASK_KEYWORDS]

    if len(module_keys) != 1:
        reason = (
            "Gorevde modul bulunamadi"
            if not module_keys
            else f"Gorevde birden fazla modul var: {', '.join(sorted(module_keys))}"
        )
        return _raw_node(pointer, span, reason, name=str(task.get("name", "")))

    module = module_keys[0]
    value = task[module]

    if module in _INCLUDE_ROLE_KEYS:
        return _build_include_role(document, task, module, value, pointer, span)

    if module in _INCLUDE_TASKS_KEYS:
        return _build_include_tasks(document, task, module, value, pointer, span)

    return _build_module(document, task, module, value, pointer, span)


def _build_include_role(
    document: YamlDocument,
    task: dict[str, Any],
    module: str,
    value: Any,
    pointer: str,
    span: NodeSpan,
) -> Node:
    """``include_role`` gorevini dugume cevirir.

    Bu bicimde parametreler gorevin KARDES ``vars:`` anahtarindadir::

        - name: Role in role - create_dir
          include_role:
            name: create_dir
          vars:                   # <- parametreler burada
            paths: [...]
    """
    if not isinstance(value, dict) or "name" not in value:
        return _raw_node(
            pointer, span, f"{module} beklenen bicimde degil", name=str(task.get("name", ""))
        )

    role_name = str(value["name"])
    node = Node(
        type=NodeType.ROLE,
        pointer=pointer,
        span=span,
        name=str(task.get("name") or role_name),
        role_name=role_name,
        tasks_from=str(value["tasks_from"]) if "tasks_from" in value else None,
    )

    _collect_keywords(node, task)

    params = task.get("vars")
    if isinstance(params, dict):
        for key, item in params.items():
            _add_param(
                node,
                document,
                key,
                item,
                f"{pointer}/vars/{escape_pointer_token(key)}",
            )

    return node


def _build_include_tasks(
    document: YamlDocument,
    task: dict[str, Any],
    module: str,
    value: Any,
    pointer: str,
    span: NodeSpan,
) -> Node:
    """``include_tasks`` gorevini dugume cevirir.

    Depodaki kullanimlarin tamami kisa bicimdir (``include_tasks: dosya.yml``),
    ancak tam bicim (``file:`` anahtarli esleme) de desteklenir.
    """
    if isinstance(value, str):
        target = value
    elif isinstance(value, dict) and isinstance(value.get("file"), str):
        target = str(value["file"])
    else:
        return _raw_node(
            pointer, span, f"{module} hedefi cozumlenemedi", name=str(task.get("name", ""))
        )

    node = Node(
        type=NodeType.TASK_INCLUDE,
        pointer=pointer,
        span=span,
        name=str(task.get("name") or target),
        include_target=target,
        module=module,
    )
    _collect_keywords(node, task)

    params = task.get("vars")
    if isinstance(params, dict):
        for key, item in params.items():
            _add_param(
                node,
                document,
                key,
                item,
                f"{pointer}/vars/{escape_pointer_token(key)}",
            )

    return node


def _build_module(
    document: YamlDocument,
    task: dict[str, Any],
    module: str,
    value: Any,
    pointer: str,
    span: NodeSpan,
) -> Node:
    """Sira disi olmayan bir modul gorevini dugume cevirir."""
    node = Node(
        type=NodeType.MODULE,
        pointer=pointer,
        span=span,
        name=str(task.get("name") or module),
        module=module,
    )
    _collect_keywords(node, task)

    module_pointer = f"{pointer}/{escape_pointer_token(module)}"

    if isinstance(value, dict):
        for key, item in value.items():
            _add_param(
                node,
                document,
                key,
                item,
                f"{module_pointer}/{escape_pointer_token(key)}",
            )
    else:
        # Kisa bicim: ``win_shell: | ...`` veya ``debug: msg``.
        _add_param(node, document, module, value, module_pointer)

    return node


def _build_block(
    document: YamlDocument, task: dict[str, Any], pointer: str, span: NodeSpan
) -> Node:
    """``block`` / ``rescue`` / ``always`` yapisini dugume cevirir.

    Referans depoda su an kullanilmiyor, ancak eklenebilecegi icin desteklenir.
    """
    node = Node(
        type=NodeType.BLOCK,
        pointer=pointer,
        span=span,
        name=str(task.get("name") or "block"),
    )
    _collect_keywords(node, task)

    for section in _BLOCK_KEYS:
        items = task.get(section)
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            child_pointer = f"{pointer}/{section}/{index}"
            node.children.append(_build_task(document, item, child_pointer))

    return node


def _raw_node(pointer: str, span: NodeSpan, reason: str, name: str = "") -> Node:
    """Anlasilamayan bir yapi icin kilitli dugum uretir."""
    return Node(
        type=NodeType.RAW,
        pointer=pointer,
        span=span,
        name=name or "ham YAML",
        lock_reason=reason,
    )


def _collect_keywords(node: Node, task: dict[str, Any]) -> None:
    """Gorevdeki Ansible anahtar kelimelerini dugume tasir."""
    for key, value in task.items():
        if key in _TASK_KEYWORDS and key not in ("name", "vars"):
            node.keywords[key] = value
    register = task.get("register")
    if isinstance(register, str):
        node.register = register


def _add_param(node: Node, document: YamlDocument, name: str, value: Any, pointer: str) -> None:
    """Dugume tek bir parametre ekler ve gerekiyorsa kilitler."""
    if pointer not in document.spans:
        # Aralik bulunamadi: guvenli taraf kilitlemektir.
        node.params[name] = ParamRef(
            name=name,
            pointer=pointer,
            value=value,
            lock_reason="Degerin kaynak metindeki yeri belirlenemedi",
        )
        return

    node.params[name] = ParamRef(
        name=name,
        pointer=pointer,
        value=value,
        lock_reason=_lock_reason(value),
    )
