"""Native HA translation loading and identity contracts; synthetic devices only."""
import ast
import json
from pathlib import Path
from string import Formatter
from unittest.mock import patch

import pytest
from homeassistant import loader
from homeassistant.bootstrap import async_load_base_functionality
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_translations

from custom_components.desloc.api import Device

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "desloc"
LOCALES = {
    "en", "ar", "bn", "cs", "de", "es", "fa", "fr", "he", "hi", "id", "it",
    "ja", "ko", "nl", "pl", "pt", "ru", "th", "tr", "uk", "vi", "zh-Hans", "zh-Hant",
}


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, f"Duplicate translation key: {key}"
        result[key] = value
    return result


def read_pack(locale):
    return json.loads((COMPONENT / "translations" / f"{locale}.json").read_text(),
                      object_pairs_hook=no_duplicates)


def flatten(value, prefix=""):
    result = {}
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            result.update(flatten(item, path))
        else:
            assert isinstance(item, str) and item.strip(), path
            result[path] = item
    return result


def fields(message):
    return {name for _, name, _, _ in Formatter().parse(message) if name is not None}


def test_complete_bundled_packs_and_placeholders():
    """A missing pack/key or silent English copy cannot claim language support."""
    assert {path.stem for path in (COMPONENT / "translations").glob("*.json")} == LOCALES
    english = flatten(read_pack("en"))
    # strings.json remains an authoring mirror; custom HA actually loads en.json.
    assert flatten(json.loads((COMPONENT / "strings.json").read_text())) == english
    for locale in LOCALES:
        messages = flatten(read_pack(locale))
        assert messages.keys() == english.keys(), locale
        for key, text in messages.items():
            assert fields(text) == fields(english[key]), (locale, key)
            assert "[%key:" not in text, (locale, key)  # Core-only references do not work here.
            assert not any(ord(char) in range(0x202A, 0x202F) for char in text), (locale, key)
            if locale != "en" and key != "title":
                assert text != english[key], (locale, key)
        for key in ("config.step.account.description", "config.step.session.description"):
            assert "C100 Plus" in messages[key] and "D110 Plus" in messages[key]
        for key in ("options.step.init.description", "options.error.invalid_pin_user"):
            assert "6–8" in messages[key], (locale, key)
        assert "1–24" in messages["options.error.invalid_pin_user"], locale


def test_runtime_translation_keys_have_bundled_messages():
    english = read_pack("en")
    for name in ("coordinator.py", "__init__.py", "sensor.py"):
        tree = ast.parse((COMPONENT / name).read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            keywords = {item.arg: item.value for item in node.keywords}
            if "translation_key" not in keywords:
                continue
            key = ast.literal_eval(keywords["translation_key"])
            if name == "sensor.py":
                assert key in english["entity"]["sensor"]
            else:
                assert key in english["exceptions"]
                assert isinstance(keywords["translation_domain"], ast.Name)
                assert keywords["translation_domain"].id == "DOMAIN"


@pytest.fixture
async def localized_hass(hass):
    Path(hass.config.path("custom_components")).symlink_to(ROOT / "custom_components", target_is_directory=True)
    loader.async_setup(hass)
    assert await async_load_base_functionality(hass)
    return hass


@pytest.mark.parametrize("locale", sorted(LOCALES))
async def test_home_assistant_loads_every_translation(localized_hass, locale):
    """Exercise HA's actual custom-component loader, not a bespoke dictionary."""
    expected = read_pack(locale)
    for category in ("config", "options", "entity", "exceptions"):
        actual = await async_get_translations(localized_hass, locale, category, {"desloc"})
        for key, value in flatten(expected[category]).items():
            assert actual[f"component.desloc.{category}.{key}"] == value


async def test_unsupported_language_falls_back_to_english(localized_hass):
    actual = await async_get_translations(localized_hass, "xx", "options", {"desloc"})
    assert actual["component.desloc.options.abort.pin_creation_uncertain"] == (
        read_pack("en")["options"]["abort"]["pin_creation_uncertain"])


async def test_localized_names_preserve_registry_identity_and_user_names(localized_hass, row):
    hass = localized_hass
    with patch("custom_components.desloc.config_flow.async_get_clientsession"), patch(
        "custom_components.desloc.async_get_clientsession"
    ), patch("custom_components.desloc.api.DeslocClient.async_devices", return_value=[Device.from_json(row)]):
        flow = await hass.config_entries.flow.async_init("desloc", context={"source": "user"})
        await hass.config_entries.flow.async_configure(flow["flow_id"], {"next_step_id": "session"})
        result = await hass.config_entries.flow.async_configure(flow["flow_id"], {
            "token": "test-secret", "app_device_id": "test-phone"})
        assert result["reason"] == "devices_added"
        await hass.async_block_till_done()
        entry = hass.config_entries.async_entries("desloc")[0]
        registry = er.async_get(hass)
        entities = er.async_entries_for_config_entry(registry, entry.entry_id)
        identity = {entity.unique_id: entity.entity_id for entity in entities}
        battery = identity["001122334455_battery"]
        rssi = identity["001122334455_rssi"]
        assert registry.async_get(battery).original_name == "Battery"
        registry.async_update_entity(battery, name="My battery title")
        hass.config.language = "es"
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert {entity.unique_id: entity.entity_id for entity in er.async_entries_for_config_entry(
            registry, entry.entry_id)} == identity
        assert registry.async_get(battery).name == "My battery title"
        assert registry.async_get(battery).original_name == "Batería"
        assert registry.async_get(rssi).original_name == "Señal Wi-Fi"
        assert hass.states.get(battery).attributes["friendly_name"] == "My battery title"
        assert await hass.config_entries.async_unload(entry.entry_id)
