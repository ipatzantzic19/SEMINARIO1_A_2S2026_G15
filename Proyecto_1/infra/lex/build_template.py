"""Genera la plantilla CloudFormation del bot Lex V2 a partir de faq.yaml (PRO-19).

Uso (desde Proyecto_1, con el venv de backend-python que ya trae PyYAML):

    python infra/lex/build_template.py infra/lex/faq.yaml -o infra/lex/bot.yaml
    python infra/lex/build_template.py infra/lex/faq.yaml --check        # solo valida
    python infra/lex/build_template.py infra/lex/faq.yaml --include-drafts -o infra/lex/bot.example.yaml

Sin ``--include-drafts`` solo se incluyen entradas ``status: approved`` y el
script falla si no hay ninguna. La plantilla NO se despliega desde aquí.

Recursos generados: rol del bot (sin permisos: bot solo de texto), bot con un
locale, intents con respuesta de cierre (sin Lambda, sin QnAIntent/Bedrock),
FallbackIntent, versión numerada y alias ``prod`` apuntando a esa versión.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

EXAMPLE_MARKER = "[EJEMPLO]"
STATUSES = ("draft", "approved")
_INTENT_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,99}$")
_SLOT_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,99}$")
_SLOT_REF_RE = re.compile(r"\{([^}]*)\}")
MIN_UTTERANCES = 5
MAX_MESSAGE_CHARS = 1000  # PlainTextMessage.Value
MAX_UTTERANCE_CHARS = 200
MAX_BRANCHES = 4  # ramas condicionales por bloque
SOURCE_FIELDS = ("title", "url", "publisher", "accessedAt", "excerpt")


class FaqError(ValueError):
    """faq.yaml inválido; ``errors`` lista cada problema."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("faq.yaml inválido:\n- " + "\n- ".join(errors))


