"""Kayipsiz YAML okuma ve cerrahi metin yamasi.

Bu modul projenin temel sozlesmesini uygular: bir YAML dosyasi okunup geri
yazildiginda, dokunulmayan hicbir bayt degismez.

Bunu saglamak icin dosyalar YENIDEN URETILMEZ. Bunun yerine:

1. ``ruamel.yaml`` ile ayristirma yapilir ve her dugum icin kaynak metindeki
   tam karakter araligi (span) cikarilir.
2. Degisiklikler ``TextEdit`` olarak biriktirilir.
3. Yamalar orijinal metne, konuma gore TERSTEN uygulanir.

Gerekce ve olcum verisi: docs/adr/ADR-0007-surgical-text-patching.md
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from ruamel.yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode
from ruamel.yaml.scalarstring import DoubleQuotedScalarString, SingleQuotedScalarString

from app.core.errors import RoundTripError, ValidationError

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = [
    "NodeSpan",
    "TextEdit",
    "YamlDocument",
    "apply_edits",
    "escape_pointer_token",
    "parse_document",
    "render_scalar",
    "serialize_document",
]

_BOM = "\ufeff"

_QUOTE_WRAPPERS = {
    "'": SingleQuotedScalarString,
    '"': DoubleQuotedScalarString,
}


# ---------------------------------------------------------------------------
# Konum bilgisi
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NodeSpan:
    """Kaynak metindeki bir YAML dugumunun tam karakter araligi.

    Args:
        pointer: JSON-pointer benzeri adres. Ornek: ``/0/vars/paths/3``.
        start: Aralik baslangici (dahil), normallestirilmis metne gore indeks.
        end: Aralik bitisi (haric).
        kind: ``scalar``, ``sequence`` veya ``mapping``.
        style: Skalerler icin tirnak/blok stili; yoksa bos dize.
    """

    pointer: str
    start: int
    end: int
    kind: str
    style: str = ""

    @property
    def is_scalar(self) -> bool:
        return self.kind == "scalar"


@dataclass(frozen=True, slots=True)
class TextEdit:
    """Orijinal metin uzerinde tek bir hedefli degisiklik.

    Args:
        start: Degistirilecek araligin baslangici (dahil).
        end: Degistirilecek araligin bitisi (haric).
        replacement: Araligin yerine gececek metin.
        reason: Denetim ve hata ayiklama icin kisa aciklama.
    """

    start: int
    end: int
    replacement: str
    reason: str = ""

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValidationError(
                "Gecersiz metin araligi",
                details={"start": self.start, "end": self.end},
            )


def apply_edits(text: str, edits: list[TextEdit]) -> str:
    """Yamalari metne uygular.

    Yamalar konuma gore tersten uygulanir; boylece onceki yamalar sonrakilerin
    indekslerini kaydirmaz.

    Args:
        text: Uzerinde islem yapilacak orijinal metin.
        edits: Uygulanacak yamalar. Sirali olmalari gerekmez.

    Returns:
        Yamalar uygulanmis metin. ``edits`` bossa girdinin aynisi.

    Raises:
        ValidationError: Yamalar cakisiyorsa veya metin sinirlarini asiyorsa.
    """
    if not edits:
        return text

    ordered = sorted(edits, key=lambda e: (e.start, e.end))

    previous_end = -1
    for edit in ordered:
        if edit.end > len(text):
            raise ValidationError(
                "Yama metin sinirlarinin disinda",
                details={"end": edit.end, "length": len(text)},
            )
        if edit.start < previous_end:
            raise ValidationError(
                "Cakisan yamalar uygulanamaz",
                details={"start": edit.start, "previous_end": previous_end},
            )
        previous_end = edit.end

    result = text
    for edit in reversed(ordered):
        result = result[: edit.start] + edit.replacement + result[edit.end :]
    return result


# ---------------------------------------------------------------------------
# Belge
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class YamlDocument:
    """Ayristirilmis bir YAML dosyasi ve onu kayipsiz geri yazmak icin gereken her sey.

    ``original_text`` gercegin kaynagidir. ``data`` ve ``spans`` bu metnin
    uzerine kurulmus goruntulerdir.
    """

    original_text: str
    """Dosyanin diskteki hali (BOM ve satir sonlari dahil, aynen)."""

    normalized_text: str
    """BOM'suz ve LF satir sonlu hali. Tum indeksler buna goredir."""

    data: Any
    """ruamel tarafindan uretilen veri (``CommentedMap`` / ``CommentedSeq`` / None)."""

    spans: dict[str, NodeSpan] = field(default_factory=dict)
    """Pointer -> karakter araligi eslemesi."""

    newline: str = "\n"
    """Dosyanin satir sonu stili: ``\\n`` veya ``\\r\\n``."""

    has_bom: bool = False
    """Dosya UTF-8 BOM ile mi basliyor."""

    parse_error: str | None = None
    """Ayristirma basarisizsa hatanin ozeti; basariliysa ``None``."""

    @property
    def is_parsed(self) -> bool:
        """Belge ayristirilabildi mi. Ayristirilamayan belgeler salt-okunurdur."""
        return self.parse_error is None

    def span(self, pointer: str) -> NodeSpan:
        """Bir pointer icin karakter araligini dondurur.

        Raises:
            ValidationError: Pointer bu belgede yoksa.
        """
        try:
            return self.spans[pointer]
        except KeyError:
            raise ValidationError(
                "Belgede boyle bir dugum yok",
                details={"pointer": pointer},
            ) from None

    def text_at(self, pointer: str) -> str:
        """Bir dugumun kaynak metindeki ham halini dondurur."""
        located = self.span(pointer)
        return self.normalized_text[located.start : located.end]

    def iter_spans(self, prefix: str = "") -> Iterator[NodeSpan]:
        """Belirli bir on ekle baslayan tum araliklari dolasir."""
        for pointer, located in self.spans.items():
            if pointer.startswith(prefix):
                yield located


