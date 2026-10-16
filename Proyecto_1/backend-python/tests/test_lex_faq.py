"""infra/lex/faq.yaml y la plantilla CloudFormation generada (PRO-19)."""

from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import re
from pathlib import Path
from typing import Any

import pytest

LEX_DIR = Path(__file__).resolve().parents[2] / "infra" / "lex"
_spec = importlib.util.spec_from_file_location("lex_build_template", LEX_DIR / "build_template.py")
builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)

TODAY = dt.date(2026, 10, 15)


@pytest.fixture
def faq() -> dict[str, Any]:
    return builder.load_faq(LEX_DIR / "faq.yaml")


def approved_faq() -> dict[str, Any]:
    """Datos sintéticos de prueba (no son información de la Facultad)."""
    source = {
        "title": "Fuente sintética de prueba",
        "url": "https://pruebas.invalid/fuente",
        "publisher": "Pruebas automatizadas",
        "accessedAt": dt.date(2026, 10, 1),
        "excerpt": "Fragmento sintético",
    }
    return {
        "version": 1,
        "bot": {
            "name": "semisocial-g15-facultad-bot",
            "locale": "es_419",
            "aliasName": "prod",
            "idleSessionTTLInSeconds": 300,
            "nluConfidenceThreshold": 0.4,
        },
        "fallback": {"status": "approved", "message": "Mensaje de fallback sintético"},
        "intents": [
            {
                "id": "PreguntaUno",
                "status": "approved",
                "topic": "prueba",
                "utterances": [f"pregunta uno variante {i}" for i in range(5)],
                "answer": "Respuesta sintética uno",
                "source": dict(source),
                "validUntil": None,
            },
            {
                "id": "PreguntaBorrador",
                "status": "draft",
                "topic": "prueba",
                "utterances": [f"borrador {i}" for i in range(5)],
                "answer": "[EJEMPLO] borrador",
                "source": dict(source),
            },
        ],
        "multiTurnIntents": [
            {
                "id": "VariosTurnos",
                "status": "approved",
                "topic": "prueba",
                "utterances": [f"varios turnos {i}" for i in range(4)] + ["consulta de {Opcion}"],
                "slot": {
                    "name": "Opcion",
                    "prompt": "¿Cuál opción?",
                    "values": [
                        {"value": "Uno", "synonyms": ["1"], "answer": "Respuesta Uno", "source": dict(source)},
                        {"value": "Dos", "answer": "Respuesta Dos", "source": dict(source)},
                    ],
                },
                "defaultAnswer": "Opción no reconocida",
            }
        ],
    }


def resources(template: dict[str, Any]) -> dict[str, Any]:
    return template["Resources"]


def locale(template: dict[str, Any]) -> dict[str, Any]:
    return resources(template)["FacultadBot"]["Properties"]["BotLocales"][0]


def intents_by_name(template: dict[str, Any]) -> dict[str, Any]:
    return {intent["Name"]: intent for intent in locale(template)["Intents"]}


# --- faq.yaml versionado -------------------------------------------------------


