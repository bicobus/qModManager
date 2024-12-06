# -*- coding: utf-8 -*-
# Licensed under the EUPL v1.2
# © 2021 bicobus <bicobus@keemail.me>
# type: ignore
import pytest

from qmm.gamestruct import liliththrone
from tests.fixtures import (
    colours,
    combatmoves,
    dialogue,
    encounters,
    items,
    items_nonvalid,
    maps,
    maps_nonvalid,
    outfits,
    races,
    races_nonvalid,
    setbonuses,
    sex,
    statuseffects,
    txt,
    characters,
)


def test_validator_items(items):
    assert liliththrone.ItemsValidator(items)


def test_validator_items_nonvalid(items_nonvalid):
    with pytest.raises(ValueError):
        liliththrone.ItemsValidator(items_nonvalid)


def test_validator_races(races):
    assert liliththrone.RaceValidator(races)


def test_validator_races_nonvalid(races_nonvalid):
    with pytest.raises(ValueError):
        liliththrone.RaceValidator(races_nonvalid)


def test_validator_outfits(outfits):
    assert liliththrone.OutfitsValidator(outfits)


def test_validator_colours(colours):
    assert liliththrone.ColoursValidator(colours)


def test_validator_setbonuses(setbonuses):
    assert liliththrone.SetBonusesValidator(setbonuses)


def test_validator_statuseffects(statuseffects):
    assert liliththrone.StatusEffectsValidator(statuseffects)


def test_validator_combatmoves(combatmoves):
    assert liliththrone.CombatMoveValidator(combatmoves)


def test_validator_dialogue(dialogue):
    assert liliththrone.DialogueValidator(dialogue)


def test_validator_encounters(encounters):
    assert liliththrone.EncountersValidator(encounters)


def test_validator_sex(sex):
    assert liliththrone.SexValidator(sex)


def test_validator_maps(maps):
    assert liliththrone.MapsValidator(maps)


def test_validator_maps_nonvalid(maps_nonvalid):
    with pytest.raises(ValueError):
        liliththrone.MapsValidator(maps_nonvalid)


def test_validator_txt(txt):
    assert liliththrone.TxtValidator(txt)


def test_validator_characters(characters):
    assert liliththrone.CharactersValidator(characters)
