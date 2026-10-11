"""IR insa mantiginin birim testleri.

Altin testler gercek depoya bakar; buradakiler kenar durumlari ve her
node tipinin karar mantigini kapsar.
"""

from __future__ import annotations

from typing import Any

import pytest
from app.ansible.ir import (
    DocumentKind,
    NodeType,
    build_ir,
    classify_document,
    node_id,
)
from app.ansible.roundtrip import TextEdit, parse_document, render_scalar, serialize_document


def ir_of(text: str) -> Any:
    return build_ir(parse_document(text))


# ---------------------------------------------------------------------------
# Belge siniflandirmasi
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("- hosts: web\n  name: x\n", DocumentKind.PLAYBOOK),
        ("- name: gorev\n  debug:\n    msg: merhaba\n", DocumentKind.TASK_LIST),
        ("trigger: none\npool:\n  name: Ansible\nsteps: []\n", DocumentKind.PIPELINE),
        ("ansible_user: admin\nansible_connection: winrm\n", DocumentKind.VARS),
        ("filebeat.inputs:\n  - type: log\n", DocumentKind.CONFIG),
        ("# yalnizca yorum\n", DocumentKind.EMPTY),
        ("a: b: c\n", DocumentKind.UNPARSED),
    ],
)
def test_belge_turu_dogru_belirlenir(text: str, expected: DocumentKind) -> None:
    assert classify_document(parse_document(text)) == expected


def test_ansible_olmayan_belge_duzenlenemez() -> None:
    ir = ir_of("trigger: none\nsteps: []\n")
    assert not ir.is_editable
    assert ir.nodes == []


def test_bozuk_belge_hata_mesajini_tasir() -> None:
    ir = ir_of("a: b: c\n")
    assert ir.kind is DocumentKind.UNPARSED
    assert ir.parse_error is not None


# ---------------------------------------------------------------------------
# Oynatma
# ---------------------------------------------------------------------------


PLAYBOOK = """\
- name: test oynatma
  hosts: web
  vars_files:
    - /etc/ansible/vault/vault_test.yml
  roles:
    - role: create_dir
      paths:
        - 'D:\\WebSites'
    - role: pingpong
  tasks:
    - name: bilgi ver
      debug:
        msg: merhaba
"""


def test_oynatma_dugumu_uretilir() -> None:
    ir = ir_of(PLAYBOOK)
    assert len(ir.nodes) == 1

    play = ir.nodes[0]
    assert play.type is NodeType.PLAY
    assert play.name == "test oynatma"
    assert play.keywords["hosts"] == "web"
    assert play.keywords["vars_files"] == ["/etc/ansible/vault/vault_test.yml"]


def test_oynatmanin_rolleri_ve_gorevleri_cocuk_olur() -> None:
    play = ir_of(PLAYBOOK).nodes[0]
    assert len(play.children) == 3

    first, second, third = play.children
    assert (first.type, first.role_name) == (NodeType.ROLE, "create_dir")
    assert (second.type, second.role_name) == (NodeType.ROLE, "pingpong")
    assert (third.type, third.module) == (NodeType.MODULE, "debug")


def test_roles_girdisinde_parametreler_satir_icidir() -> None:
    """``- role: X`` biciminde parametreler ``role:`` ile kardestir."""
    role = ir_of(PLAYBOOK).nodes[0].children[0]
    assert set(role.params) == {"paths"}
    assert role.params["paths"].pointer == "/0/roles/0/paths"
    assert role.params["paths"].value == ["D:\\WebSites"]
    assert not role.params["paths"].is_locked


def test_parametresiz_rol_girdisi_calisir() -> None:
    role = ir_of(PLAYBOOK).nodes[0].children[1]
    assert role.params == {}
    assert role.role_name == "pingpong"