def _entries(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Entradas de contenido de la Facultad (un turno y varios turnos)."""
    return [*(data.get("intents") or []), *(data.get("multiTurnIntents") or [])]


def _conversational(data: dict[str, Any]) -> list[dict[str, Any]]:
    return list(data.get("conversationalIntents") or [])


def _approved_ids(entries: list[dict[str, Any]]) -> set[str]:
    return {entry["id"] for entry in entries if entry.get("status") == "approved"}


def _approved_texts(data: dict[str, Any]) -> list[tuple[str, str]]:
    """(dónde, texto) de cada texto visible o fuente de las entradas aprobadas."""
    texts: list[tuple[str, str]] = []
    if data["fallback"].get("status") == "approved":
        texts.append(("fallback.message", data["fallback"]["message"]))
    for entry in _entries(data):
        if entry.get("status") != "approved":
            continue
        where = entry["id"]
        for key in ("answer", "defaultAnswer"):
            if entry.get(key):
                texts.append((f"{where}.{key}", entry[key]))
        sources = [entry["source"]] if entry.get("source") else []
        slot = entry.get("slot") or {}
        if slot:
            texts.append((f"{where}.slot.prompt", slot["prompt"]))
            for value in slot.get("values") or []:
                texts.append((f"{where}.{value['value']}.answer", value["answer"]))
                sources.append(value["source"])
        for source in sources:
            texts.extend((f"{where}.source.{k}", str(source.get(k, ""))) for k in ("title", "url", "publisher", "excerpt"))
    for entry in _conversational(data):
        if entry.get("status") == "approved":
            texts.append((f"{entry['id']}.answer", entry["answer"]))
    return texts


def test_committed_faq_is_valid_and_approved_entries_have_no_examples(faq) -> None:
    # Pasa con todo en draft y sigue pasando a medida que se aprueban entradas.
    assert builder.validate_faq(faq, include_drafts=True) == []
    raw = (LEX_DIR / "faq.yaml").read_text(encoding="utf-8")
    gmail = re.findall(r"[\w.+-]+@gmail\.com", raw, flags=re.IGNORECASE)
    assert gmail == [], "faq.yaml no debe contener correos de Gmail"
    for where, text in _approved_texts(faq):
        assert builder.EXAMPLE_MARKER not in text, f"{where} aprobado contiene {builder.EXAMPLE_MARKER}"
        assert "example.org" not in text, f"{where} aprobado usa una URL de ejemplo"


def test_draft_entries_of_committed_faq_are_never_deployed(faq) -> None:
    every = _entries(faq) + _conversational(faq)
    drafts = {entry["id"] for entry in every if entry.get("status") != "approved"}
    approved = _approved_ids(_entries(faq))
    if not approved or faq["fallback"].get("status") != "approved":
        # Sin entradas o fallback aprobados no se puede generar el bot real.
        with pytest.raises(builder.FaqError):
            builder.build_template(faq)
        return
    intents = set(intents_by_name(builder.build_template(faq)))
    assert drafts.isdisjoint(intents)
    assert approved | _approved_ids(_conversational(faq)) | {"FallbackIntent"} == intents


# --- temas anunciados (fallback y saludo) ---------------------------------------

_TOPICS_RE = re.compile(r"Puedo ayudarte con: (.+?)\.(?:\s|$)")


def _listed_topics(text: str) -> list[str]:
    match = _TOPICS_RE.search(" ".join(text.split()))
    assert match, f"No se encontró 'Puedo ayudarte con: ...' en: {text[:80]}"
    return [topic.strip() for topic in re.split(r", | y ", match.group(1))]


def _topic_lists(data: dict[str, Any]) -> dict[str, list[str]]:
    lists = {"fallback": _listed_topics(data["fallback"]["message"])}
    for entry in _conversational(data):
        if entry.get("status") == "approved" and "Puedo ayudarte con:" in entry["answer"]:
            lists[entry["id"]] = _listed_topics(entry["answer"])
    return lists


def test_fallback_and_greeting_only_list_topics_of_approved_entries(faq) -> None:
    approved_topics = {e["topic"] for e in _entries(faq) if e.get("status") == "approved"}
    lists = _topic_lists(faq)
    assert "Saludo" in lists, "El saludo debe listar los temas disponibles"
    for where, topics in lists.items():
        unknown = [t for t in topics if t not in approved_topics]
        assert unknown == [], f"{where} menciona temas sin entrada aprobada: {unknown}"


def test_fallback_and_greeting_list_every_approved_topic(faq) -> None:
    # Al aprobar una entrada nueva, esta prueba recuerda agregar su tema al
    # fallback y al saludo.
    approved_topics = {e["topic"] for e in _entries(faq) if e.get("status") == "approved"}
    for where, topics in _topic_lists(faq).items():
        missing = sorted(approved_topics - set(topics))
        assert missing == [], f"{where} no menciona temas aprobados: {missing}"


def test_template_generation_is_deterministic_from_test_faq() -> None:
    data = approved_faq()
    first = builder.render(builder.build_template(data, today=TODAY), example=False)
    second = builder.render(builder.build_template(data, today=TODAY), example=False)
    assert first == second
    assert "PreguntaBorrador" not in first  # la entrada draft del faq de prueba no se despliega
    with_drafts = builder.render(builder.build_template(data, include_drafts=True, today=TODAY), example=True)
    assert "PreguntaBorrador" in with_drafts and "NO DESPLEGAR" in with_drafts


# --- sin anclas ni alias YAML (CloudFormation los rechaza) ------------------


def _yaml_anchors_and_aliases(text: str) -> list[str]:
    """Anclas (&x) y alias (*x) a nivel de sintaxis YAML, no dentro de textos."""
    import yaml

    found = []
    for event in yaml.parse(text):
        if isinstance(event, yaml.AliasEvent):
            found.append(f"*{event.anchor}")
        elif getattr(event, "anchor", None):
            found.append(f"&{event.anchor}")
    return found


def faq_with_shared_objects() -> dict[str, Any]:
    """Como el faq real: varios valores comparten la misma fuente (ancla en faq.yaml)."""
    data = approved_faq()
    shared_source = data["multiTurnIntents"][0]["slot"]["values"][0]["source"]
    shared_synonyms = ["1", "uno"]
    for value in data["multiTurnIntents"][0]["slot"]["values"]:
        value["source"] = shared_source
        value["synonyms"] = shared_synonyms
    data["intents"][0]["source"] = shared_source
    # Texto con "&" y "*" que NO es sintaxis YAML: no debe contarse como alias.
    data["intents"][0]["answer"] = "Respuesta con *id001 y &id002 como texto literal"
    return data


def test_rendered_template_has_no_yaml_anchors_or_aliases() -> None:
    text = builder.render(builder.build_template(faq_with_shared_objects(), today=TODAY), example=False)
    assert _yaml_anchors_and_aliases(text) == []
    assert "*id001 y &id002" in text  # el texto literal se conserva


def test_render_never_emits_aliases_even_for_shared_objects() -> None:
    import yaml

    template = builder.build_template(approved_faq(), today=TODAY)
    shared_tags = template["Resources"]["FacultadBot"]["Properties"]["BotTags"]
    template["Resources"]["FacultadBotRole"]["Properties"]["Tags"] = shared_tags  # mismo objeto dos veces
    text = builder.render(template, example=False)
    assert _yaml_anchors_and_aliases(text) == []
    # Mismo contenido: cada aparición se escribe completa.
    assert yaml.safe_load(text) == template


def test_committed_bot_template_has_no_yaml_anchors_or_aliases() -> None:
    bot = LEX_DIR / "bot.yaml"
    if not bot.exists():
        pytest.skip("infra/lex/bot.yaml no generado")
    assert _yaml_anchors_and_aliases(bot.read_text(encoding="utf-8")) == []


# --- longitud de mensajes de Lex V2 ------------------------------------------

# PlainTextMessage.value: "Minimum length of 1. Maximum length of 1000."
# https://docs.aws.amazon.com/lexv2/latest/APIReference/API_PlainTextMessage.html
# Lex cuenta "Unicode code units" (UTF-16):
# https://docs.aws.amazon.com/lexv2/latest/dg/quotas.html
LEX_MESSAGE_MAX = 1000


def _lex_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _plain_text_messages(node: Any) -> list[str]:
    if isinstance(node, dict):
        if set(node) == {"PlainTextMessage"}:
            return [node["PlainTextMessage"]["Value"]]
        return [m for value in node.values() for m in _plain_text_messages(value)]
    if isinstance(node, list):
        return [m for value in node for m in _plain_text_messages(value)]
    return []


def test_builder_limit_matches_lex_documentation() -> None:
    assert builder.MAX_MESSAGE_CHARS == LEX_MESSAGE_MAX


def test_all_committed_messages_fit_in_a_lex_message(faq) -> None:
    # Incluye drafts: el texto que se aprobará es el mismo que hoy está en draft.
    messages = _plain_text_messages(builder.build_template(faq, include_drafts=True))
    expected = 1 + len(_conversational(faq)) + sum(
        len((e.get("slot") or {}).get("values") or []) + 2 if e.get("slot") else 1 for e in _entries(faq)
    )
    # respuestas (con "Fuente: ..."), prompts, defaultAnswer, conversacionales y fallback
    assert len(messages) == expected
    too_long = [(m[:60], _lex_length(m)) for m in messages if _lex_length(m) > LEX_MESSAGE_MAX]
    assert too_long == [], f"Mensajes que superan {LEX_MESSAGE_MAX} unidades: {too_long}"


# --- plantilla ---------------------------------------------------------------


def test_template_has_bot_locale_version_and_prod_alias() -> None:
    template = builder.build_template(approved_faq(), today=TODAY)
    res = resources(template)
    assert {r["Type"] for r in res.values()} == {
        "AWS::IAM::Role",
        "AWS::Lex::Bot",
        "AWS::Lex::BotVersion",
        "AWS::Lex::BotAlias",
    }
    bot = res["FacultadBot"]["Properties"]
    assert bot["Name"] == "semisocial-g15-facultad-bot"
    assert bot["IdleSessionTTLInSeconds"] == 300
    assert locale(template)["LocaleId"] == "es_419"
    alias = res["FacultadBotAlias"]["Properties"]
    assert alias["BotAliasName"] == "prod"
    # versión numerada: el alias apunta al recurso BotVersion de este contenido
    assert alias["BotVersion"] == {"Fn::GetAtt": [version_logical_id(template), "BotVersion"]}
    assert set(template["Outputs"]) == {"LexBotId", "LexBotAliasId", "LexLocaleId", "LexBotAliasArn"}


def test_template_has_no_lambda_qna_or_bedrock() -> None:
    text = str(builder.build_template(approved_faq(), today=TODAY))
    for forbidden in ("Lambda", "CodeHook", "QnAIntent", "Bedrock", "Kendra", "TestBotAliasSettings"):
        assert forbidden not in text
    signatures = [i.get("ParentIntentSignature") for i in locale(builder.build_template(approved_faq(), today=TODAY))["Intents"]]
    assert [s for s in signatures if s] == ["AMAZON.FallbackIntent"]


def test_only_approved_entries_are_generated_and_answers_cite_source() -> None:
    intents = intents_by_name(builder.build_template(approved_faq(), today=TODAY))
    assert set(intents) == {"PreguntaUno", "VariosTurnos", "FallbackIntent"}
    message = intents["PreguntaUno"]["IntentClosingSetting"]["ClosingResponse"]["MessageGroupsList"][0]["Message"]
    assert message["PlainTextMessage"]["Value"] == (
        "Respuesta sintética uno\nFuente: Fuente sintética de prueba (consultado 2026-10-01)."
    )


def test_multi_turn_intent_uses_required_slot_and_conditional_branches() -> None:
    template = builder.build_template(approved_faq(), today=TODAY)
    intent = intents_by_name(template)["VariosTurnos"]
    assert intent["Slots"][0]["ValueElicitationSetting"]["SlotConstraint"] == "Required"
    assert intent["SlotPriorities"] == [{"Priority": 1, "SlotName": "Opcion"}]
    conditional = intent["IntentClosingSetting"]["Conditional"]
    assert [b["Condition"]["ExpressionString"] for b in conditional["ConditionalBranches"]] == [
        '{Opcion} = "Uno"',
        '{Opcion} = "Dos"',
    ]
    slot_type = locale(template)["SlotTypes"][0]
    assert slot_type["ValueSelectionSetting"] == {"ResolutionStrategy": "TOP_RESOLUTION"}
    assert slot_type["SlotTypeValues"][0] == {"SampleValue": {"Value": "Uno"}, "Synonyms": [{"Value": "1"}]}


# --- versiones: hash en el nombre lógico de BotVersion ---------------------


def version_logical_id(template: dict[str, Any]) -> str:
    ids = [k for k, r in resources(template).items() if r["Type"] == "AWS::Lex::BotVersion"]
    assert len(ids) == 1, ids
    return ids[0]


def _logical_ids(data: dict[str, Any]) -> tuple[str, str]:
    template = builder.build_template(data, today=TODAY)
    alias = [k for k, r in resources(template).items() if r["Type"] == "AWS::Lex::BotAlias"]
    assert len(alias) == 1
    return version_logical_id(template), alias[0]


def _changes() -> dict[str, Any]:
    def answer(d):
        d["intents"][0]["answer"] = "Respuesta sintética uno, corregida"

    def utterance(d):
        d["intents"][0]["utterances"].append("pregunta uno variante nueva")

    def threshold(d):
        d["bot"]["nluConfidenceThreshold"] = 0.5

    def fallback(d):
        d["fallback"]["message"] = "Otro mensaje de fallback sintético"

    def conversational(d):
        d["conversationalIntents"] = [
            {"id": "SaludoPrueba", "status": "approved", "utterances": [f"saludo {i}" for i in range(5)], "answer": "Hola"}
        ]

    return {f.__name__: f for f in (answer, utterance, threshold, fallback, conversational)}


def test_version_logical_id_is_alphanumeric_and_carries_content_hash() -> None:
    version_id, _ = _logical_ids(approved_faq())
    assert re.fullmatch(r"FacultadBotVersion[0-9a-f]{12}", version_id)
    assert re.fullmatch(r"[A-Za-z0-9]+", version_id)  # regla de nombres lógicos de CloudFormation


def test_version_logical_id_is_stable_without_content_change() -> None:
    assert _logical_ids(approved_faq()) == _logical_ids(approved_faq())
    # Las fechas de validación (today) no forman parte del contenido.
    template = builder.build_template(approved_faq(), today=dt.date(2026, 10, 20))
    assert version_logical_id(template) == _logical_ids(approved_faq())[0]


@pytest.mark.parametrize("change", list(_changes().values()), ids=list(_changes()))
def test_content_change_creates_new_version_but_keeps_alias(change) -> None:
    before_version, before_alias = _logical_ids(approved_faq())
    data = approved_faq()
    change(data)
    after_version, after_alias = _logical_ids(data)
    assert after_version != before_version
    assert after_alias == before_alias == builder.ALIAS_LOGICAL_ID == "FacultadBotAlias"


def test_alias_and_outputs_reference_current_version_and_fixed_alias() -> None:
    template = builder.build_template(approved_faq(), today=TODAY)
    alias = resources(template)["FacultadBotAlias"]["Properties"]
    assert alias["BotVersion"] == {"Fn::GetAtt": [version_logical_id(template), "BotVersion"]}
    assert template["Outputs"]["LexBotAliasId"]["Value"] == {"Fn::GetAtt": ["FacultadBotAlias", "BotAliasId"]}
    assert template["Outputs"]["LexBotAliasArn"]["Value"] == {"Fn::GetAtt": ["FacultadBotAlias", "Arn"]}


# --- intents conversacionales -------------------------------------------------


def faq_with_conversational() -> dict[str, Any]:
    data = approved_faq()
    data["conversationalIntents"] = [
        {
            "id": "Saludo",
            "status": "approved",
            "utterances": ["hola", "buenos días", "buenas tardes", "buenas noches", "saludos"],
            "answer": "¡Hola! Puedo ayudarte con: prueba.",
        },
        {
            "id": "AgradecimientoBorrador",
            "status": "draft",
            "utterances": ["gracias", "muchas gracias", "mil gracias", "te lo agradezco", "muy amable"],
            "answer": "¡De nada!",
        },
    ]
    return data


def test_conversational_intent_is_generated_without_source_line() -> None:
    intents = intents_by_name(builder.build_template(faq_with_conversational(), today=TODAY))
    value = intents["Saludo"]["IntentClosingSetting"]["ClosingResponse"]["MessageGroupsList"][0]["Message"]
    assert value["PlainTextMessage"]["Value"] == "¡Hola! Puedo ayudarte con: prueba."
    assert "Fuente" not in str(intents["Saludo"])
    assert [u["Utterance"] for u in intents["Saludo"]["SampleUtterances"]][0] == "hola"
    assert "AgradecimientoBorrador" not in intents  # draft no se despliega
    assert "AgradecimientoBorrador" in intents_by_name(
        builder.build_template(faq_with_conversational(), include_drafts=True, today=TODAY)
    )


def test_conversational_intents_alone_cannot_generate_a_bot() -> None:
    data = faq_with_conversational()
    for entry in _entries(data):
        entry["status"] = "draft"
    errors = builder.validate_faq(data, today=TODAY)
    assert any("no hay entradas aprobadas" in e for e in errors)


def mutate_conversational(change) -> list[str]:
    data = copy.deepcopy(faq_with_conversational())
    change(data["conversationalIntents"][0], data)
    return builder.validate_faq(data, include_drafts=True, today=TODAY)


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        (lambda e, d: e.update(source={"title": "x"}), "no llevan source"),
        (lambda e, d: e.update(answer="Visita https://portal.ingenieria.usac.edu.gt/"), "una URL"),
        (lambda e, d: e.update(answer="Escribe a alguien@ingenieria.usac.edu.gt"), "un correo"),
        (lambda e, d: e.update(answer="Atendemos de 08:00 a 13:00"), "cifras"),
        (lambda e, d: e.update(answer="Llama al 24189100"), "cifras"),
        (lambda e, d: e.update(answer=" "), "vacío"),
        (lambda e, d: e.update(answer="[EJEMPLO] hola", status="approved"), "[EJEMPLO]"),
        (lambda e, d: e.update(utterances=["hola", "buenas"]), "al menos 5"),
        (lambda e, d: e["utterances"].append("pregunta uno variante 0"), "repetida"),
        (lambda e, d: d["conversationalIntents"][1]["utterances"].append("¿Hola?"), "repetida"),
        (lambda e, d: e["utterances"].append("hola {Opcion}"), "slot desconocido"),
        (lambda e, d: e.update(id="PreguntaUno"), "id repetido"),
        (lambda e, d: e.update(id="FallbackIntent"), "id inválido"),
    ],
)
def test_invalid_conversational_intent_is_rejected(change, fragment: str) -> None:
    errors = mutate_conversational(change)
    assert any(fragment in error for error in errors), errors


def test_valid_conversational_intents_have_no_errors() -> None:
    assert builder.validate_faq(faq_with_conversational(), include_drafts=True, today=TODAY) == []


# --- validación ---------------------------------------------------------------


def mutate(change) -> list[str]:
    data = copy.deepcopy(approved_faq())
    change(data)
    return builder.validate_faq(data, today=TODAY)


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        (lambda d: d["intents"][0]["source"].pop("url"), "falta source.url"),
        (lambda d: d["intents"][0]["source"].pop("accessedAt"), "falta source.accessedAt"),
        (lambda d: d["intents"][0]["source"].pop("excerpt"), "falta source.excerpt"),
        (lambda d: d["intents"][0].pop("source"), "falta source"),
        (lambda d: d["intents"][0]["source"].update(url="http://inseguro.invalid"), "https"),
        (lambda d: d["intents"][0]["source"].update(url="https://example.org/x"), "URL de ejemplo"),
        (lambda d: d["intents"][0]["source"].update(accessedAt="15/10/2026"), "fecha ISO"),
        (lambda d: d["intents"][0]["source"].update(accessedAt=dt.date(2026, 12, 1)), "futuro"),
        (lambda d: d["intents"][0].update(answer="[EJEMPLO] algo"), "[EJEMPLO]"),
        (lambda d: d["intents"][0].update(answer="  "), "vacío"),
        (lambda d: d["intents"][0].update(answer="x" * 1000), "supera 1000"),
        (lambda d: d["intents"][0].update(validUntil=dt.date(2026, 1, 1)), "venció"),
        (lambda d: d["intents"][0].update(utterances=["solo una"]), "al menos 5"),
        (lambda d: d["intents"][0]["utterances"].append("¿Varios turnos 0?"), "repetida"),
        (lambda d: d["intents"][0]["utterances"].append("hola {Desconocido}"), "slot desconocido"),
        (lambda d: d["intents"][0].update(id="FallbackIntent"), "id inválido"),
        (lambda d: d["intents"][0].update(id="con espacio"), "id inválido"),
        (lambda d: d["multiTurnIntents"][0].update(id="PreguntaUno"), "id repetido"),
        (lambda d: d["intents"][0].update(status="publicado"), "status"),
        (lambda d: d["fallback"].update(status="draft"), "fallback"),
        (lambda d: d["bot"].update(locale="es_ES"), "es_419"),
        (lambda d: d["bot"].update(aliasName="TestBotAlias"), "TestBotAlias"),
        (lambda d: d["bot"].update(idleSessionTTLInSeconds=30), "idleSessionTTLInSeconds"),
        (
            lambda d: d["multiTurnIntents"][0]["slot"].update(
                values=[{"value": f"V{i}", "answer": "a", "source": d["intents"][0]["source"]} for i in range(5)]
            ),
            "entre 1 y 4",
        ),
        (lambda d: d["multiTurnIntents"][0]["slot"]["values"][1].update(value="uno"), "value repetido"),
        (lambda d: d["multiTurnIntents"][0]["slot"]["values"][0].update(value='con "comillas"'), "comillas"),
        (lambda d: d["multiTurnIntents"][0]["slot"]["values"][0].pop("source"), "falta source"),
    ],
)
def test_invalid_faq_is_rejected(change, fragment: str) -> None:
    errors = mutate(change)
    assert any(fragment in error for error in errors), errors


def test_valid_approved_faq_has_no_errors() -> None:
    assert builder.validate_faq(approved_faq(), today=TODAY) == []


def test_cli_check_and_generation(tmp_path: Path, capsys) -> None:
    import yaml

    approved = tmp_path / "faq-approved.yaml"
    approved.write_text(yaml.safe_dump(approved_faq(), allow_unicode=True), encoding="utf-8")
    drafts_only = copy.deepcopy(approved_faq())
    for entry in [drafts_only["fallback"], *_entries(drafts_only)]:
        entry["status"] = "draft"
    draft = tmp_path / "faq-draft.yaml"
    draft.write_text(yaml.safe_dump(drafts_only, allow_unicode=True), encoding="utf-8")

    assert builder.main([str(draft), "--check"]) == 1
    assert builder.main([str(draft), "--check", "--include-drafts"]) == 0
    not_written = tmp_path / "no-bot.yaml"
    assert builder.main([str(draft), "-o", str(not_written)]) == 1
    assert not not_written.exists()

    assert builder.main([str(approved), "--check"]) == 0
    output = tmp_path / "bot.yaml"
    assert builder.main([str(approved), "-o", str(output)]) == 0
    assert "PreguntaBorrador" not in output.read_text(encoding="utf-8")


def test_cli_validates_committed_faq(capsys) -> None:
    assert builder.main([str(LEX_DIR / "faq.yaml"), "--check", "--include-drafts"]) == 0