def load_faq(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


# --------------------------------------------------------------------------
# Validación
# --------------------------------------------------------------------------


def _included(entry: dict[str, Any], include_drafts: bool) -> bool:
    return entry.get("status") == "approved" or include_drafts


def _check_source(where: str, source: Any, approved: bool, today: dt.date, errors: list[str]) -> None:
    if not isinstance(source, dict):
        errors.append(f"{where}: falta source")
        return
    for name in SOURCE_FIELDS:
        if source.get(name) in (None, ""):
            errors.append(f"{where}: falta source.{name}")
    url = str(source.get("url") or "")
    if url and not url.startswith("https://"):
        errors.append(f"{where}: source.url debe usar https")
    accessed = source.get("accessedAt")
    if accessed not in (None, "") and not isinstance(accessed, dt.date):
        errors.append(f"{where}: source.accessedAt debe ser una fecha ISO (AAAA-MM-DD)")
    elif isinstance(accessed, dt.date) and accessed > today:
        errors.append(f"{where}: source.accessedAt está en el futuro")
    if approved and "example.org" in url:
        errors.append(f"{where}: una entrada aprobada no puede usar una URL de ejemplo")


def _check_text(where: str, text: Any, approved: bool, errors: list[str]) -> None:
    if not isinstance(text, str) or not text.strip():
        errors.append(f"{where}: no puede estar vacío")
    elif approved and EXAMPLE_MARKER in text:
        errors.append(f"{where}: una entrada aprobada contiene {EXAMPLE_MARKER}")


def _check_valid_until(where: str, entry: dict[str, Any], approved: bool, today: dt.date, errors: list[str]) -> None:
    until = entry.get("validUntil")
    if until is None:
        return
    if not isinstance(until, dt.date):
        errors.append(f"{where}: validUntil debe ser una fecha ISO o null")
    elif approved and until < today:
        errors.append(f"{where}: validUntil ya venció ({until.isoformat()}); actualice la información")


def _check_length(where: str, answer: Any, source: Any, errors: list[str]) -> None:
    if isinstance(answer, str) and isinstance(source, dict) and source.get("title") and source.get("accessedAt"):
        if len(closing_message(answer, source)) > MAX_MESSAGE_CHARS:
            errors.append(f"{where}: la respuesta con la fuente supera {MAX_MESSAGE_CHARS} caracteres")


def closing_message(answer: str, source: dict[str, Any]) -> str:
    accessed = source["accessedAt"]
    accessed_text = accessed.isoformat() if isinstance(accessed, dt.date) else str(accessed)
    return f"{answer.strip()}\nFuente: {source['title']} (consultado {accessed_text})."


def validate_faq(
    data: Any, *, include_drafts: bool = False, today: dt.date | None = None
) -> list[str]:
    today = today or dt.date.today()
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["el archivo debe ser un objeto YAML"]
    bot = data.get("bot") or {}
    if bot.get("locale") != "es_419":
        errors.append("bot.locale debe ser es_419 (decisión PRO-19)")
    if not isinstance(bot.get("idleSessionTTLInSeconds"), int) or not 60 <= bot["idleSessionTTLInSeconds"] <= 86400:
        errors.append("bot.idleSessionTTLInSeconds debe ser un entero entre 60 y 86400")
    if bot.get("aliasName") in (None, "", "TestBotAlias"):
        errors.append("bot.aliasName es obligatorio y no puede ser TestBotAlias")
    threshold = bot.get("nluConfidenceThreshold")
    if not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
        errors.append("bot.nluConfidenceThreshold debe estar entre 0 y 1")

    fallback = data.get("fallback") or {}
    if fallback.get("status") not in STATUSES:
        errors.append("fallback.status debe ser draft o approved")
    _check_text("fallback.message", fallback.get("message"), fallback.get("status") == "approved", errors)
    if not include_drafts and fallback.get("status") != "approved":
        errors.append("fallback: el mensaje de fallback debe estar aprobado para generar el bot")

    seen_ids: set[str] = set()
    seen_utterances: dict[str, str] = {}
    included = 0

    def check_common(kind: str, index: int, entry: Any) -> tuple[str, bool] | None:
        if not isinstance(entry, dict):
            errors.append(f"{kind}[{index}]: debe ser un objeto")
            return None
        intent_id = str(entry.get("id") or "")
        where = f"{kind}[{index}] {intent_id or '(sin id)'}"
        if not _INTENT_ID_RE.match(intent_id) or intent_id == "FallbackIntent":
            errors.append(f"{where}: id inválido (letras, números y _; no FallbackIntent)")
        elif intent_id in seen_ids:
            errors.append(f"{where}: id repetido")
        seen_ids.add(intent_id)
        if entry.get("status") not in STATUSES:
            errors.append(f"{where}: status debe ser draft o approved")
        return where, entry.get("status") == "approved"

    def check_utterances(where: str, entry: dict[str, Any], slot_name: str | None) -> None:
        utterances = entry.get("utterances") or []
        if len(utterances) < MIN_UTTERANCES:
            errors.append(f"{where}: se requieren al menos {MIN_UTTERANCES} utterances")
        for utterance in utterances:
            text = str(utterance).strip()
            if not text or len(text) > MAX_UTTERANCE_CHARS:
                errors.append(f"{where}: utterance vacía o de más de {MAX_UTTERANCE_CHARS} caracteres")
            for ref in _SLOT_REF_RE.findall(text):
                if ref != slot_name:
                    errors.append(f"{where}: la utterance referencia un slot desconocido {{{ref}}}")
            key = text.lower().rstrip("?¿!¡. ").lstrip("¿¡")
            if key in seen_utterances:
                errors.append(f"{where}: utterance repetida (también en {seen_utterances[key]}): {text}")
            seen_utterances[key] = where

    for index, entry in enumerate(data.get("intents") or []):
        checked = check_common("intents", index, entry)
        if not checked:
            continue
        where, approved = checked
        if not _included(entry, include_drafts):
            continue
        included += 1
        check_utterances(where, entry, None)
        _check_text(f"{where}.answer", entry.get("answer"), approved, errors)
        _check_source(where, entry.get("source"), approved, today, errors)
        _check_valid_until(where, entry, approved, today, errors)
        _check_length(where, entry.get("answer"), entry.get("source"), errors)

    for index, entry in enumerate(data.get("multiTurnIntents") or []):
        checked = check_common("multiTurnIntents", index, entry)
        if not checked:
            continue
        where, approved = checked
        if not _included(entry, include_drafts):
            continue
        included += 1
        slot = entry.get("slot") or {}
        slot_name = str(slot.get("name") or "")
        if not _SLOT_NAME_RE.match(slot_name):
            errors.append(f"{where}: slot.name inválido")
        check_utterances(where, entry, slot_name)
        _check_text(f"{where}.slot.prompt", slot.get("prompt"), approved, errors)
        _check_text(f"{where}.defaultAnswer", entry.get("defaultAnswer"), approved, errors)
        _check_valid_until(where, entry, approved, today, errors)
        values = slot.get("values") or []
        if not 1 <= len(values) <= MAX_BRANCHES:
            errors.append(f"{where}: slot.values debe tener entre 1 y {MAX_BRANCHES} valores")
        seen_values: set[str] = set()
        for value_index, value in enumerate(values):
            value_where = f"{where}.slot.values[{value_index}]"
            name = str((value or {}).get("value") or "").strip()
            if not name or '"' in name:
                errors.append(f"{value_where}: value vacío o con comillas")
            elif name.lower() in seen_values:
                errors.append(f"{value_where}: value repetido")
            seen_values.add(name.lower())
            _check_text(f"{value_where}.answer", (value or {}).get("answer"), approved, errors)
            _check_source(value_where, (value or {}).get("source"), approved, today, errors)
            _check_length(value_where, (value or {}).get("answer"), (value or {}).get("source"), errors)

    if included == 0:
        errors.append(
            "no hay entradas aprobadas (status: approved); use --include-drafts solo para la plantilla de ejemplo"
        )
    return errors


# --------------------------------------------------------------------------
# Plantilla
# --------------------------------------------------------------------------


def _messages(text: str) -> dict[str, Any]:
    return {"MessageGroupsList": [{"Message": {"PlainTextMessage": {"Value": text}}}], "AllowInterrupt": False}


def _end_conversation() -> dict[str, Any]:
    return {"DialogAction": {"Type": "EndConversation"}}


def _single_turn_intent(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "Name": entry["id"],
        "Description": f"{entry.get('topic', '')} | fuente: {entry['source']['title']}"[:200],
        "SampleUtterances": [{"Utterance": str(u).strip()} for u in entry["utterances"]],
        "IntentClosingSetting": {
            "IsActive": True,
            "ClosingResponse": _messages(closing_message(entry["answer"], entry["source"])),
        },
    }


def _multi_turn(entry: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    slot = entry["slot"]
    slot_type_name = f"{entry['id']}{slot['name']}Tipo"
    slot_type = {
        "Name": slot_type_name,
        "Description": f"Valores de {slot['name']} para {entry['id']}",
        "ValueSelectionSetting": {"ResolutionStrategy": "TOP_RESOLUTION"},
        "SlotTypeValues": [
            {
                "SampleValue": {"Value": value["value"]},
                **({"Synonyms": [{"Value": s} for s in value["synonyms"]]} if value.get("synonyms") else {}),
            }
            for value in slot["values"]
        ],
    }
    branches = [
        {
            "Name": f"Valor{index + 1}",
            "Condition": {"ExpressionString": f'{{{slot["name"]}}} = "{value["value"]}"'},
            "NextStep": _end_conversation(),
            "Response": _messages(closing_message(value["answer"], value["source"])),
        }
        for index, value in enumerate(slot["values"])
    ]
    intent = {
        "Name": entry["id"],
        "Description": f"{entry.get('topic', '')} (varios turnos)"[:200],
        "SampleUtterances": [{"Utterance": str(u).strip()} for u in entry["utterances"]],
        "Slots": [
            {
                "Name": slot["name"],
                "SlotTypeName": slot_type_name,
                "ValueElicitationSetting": {
                    "SlotConstraint": "Required",
                    "PromptSpecification": {**_messages(slot["prompt"]), "MaxRetries": 2, "AllowInterrupt": True},
                },
            }
        ],
        "SlotPriorities": [{"Priority": 1, "SlotName": slot["name"]}],
        "IntentClosingSetting": {
            "IsActive": True,
            "Conditional": {
                "IsActive": True,
                "ConditionalBranches": branches,
                "DefaultBranch": {"NextStep": _end_conversation(), "Response": _messages(entry["defaultAnswer"])},
            },
        },
    }
    return intent, slot_type


def build_template(data: dict[str, Any], *, include_drafts: bool = False, today: dt.date | None = None) -> dict[str, Any]:
    errors = validate_faq(data, include_drafts=include_drafts, today=today)
    if errors:
        raise FaqError(errors)
    bot = data["bot"]
    locale = bot["locale"]

    intents: list[dict[str, Any]] = []
    slot_types: list[dict[str, Any]] = []
    for entry in data.get("intents") or []:
        if _included(entry, include_drafts):
            intents.append(_single_turn_intent(entry))
    for entry in data.get("multiTurnIntents") or []:
        if _included(entry, include_drafts):
            intent, slot_type = _multi_turn(entry)
            intents.append(intent)
            slot_types.append(slot_type)
    intents.append(
        {
            "Name": "FallbackIntent",
            "Description": "Entrada no entendida",
            "ParentIntentSignature": "AMAZON.FallbackIntent",
            "IntentClosingSetting": {"IsActive": True, "ClosingResponse": _messages(data["fallback"]["message"].strip())},
        }
    )

    bot_locale: dict[str, Any] = {
        "LocaleId": locale,
        "Description": "Bot de la Facultad de Ingeniería (Semi-Social)",
        "NluConfidenceThreshold": float(bot["nluConfidenceThreshold"]),
        "Intents": intents,
    }
    if slot_types:
        bot_locale["SlotTypes"] = slot_types
    # BotVersion solo publica una versión nueva si cambian sus propiedades: el
    # hash del contenido fuerza una versión (y mueve el alias) en cada cambio.
    content_hash = hashlib.sha256(
        json.dumps([bot, bot_locale], sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()[:12]

    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": f"PRO-19: bot Lex V2 {bot['name']} ({locale}), generado desde infra/lex/faq.yaml.",
        "Resources": {
            "FacultadBotRole": {
                "Type": "AWS::IAM::Role",
                "Properties": {
                    "Description": "Rol de ejecución del bot Lex (solo texto; sin permisos adicionales).",
                    "AssumeRolePolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Principal": {"Service": "lexv2.amazonaws.com"},
                                "Action": "sts:AssumeRole",
                                "Condition": {"StringEquals": {"aws:SourceAccount": {"Ref": "AWS::AccountId"}}},
                            }
                        ],
                    },
                    "Tags": [{"Key": "Project", "Value": "Semi-Social"}, {"Key": "Ticket", "Value": "PRO-19"}],
                },
            },
            "FacultadBot": {
                "Type": "AWS::Lex::Bot",
                "Properties": {
                    "Name": bot["name"],
                    "Description": "Bot de consultas de la Facultad de Ingeniería (Semi-Social, PRO-19).",
                    "RoleArn": {"Fn::GetAtt": ["FacultadBotRole", "Arn"]},
                    "DataPrivacy": {"ChildDirected": False},
                    "IdleSessionTTLInSeconds": bot["idleSessionTTLInSeconds"],
                    "AutoBuildBotLocales": True,
                    "BotLocales": [bot_locale],
                    "BotTags": [{"Key": "Project", "Value": "Semi-Social"}, {"Key": "Ticket", "Value": "PRO-19"}],
                },
            },
            "FacultadBotVersion": {
                "Type": "AWS::Lex::BotVersion",
                "Properties": {
                    "BotId": {"Ref": "FacultadBot"},
                    "Description": f"Versión publicada desde faq.yaml (contenido {content_hash})",
                    "BotVersionLocaleSpecification": [
                        {"LocaleId": locale, "BotVersionLocaleDetails": {"SourceBotVersion": "DRAFT"}}
                    ],
                },
            },
            "FacultadBotAlias": {
                "Type": "AWS::Lex::BotAlias",
                "Properties": {
                    "BotId": {"Ref": "FacultadBot"},
                    "BotAliasName": bot["aliasName"],
                    "Description": "Alias consumido por los backends Node.js y Python",
                    "BotVersion": {"Fn::GetAtt": ["FacultadBotVersion", "BotVersion"]},
                    "BotAliasLocaleSettings": [{"LocaleId": locale, "BotAliasLocaleSetting": {"Enabled": True}}],
                },
            },
        },
        "Outputs": {
            "LexBotId": {"Description": "Valor para LEX_BOT_ID", "Value": {"Ref": "FacultadBot"}},
            "LexBotAliasId": {
                "Description": "Valor para LEX_BOT_ALIAS_ID",
                "Value": {"Fn::GetAtt": ["FacultadBotAlias", "BotAliasId"]},
            },
            "LexLocaleId": {"Description": "Valor para LEX_LOCALE_ID", "Value": locale},
            "LexBotAliasArn": {
                "Description": "Recurso para lex:RecognizeText (infra/iam/lex-runtime-policy.json)",
                "Value": {"Fn::GetAtt": ["FacultadBotAlias", "Arn"]},
            },
        },
    }