def test_duz_metin_rol_girdisi_desteklenir() -> None:
    ir = ir_of("- hosts: web\n  roles:\n    - create_dir\n")
    role = ir.nodes[0].children[0]
    assert role.type is NodeType.ROLE
    assert role.role_name == "create_dir"


# ---------------------------------------------------------------------------
# include_role
# ---------------------------------------------------------------------------


INCLUDE_ROLE = """\
- name: Role in role - create_dir
  include_role:
    name: create_dir
    tasks_from: main.yml
  when: dotnetcore is defined
  vars:
    paths:
      - 'D:\\WebSites'
    state: present
"""


def test_include_role_parametreleri_kardes_varsdan_gelir() -> None:
    """``include_role`` biciminde parametreler gorevin ``vars:`` anahtarindadir."""
    node = ir_of(INCLUDE_ROLE).nodes[0]
    assert node.type is NodeType.ROLE
    assert node.role_name == "create_dir"
    assert node.tasks_from == "main.yml"
    assert set(node.params) == {"paths", "state"}
    assert node.params["state"].pointer == "/0/vars/state"


def test_include_role_when_anahtari_korunur() -> None:
    node = ir_of(INCLUDE_ROLE).nodes[0]
    assert node.keywords["when"] == "dotnetcore is defined"


def test_bozuk_include_role_ham_dugum_olur() -> None:
    ir = ir_of("- include_role:\n    tasks_from: main.yml\n")
    node = ir.nodes[0]
    assert node.type is NodeType.RAW
    assert node.is_locked


# ---------------------------------------------------------------------------
# include_tasks
# ---------------------------------------------------------------------------


def test_include_tasks_kisa_bicim() -> None:
    node = ir_of("- include_tasks: create_dir.yml\n").nodes[0]
    assert node.type is NodeType.TASK_INCLUDE
    assert node.include_target == "create_dir.yml"


def test_include_tasks_tam_bicim() -> None:
    node = ir_of("- include_tasks:\n    file: create_dir.yml\n").nodes[0]
    assert node.type is NodeType.TASK_INCLUDE
    assert node.include_target == "create_dir.yml"


def test_cozumlenemeyen_include_tasks_ham_olur() -> None:
    node = ir_of("- include_tasks:\n    - liste\n").nodes[0]
    assert node.type is NodeType.RAW


# ---------------------------------------------------------------------------
# Modul gorevleri
# ---------------------------------------------------------------------------


def test_modul_argumanlari_parametre_olur() -> None:
    node = ir_of("- name: kopyala\n  win_copy:\n    src: a\n    dest: b\n").nodes[0]
    assert node.type is NodeType.MODULE
    assert node.module == "win_copy"
    assert set(node.params) == {"src", "dest"}
    assert node.params["src"].pointer == "/0/win_copy/src"


def test_kisa_bicim_modul_tek_parametre_olur() -> None:
    node = ir_of("- name: calistir\n  win_shell: dir\n").nodes[0]
    assert node.module == "win_shell"
    assert node.params["win_shell"].value == "dir"


def test_register_yakalanir() -> None:
    node = ir_of("- win_shell: dir\n  register: sonuc\n").nodes[0]
    assert node.register == "sonuc"


def test_dongu_anahtarlari_korunur() -> None:
    node = ir_of('- win_file:\n    path: x\n  with_items: "{{ paths }}"\n').nodes[0]
    assert node.keywords["with_items"] == "{{ paths }}"


def test_modulsuz_gorev_ham_olur() -> None:
    node = ir_of("- name: yalnizca ad\n  when: true\n").nodes[0]
    assert node.type is NodeType.RAW
    assert "modul bulunamadi" in node.lock_reason


def test_cift_modullu_gorev_ham_olur() -> None:
    node = ir_of("- debug:\n    msg: a\n  win_shell: dir\n").nodes[0]
    assert node.type is NodeType.RAW
    assert "birden fazla modul" in node.lock_reason


# ---------------------------------------------------------------------------
# block
# ---------------------------------------------------------------------------


