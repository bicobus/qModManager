# -*- coding: utf-8 -*-
# Licensed under the EUPL v1.2
# © 2021 bicobus <bicobus@keemail.me>
import pytest


@pytest.fixture(
    params=[
        "innoxia/items/tattoos/heartWomb/heart_womb.svg",
        "innoxia/items/tattoos/heartWomb/heart_womb.xml",
        "innoxia/items/clothing/rentalMommy/special%char.svg",
        "innoxia/items/clothing/rentalMommy/with.dots.svg",
        "innoxia/items/clothing/rentalMommy/text_flames_50.svg",
        "innoxia/items/clothing/rentalMommy/rental_mommy.xml",
        "innoxia/items/clothing/template/socks.svg",
        "innoxia/items/clothing/template/socks_hand.svg",
        "innoxia/items/clothing/template/socks.xml",
        "innoxia/items/clothing/gothicDress/gothic_dress.svg",
        "innoxia/items/clothing/gothicDress/gothic_dress.xml",
        "innoxia/items/items/race/background_bottom.svg",
        "innoxia/items/items/race/hyena_bone_crunchers.xml",
        "innoxia/items/patterns/file.xml",
        "namespace/items/weapons/weapon_name/file.xml",
        "namespace/items/weapons/weapon_name/file.svg",
        "namespace/items/items/file.xml",
        "namespace/items/weapons/file.xml",
        "namespace/items/weapons/",
        "namespace/items/patterns/",
        "namespace/items/clothing/testclothing/",
        "namespace/items/clothing/",
        "namespace/items/",
    ]
)
def items(request):
    return request.param


@pytest.fixture(
    params=[
        "innoxia/items/weapons/example_location.txt",
        "innoxia/items/patterns/pattern_modding.txt",
        "innoxia/items/tattoos/heartWomb/heart_womb.png",
    ]
)
def items_nonvalid(request):
    return request.param


@pytest.fixture(
    params=(
        "innoxia/race/hyena/coveringTypes/fur.xml",
        "innoxia/race/hyena/bodyParts/breast.xml",
        "innoxia/race/hyena/subspecies/striped.xml",
        "innoxia/race/hyena/subspecies/background_striped.svg",
        "innoxia/race/hyena/racialBody.xml",
        "innoxia/race/hyena/race.xml",
        "namespace/race/",
        "namespace/race/hyena/",
        "namespace/race/hyena/coveringTypes/",
        "namespace/race/hyena/bodyParts/",
        "namespace/race/hyena/subspecies/",
    )
)
def races(request):
    return request.param


@pytest.fixture(
    params=(
        "innoxia/race/hyena/coveringTypes/fur.svg",
        "innoxia/race/hyena/unused_bodyParts/antenna.xml",
        "namespace/race/racename/badfile.xml",
        "namespace/race/file.xml",
    )
)
def races_nonvalid(request):
    return request.param


@pytest.fixture(
    params=[
        "innoxia/outfits/casualDates/dress_toys.xml",
        "namespace/outfits/",
        "namespace/outfits/node/",
    ]
)
def outfits(request):
    return request.param


@pytest.fixture(
    params=[
        "innoxia/colours/fuchsia.xml",
        "namespace/colours/",
    ]
)
def colours(request):
    return request.param


@pytest.fixture(
    params=[
        "innoxia/setBonuses/template.xml",
        "namespace/setBonuses/",
    ]
)
def setbonuses(request):
    return request.param


@pytest.fixture(
    params=[
        "innoxia/statusEffects/set_template.svg",
        "innoxia/statusEffects/set_template.xml",
        "namespace/statusEffects/"
    ]
)
def statuseffects(request):
    return request.param


@pytest.fixture(
    params=[
        "innoxia/combatMove/hyena_bone_crush.svg",
        "innoxia/combatMove/hyena_bone_crush.xml",
        "namespace/combatMove/",
    ]
)
def combatmoves(request):
    return request.param


@pytest.fixture(
    params=[
        "namespace/dialogue/dominion/mansion_dungeon.xml",
        "namespace/dialogue/node/node/node/file.xml",
        "namespace/dialogue/flags.xml",
        "namespace/dialogue/",
        "namespace/dialogue/dominion/",
    ]
)
def dialogue(request):
    return request.param


@pytest.fixture(
    params=[
        "AceXp/encounters/dominion/AngelOffice.xml",
        "AceXp/encounters/submission/Elizabeth.xml",
        "namespace/encounters/",
        "namespace/encounters/node/",
    ]
)
def encounters(request):
    return request.param


@pytest.fixture(params=[
    "namespace/sex/",
    "namespace/sex/managers/",
    "namespace/sex/actions/",
    "namespace/sex/managers/some_file.xml",
    "namespace/sex/actions/some_file.xml",
])
def sex(request):
    return request.param


@pytest.fixture(
    params=[
        "AceXp/maps/dominion/mansion/dungeon/map.png",
        "AceXp/maps/dominion/mansion/dungeon/worldType.xml",
        "AceXp/maps/dominion/mansion/dungeon/placeTypes/stairs.xml",
        "AceXp/maps/dominion/mansion/dungeon/placeTypes/stairs.svg",
        "AceXp/maps/dominion/mansion/dungeon/",
        "AceXp/maps/dominion/mansion/dungeon/placeTypes/",
        "AceXp/maps/",
    ]
)
def maps(request):
    return request.param


@pytest.fixture(
    params=[
        "namespace/maps/node1/node2/node3/placeTypes/map.png",
        "namespace/maps/node1/node2/node3/placeTypes/worldType.xml",
    ]
)
def maps_nonvalid(request):
    return request.param


@pytest.fixture(
    params=[
        "AceXp/txt/submission/elizabeth.xml",
        "AceXp/txt/dominion/angel_office.xml",
        "AceXp/txt/submission/",
        "AceXp/txt/",
        "namespace/txt/file.xml",
    ]
)
def txt(request):
    return request.param