def render(template: dict[str, Any], *, example: bool) -> str:
    header = ["# GENERADO por infra/lex/build_template.py desde infra/lex/faq.yaml. No editar a mano."]
    if example:
        header += [
            "# ⚠️ PLANTILLA DE EJEMPLO generada con --include-drafts: contiene marcadores [EJEMPLO]",
            "# y NINGÚN dato real de la Facultad. NO DESPLEGAR.",
        ]
    body = yaml.safe_dump(template, sort_keys=False, allow_unicode=True, width=100)
    return "\n".join(header) + "\n" + body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("faq", type=Path)
    parser.add_argument("-o", "--output", type=Path, help="archivo de salida (por defecto, stdout)")
    parser.add_argument("--include-drafts", action="store_true", help="incluir entradas draft (solo ejemplo)")
    parser.add_argument("--check", action="store_true", help="solo validar faq.yaml")
    args = parser.parse_args(argv)

    data = load_faq(args.faq)
    if args.check:
        errors = validate_faq(data, include_drafts=args.include_drafts)
        print("faq.yaml válido" if not errors else "faq.yaml inválido:\n- " + "\n- ".join(errors))
        return 0 if not errors else 1
    try:
        text = render(build_template(data, include_drafts=args.include_drafts), example=args.include_drafts)
    except FaqError as exc:
        print(exc, file=sys.stderr)
        return 1
    if args.output:
        args.output.write_text(text, encoding="utf-8", newline="\n")
        print(f"Plantilla escrita en {args.output}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