def test_block_yapisi_cocuk_uretir() -> None:
    text = (
        "- name: kapsayici\n"
        "  block:\n"
        "    - debug:\n"
        "        msg: bir\n"
        "  rescue:\n"
        "    - debug:\n"
        "        msg: iki\n"
    )
    node = ir_of(text).nodes[0]
    assert node.type is NodeType.BLOCK
    assert len(node.children) == 2
    assert all(child.type is NodeType.MODULE for child in node.children)


# ---------------------------------------------------------------------------
# Kilitleme
# ---------------------------------------------------------------------------


def test_jinja_ifadesi_iceren_parametre_kilitlenir() -> None:
    text = (
        "- win_iis_webapppool:\n    identityType: \"{% if item == 'x' %}a{% else %}b{% endif %}\"\n"
    )
    node = ir_of(text).nodes[0]
    ref = node.params["identityType"]
    assert ref.is_locked
    assert "Jinja" in ref.lock_reason


def test_basit_degisken_ikamesi_kilitlenmez() -> None:
    node = ir_of('- win_file:\n    path: "{{ item }}"\n').nodes[0]
    ref = node.params["path"]
    assert not ref.is_locked
    assert ref.is_templated


def test_cok_satirli_deger_kilitlenir() -> None:
    node = ir_of("- win_shell: |\n    satir bir\n    satir iki\n").nodes[0]
    assert node.params["win_shell"].is_locked
    assert "cok satirli" in node.params["win_shell"].lock_reason


def test_ic_ice_yapida_jinja_kilitlenir() -> None:
    text = '- win_dsc:\n    attributes:\n      inner: "{% if a %}b{% endif %}"\n'
    node = ir_of(text).nodes[0]
    assert node.params["attributes"].is_locked


def test_kismi_kilitleme_digerlerini_etkilemez() -> None:
    """Bir parametre kilitliyse gorev yine de tipli kalmali."""
    text = (
        "- name: karisik\n"
        "  win_iis_webapppool:\n"
        "    name: normal\n"
        '    identityType: "{% if a %}x{% endif %}"\n'
    )
    node = ir_of(text).nodes[0]
    assert node.type is NodeType.MODULE
    assert not node.is_locked
    assert node.locked_params == ["identityType"]
    assert not node.params["name"].is_locked


# ---------------------------------------------------------------------------
# Gezinme ve kimlik
# ---------------------------------------------------------------------------


def test_walk_ic_ice_dugumleri_dolasir() -> None:
    ir = ir_of(PLAYBOOK)
    assert len(list(ir.walk())) == 4  # 1 oynatma + 3 cocuk


def test_find_pointer_ile_dugum_bulur() -> None:
    ir = ir_of(PLAYBOOK)
    node = ir.find("/0/roles/0")
    assert node is not None
    assert node.role_name == "create_dir"
    assert ir.find("/yok") is None


def test_node_id_dosya_ve_pointer_birlestirir() -> None:
    assert node_id("playbooks/x.yml", "/0/roles/1") == "playbooks/x.yml#/0/roles/1"


def test_egik_cizgili_anahtar_pointerda_kacirilir() -> None:
    node = ir_of("- win_copy:\n    a/b: deger\n").nodes[0]
    assert node.params["a/b"].pointer == "/0/win_copy/a~1b"


# ---------------------------------------------------------------------------
# Ucdan uca: IR uzerinden duzenleme
# ---------------------------------------------------------------------------


def test_ir_uzerinden_parametre_duzenlenebilir() -> None:
    """IR'dan alinan pointer ile yapilan yama dosyanin geri kalanini bozmamalidir."""
    original = PLAYBOOK
    document = parse_document(original)
    ir = build_ir(document)

    role = ir.find("/0/roles/0")
    assert role is not None
    span = document.span(role.params["paths"].pointer)

    produced = serialize_document(
        document,
        [TextEdit(span.start, span.end, render_scalar(["D:\\Yeni", "D:\\Ikinci"]))],
    )

    assert "D:\\Yeni" in produced
    assert "test oynatma" in produced
    assert "pingpong" in produced
    assert parse_document(produced).is_parsed