# ---------------------------------------------------------------------------
# Ayristirma
# ---------------------------------------------------------------------------


def _make_yaml() -> YAML:
    """Projenin tek YAML yapilandirmasi.

    ADR-0002 geregi yalnizca round-trip modu kullanilir.
    """
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.width = 1_000_000
    return yaml


def _detect_newline(text: str) -> str:
    """Metnin baskin satir sonu stilini tespit eder.

    Karma satir sonu iceren dosyalarda cogunluk kazanir; ancak bu durumda
    yeniden birlestirme kayipli olabilecegi icin cagiran taraf uyarilmalidir.
    """
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    return "\r\n" if crlf > lf else "\n"


def _quote_style(node: ScalarNode) -> str:
    """Bir skaler dugumun tirnak/blok stilini dondurur."""
    style = getattr(node, "style", None)
    return style if isinstance(style, str) else ""


def escape_pointer_token(token: str) -> str:
    """Bir anahtari JSON-pointer bilesenine cevirir (RFC 6901).

    ``~`` ve ``/`` karakterleri kacirilir; boylece ``a/b`` adli bir anahtar
    ``a~1b`` olarak adreslenir ve yol ayraciyla karismaz.
    """
    return token.replace("~", "~0").replace("/", "~1")


def _collect_spans(node: Node, pointer: str, out: dict[str, NodeSpan]) -> None:
    """Dugum agacini dolasarak pointer -> aralik eslemesi kurar."""
    start = node.start_mark.index
    end = node.end_mark.index

    if isinstance(node, ScalarNode):
        out[pointer] = NodeSpan(pointer, start, end, "scalar", _quote_style(node))
        return

    if isinstance(node, SequenceNode):
        out[pointer] = NodeSpan(pointer, start, end, "sequence")
        for index, child in enumerate(node.value):
            _collect_spans(child, f"{pointer}/{index}", out)
        return

    if isinstance(node, MappingNode):
        out[pointer] = NodeSpan(pointer, start, end, "mapping")
        for key_node, value_node in node.value:
            key = key_node.value if isinstance(key_node, ScalarNode) else "?"
            _collect_spans(value_node, f"{pointer}/{escape_pointer_token(str(key))}", out)


