# SPDX-License-Identifier: GPL-3.0-only
"""Exact-codename resolution for shared-image hardware variants."""

from asteroid_docking_bay.variants import exact_codename, image_of


def test_unique_image_is_passed_through():
    # A watch with its own image (not in the table) keeps its name — including
    # a brand-new port that a-d-b has never heard of.
    assert exact_codename("narwhal", {"resolution": "360x360"}) == "narwhal"
    assert exact_codename("sol", {}) == "sol"


def test_tunny_detected_by_resolution():
    assert exact_codename("skipjack", {"resolution": "400x400"}) == "tunny"
    assert exact_codename("skipjack", {"resolution": "360x360"}) == "skipjack"


def test_belugaxl_detected_orientation_agnostic():
    assert exact_codename("beluga", {"resolution": "402x476"}) == "belugaxl"
    assert exact_codename("beluga", {"resolution": "476x402"}) == "belugaxl"
    assert exact_codename("beluga", {"resolution": "320x360"}) == "beluga"


def test_undetectable_family_falls_back_to_base():
    # catfish/catshark/catfish_ext differ by gps/lte/ram — none detectable yet.
    assert exact_codename("catfish", {"resolution": "400x400"}) == "catfish"
    assert exact_codename("catfish", {}) == "catfish"
    assert exact_codename("rubyfish", {"resolution": "454x454"}) == "rubyfish"


def test_unprobed_shared_image_falls_back_to_base():
    assert exact_codename("skipjack", {}) == "skipjack"
    assert exact_codename("beluga", {}) == "beluga"


def test_none_machine_stays_none():
    assert exact_codename(None, {}) is None


def test_image_of_reverse_lookup():
    assert image_of("tunny") == "skipjack"
    assert image_of("belugaxl") == "beluga"
    assert image_of("orca") == "beluga"
    assert image_of("narwhal") is None