def test_kilitli_parametre_duzenleme_icin_isaretlidir() -> None:
    """Kilitli bir parametre arayuze 'duzenlenemez' bilgisiyle gitmelidir."""
    text = "- win_shell: |\n    $x = 1\n    Write-Host $x\n"
    node = ir_of(text).nodes[0]
    ref = node.params["win_shell"]
    assert ref.is_locked
    assert ref.lock_reason
    assert ref.value.startswith("$x = 1")


# ---------------------------------------------------------------------------
# Savunma dallari: bozuk/beklenmedik girdi cokme yerine RAW uretmelidir
# ---------------------------------------------------------------------------


def test_include_tasks_sibling_vars_parametre_olarak_okunur() -> None:
    """Referans depoda gorulmese de include_tasks 'vars:' alabilir."""
    text = "- include_tasks: alt.yml\n  vars:\n    hedef: D:\\Kok\n"
    node = ir_of(text).nodes[0]
    assert node.type is NodeType.TASK_INCLUDE
    assert node.include_target == "alt.yml"
    assert node.params["hedef"].value == "D:\\Kok"
    assert node.params["hedef"].pointer == "/0/vars/hedef"


def test_include_tasks_cozumlenemeyen_hedef_raw_olur() -> None:
    text = "- include_tasks:\n    apply:\n      tags: x\n"
    node = ir_of(text).nodes[0]
    assert node.type is NodeType.RAW
    assert "cozumlenemedi" in node.lock_reason


def test_rol_girdisi_esleme_veya_metin_degilse_raw_olur() -> None:
    text = "- hosts: web\n  roles:\n    - [a, b]\n"
    play = ir_of(text).nodes[0]
    assert play.children[0].type is NodeType.RAW


def test_rol_girdisinde_role_anahtari_yoksa_raw_olur() -> None:
    text = "- hosts: web\n  roles:\n    - name: yalnizca-isim\n      when: true\n"
    entry = ir_of(text).nodes[0].children[0]
    assert entry.type is NodeType.RAW
    assert "'role' anahtari yok" in entry.lock_reason
    assert entry.name == "yalnizca-isim"


def test_roles_bolumune_yazilmis_gorev_sebebiyle_birlikte_raw_olur() -> None:
    """Referans depodaki gercek hatanin birim testi.

    ``roles:`` listesine gorev yazmak gecerli Ansible degildir; IR bunu
    bozmadan korumali ama kullaniciya nedenini soylemelidir.
    """
    text = "- hosts: web\n  roles:\n    - name: saglik\n      uri:\n        url: http://x\n"
    entry = ir_of(text).nodes[0].children[0]
    assert entry.type is NodeType.RAW
    assert "gorev gibi gorunuyor" in entry.lock_reason
    assert "uri" in entry.lock_reason


def test_gorev_esleme_degilse_raw_olur() -> None:
    text = "- hosts: web\n  tasks:\n    - duz-metin-gorev\n"
    task = ir_of(text).nodes[0].children[0]
    assert task.type is NodeType.RAW
    assert "esleme degil" in task.lock_reason


def test_liste_icindeki_jinja_ifadesi_parametreyi_kilitler() -> None:
    """Kilit karari listelerin icine de bakmalidir."""
    text = '- win_shell: x\n  loop:\n    - sabit\n    - "{% if a %}b{% endif %}"\n'
    node = ir_of(text).nodes[0]
    assert node.keywords["loop"]


def test_skaler_kok_config_sayilir() -> None:
    assert classify_document(parse_document("sadece-bir-metin\n")) is DocumentKind.CONFIG