def parse_document(text: str) -> YamlDocument:
    """Bir YAML metnini kayipsiz islenebilir bir belgeye cevirir.

    Ayristirma basarisiz olursa istisna FIRLATILMAZ. Bunun yerine belge
    ``parse_error`` alani dolu olarak doner ve salt-okunur kabul edilir.
    Referans depoda gercekten bozuk dosyalar vardir; bunlar platformun
    calismasini engellememelidir.

    Args:
        text: Dosya icerigi. Satir sonlari ve BOM aynen korunur.

    Returns:
        Ayristirilmis belge. ``is_parsed`` ile durumu kontrol edilmelidir.
    """
    has_bom = text.startswith(_BOM)
    body = text[len(_BOM) :] if has_bom else text
    newline = _detect_newline(body)
    normalized = body.replace("\r\n", "\n")

    document = YamlDocument(
        original_text=text,
        normalized_text=normalized,
        data=None,
        newline=newline,
        has_bom=has_bom,
    )

    yaml = _make_yaml()
    try:
        root = yaml.compose(normalized)
    except YAMLError as exc:
        document.parse_error = _summarize(exc)
        return document

    if root is None:
        return document

    spans: dict[str, NodeSpan] = {}
    _collect_spans(root, "", spans)
    document.spans = spans

    try:
        document.data = yaml.load(normalized)
    except YAMLError as exc:
        document.parse_error = _summarize(exc)

    return document


def _summarize(exc: YAMLError) -> str:
    """Bir YAML hatasini tek satirlik ozete cevirir."""
    message = str(exc).strip().splitlines()
    head = message[0] if message else exc.__class__.__name__
    return f"{exc.__class__.__name__}: {head}"


# ---------------------------------------------------------------------------
# Geri yazma
# ---------------------------------------------------------------------------


def serialize_document(document: YamlDocument, edits: list[TextEdit] | None = None) -> str:
    """Belgeyi, istege bagli yamalarla birlikte metne cevirir.

    Yama yoksa cikti girdinin BIREBIR AYNISIDIR; bu, kayipsizlik sozlesmesinin
    tanim geregi saglanmasi demektir.

    Args:
        document: Yazilacak belge.
        edits: Uygulanacak yamalar. ``None`` veya bos ise dosya aynen doner.

    Returns:
        Diske yazilabilir metin (orijinal satir sonu stili ve BOM ile).

    Raises:
        RoundTripError: Yama uygulandiktan sonra sonuc gecerli YAML degilse.
    """
    if not edits:
        return document.original_text

    if not document.is_parsed:
        raise RoundTripError(
            "Ayristirilamayan bir dosya duzenlenemez",
            details={"parse_error": document.parse_error},
        )

    patched = apply_edits(document.normalized_text, edits)

    yaml = _make_yaml()
    try:
        yaml.load(patched)
    except YAMLError as exc:
        raise RoundTripError(
            "Yama sonrasi dosya gecerli YAML degil, yazma iptal edildi",
            details={"error": _summarize(exc)},
        ) from exc

    return _restore_format(patched, document)


def _restore_format(normalized: str, document: YamlDocument) -> str:
    """Normallestirilmis metni dosyanin orijinal bicimine geri cevirir."""
    restored = normalized
    if document.newline != "\n":
        restored = restored.replace("\n", document.newline)
    return _BOM + restored if document.has_bom else restored


# ---------------------------------------------------------------------------
# Deger uretimi
# ---------------------------------------------------------------------------


def render_scalar(value: object, *, style: str = "") -> str:
    """Tek bir skaler degeri YAML gosterimine cevirir.

    Elle string birlestirme yerine ``ruamel`` kullanilir; boylece kacirma
    kurallari (tirnak, ozel karakter) kutuphaneye birakilir.

    Args:
        value: Yazilacak deger.
        style: Zorlanacak tirnak stili: ``'``, ``"`` veya bos (otomatik).

    Returns:
        Satir sonu icermeyen tek satirlik YAML gosterimi.
    """
    payload = value
    if isinstance(value, str) and style:
        wrapper = _QUOTE_WRAPPERS.get(style)
        if wrapper is not None:
            payload = wrapper(value)

    buffer = io.StringIO()
    _make_yaml().dump(payload, buffer)
    return buffer.getvalue().rstrip("\n").removesuffix("...").rstrip()
