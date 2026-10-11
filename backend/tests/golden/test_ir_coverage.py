"""★ ALTIN TESTLER — IR kapsami.

Kayipsizlik yalnizca metin duzeyinde degil, ANLAM duzeyinde de gecerli olmali:
referans depodaki hicbir gorev, rol cagrisi veya oynatma IR'a cevrilirken
kaybolmamali veya sessizce ``RAW`` olmamalidir.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from app.ansible.ir import DocumentKind, NodeType, build_ir, classify_document
from app.ansible.roundtrip import parse_document

from tests.golden.conftest import (
    iter_reference_yaml_files,
    reference_id,
    requires_reference_repo,
)

pytestmark = pytest.mark.golden

_REFERENCE_FILES = iter_reference_yaml_files()

# Referans depodaki gercek dagilim (2026-09-30 olcumu).
# Bu sayilar degisirse ya depo degismistir ya da ayristirici bozulmustur;
# her iki durumda da bilincli bir guncelleme gerekir.
EXPECTED_KINDS = {
    DocumentKind.PLAYBOOK: 268,
    DocumentKind.TASK_LIST: 177,
    DocumentKind.PIPELINE: 13,
    DocumentKind.UNPARSED: 3,
}

# Referans depoda tanimlanamayan bilinen dugumler.
# Bu iki girdi ``roles:`` listesine yanlislikla GOREV olarak yazilmis;
# gecerli Ansible degildir. Platform bunlari bozmadan korur ve isaretler.
# Bkz. docs/13-roadmap-wbs.md "Not Dusulenler".
KNOWN_RAW_NODES = [
    "playbooks/altortam/update_netcore_boa/install_boa_webapi.yml#/0/roles/3",
    "playbooks/altortam/update_netcore_boa/install_boa_webapi.yml#/0/roles/4",
]


def _read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


@requires_reference_repo
def test_document_kinds_match_expected_distribution() -> None:
    """Belge turu dagilimi beklenen degerlerle ortusmelidir."""
    kinds: Counter[DocumentKind] = Counter()
    for path in _REFERENCE_FILES:
        kinds[classify_document(parse_document(_read(path)))] += 1

    for kind, expected in EXPECTED_KINDS.items():
        assert kinds[kind] == expected, f"{kind}: beklenen {expected}, bulunan {kinds[kind]}"


@requires_reference_repo
def test_pipeline_files_are_not_editable() -> None:
    """Azure Pipelines dosyalari gorsel duzenleyicide acilmamalidir."""
    from tests.golden.conftest import REFERENCE_REPO

    assert REFERENCE_REPO is not None
    pipelines = [p for p in _REFERENCE_FILES if "azure-pipelines" in p.parts]
    assert pipelines, "azure-pipelines dosyalari bulunamadi"

    for path in pipelines:
        ir = build_ir(parse_document(_read(path)))
        relative = path.relative_to(REFERENCE_REPO).as_posix()
        assert not ir.is_editable, f"{relative} duzenlenebilir isaretlendi"
        assert ir.nodes == [], f"{relative} icin dugum uretilmemeliydi"


@requires_reference_repo
@pytest.mark.parametrize("yaml_path", _REFERENCE_FILES, ids=reference_id)
def test_every_entry_becomes_exactly_one_node(yaml_path: Path) -> None:
    """Koktaki her girdi tam olarak bir ust duzey dugume karsilik gelmelidir."""
    document = parse_document(_read(yaml_path))
    ir = build_ir(document)

    if not ir.is_editable:
        return

    assert isinstance(document.data, list)
    assert len(ir.nodes) == len(document.data)


@requires_reference_repo
@pytest.mark.parametrize("yaml_path", _REFERENCE_FILES, ids=reference_id)
def test_every_node_has_a_source_span(yaml_path: Path) -> None:
    """Her dugum kaynak metinde gercek bir araliga isaret etmelidir.

    Araligi olmayan bir dugum duzenlenemez; sessizce kaybolmasindansa
    burada yakalanmalidir.
    """
    document = parse_document(_read(yaml_path))
    ir = build_ir(document)

    if not ir.is_editable:
        return

    for node in ir.walk():
        assert node.span.kind != "missing", f"{node.pointer} icin aralik bulunamadi"
        assert node.span.end > node.span.start, f"{node.pointer} bos aralik"
        assert node.pointer in document.spans


@requires_reference_repo
@pytest.mark.parametrize("yaml_path", _REFERENCE_FILES, ids=reference_id)
def test_param_pointers_resolve_to_spans(yaml_path: Path) -> None:
    """Her parametre, kaynak metinde adreslenebilir olmalidir."""
    document = parse_document(_read(yaml_path))
    ir = build_ir(document)

    if not ir.is_editable:
        return

    for node in ir.walk():
        for ref in node.params.values():
            assert ref.pointer in document.spans, (
                f"{node.pointer} parametresi {ref.name} adreslenemiyor ({ref.pointer})"
            )


@requires_reference_repo
def test_only_known_raw_nodes_exist() -> None:
    """``RAW`` dugumler yalnizca bilinen ve gerekcelendirilmis yerlerde olmalidir.

    Olcum sonucu referans depoda tanimlanamayan tek desen, ``roles:`` listesine
    yanlislikla yazilmis iki gorevdir. Bu gecerli Ansible degildir ve
    calistirildiginda hata verir; platform bunu bozmadan korur ve isaretler.

    Yeni bir ``RAW`` dugum cikiyorsa ya depoya yeni bir desen girmistir ya da
    ayristirici gerilemistir; ikisi de incelenmelidir.
    """
    from tests.golden.conftest import REFERENCE_REPO

    assert REFERENCE_REPO is not None
    found: list[str] = []

    for path in _REFERENCE_FILES:
        ir = build_ir(parse_document(_read(path)))
        if not ir.is_editable:
            continue
        relative = path.relative_to(REFERENCE_REPO).as_posix()
        found.extend(
            f"{relative}#{node.pointer}" for node in ir.walk() if node.type is NodeType.RAW
        )

    assert sorted(found) == sorted(KNOWN_RAW_NODES), (
        "Beklenmeyen tanimlanamayan dugumler: "
        + "; ".join(sorted(set(found) - set(KNOWN_RAW_NODES))[:10])
    )


@requires_reference_repo
def test_known_raw_nodes_explain_themselves() -> None:
    """Her ``RAW`` dugum kullaniciya neden kilitli oldugunu soylemelidir."""
    from tests.golden.conftest import REFERENCE_REPO

    assert REFERENCE_REPO is not None
    path = REFERENCE_REPO / "playbooks/altortam/update_netcore_boa/install_boa_webapi.yml"
    ir = build_ir(parse_document(_read(path)))

    raw_nodes = [node for node in ir.walk() if node.type is NodeType.RAW]
    assert len(raw_nodes) == 2

    for node in raw_nodes:
        assert node.is_locked
        assert "gorev gibi gorunuyor" in node.lock_reason
        assert "uri" in node.lock_reason


@requires_reference_repo
def test_role_calls_are_fully_recognized() -> None:
    """Tum rol cagrilari ROLE dugumu olmali ve rol adi cozumlenmelidir.

    Olculen dagilim: ``roles:`` girdisi 809, ``include_role`` 460.
    """
    role_nodes = 0
    without_name = 0

    for path in _REFERENCE_FILES:
        ir = build_ir(parse_document(_read(path)))
        for node in ir.walk():
            if node.type is NodeType.ROLE:
                role_nodes += 1
                if not node.role_name:
                    without_name += 1

    assert without_name == 0, f"{without_name} rol cagrisinda rol adi cozumlenemedi"
    assert role_nodes == 809 + 460


@requires_reference_repo
def test_include_tasks_targets_are_resolved() -> None:
    """Tum ``include_tasks`` cagrilarinda hedef dosya cozumlenmelidir."""
    total = 0
    for path in _REFERENCE_FILES:
        ir = build_ir(parse_document(_read(path)))
        for node in ir.walk():
            if node.type is NodeType.TASK_INCLUDE:
                total += 1
                assert node.include_target, f"{node.pointer} hedefi bos"

    assert total == 111


@requires_reference_repo
def test_locked_params_are_rare_and_justified() -> None:
    """Kilitli parametreler az olmali ve her birinin gerekcesi bulunmalidir.

    Olcum: depoda Jinja ifadesi (``{%``) 9, cok satirli deger 59 kez geciyor.
    Bunlarin disinda bir sey kilitlenmemelidir.
    """
    locked = 0
    for path in _REFERENCE_FILES:
        ir = build_ir(parse_document(_read(path)))
        for node in ir.walk():
            for ref in node.params.values():
                if ref.is_locked:
                    locked += 1
                    assert ref.lock_reason, f"{ref.pointer} gerekcesiz kilitli"

    total_params = sum(
        len(node.params)
        for path in _REFERENCE_FILES
        for node in build_ir(parse_document(_read(path))).walk()
    )
    assert total_params > 0
    ratio = locked / total_params
    assert ratio < 0.10, f"Parametrelerin %{ratio:.1%}'i kilitli — cok yuksek"


@requires_reference_repo
def test_registers_are_captured() -> None:
    """``register`` ile tanimlanan degiskenler dugumde tasinmalidir.

    Bagimlilik grafi (WP-14) bu bilgiye dayanir.
    """
    registers = [
        node.register
        for path in _REFERENCE_FILES
        for node in build_ir(parse_document(_read(path))).walk()
        if node.register
    ]
    assert len(registers) == 30
    assert "_root_ca_cert" in registers
