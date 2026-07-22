# SPDX-License-Identifier: GPL-3.0-only
"""Exact-codename resolution for shared-image hardware variants."""

from asteroid_docking_bay.variants import (codename_from_bootloader,
                                           exact_codename, image_of)


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


# ── bootloader-named codenames (primary detector) ───────────────────────────
#
# Values below are real strings read off the rig on 2026-07-18, not invented:
# rover and rubyfish run the SAME image, report the SAME MACHINE (rubyfish) and
# the SAME 454x454 panel, and differ only by LTE — which no detector can see.
# The bootloader string is the only thing that tells them apart.

def test_bootloader_names_the_variant_where_nothing_else_can():
    rover = exact_codename("rubyfish", {"resolution": "454x454",
                                        "bootloader": "rover-03.02.39.03.16"})
    ruby = exact_codename("rubyfish", {"resolution": "454x454",
                                       "bootloader": "rubyfish-03.02.04.02.16"})
    assert rover == "rover", rover
    assert ruby == "rubyfish", ruby
    assert rover != ruby, "resolution is identical, so only the bootloader can split these"


def test_bootloader_beats_a_conflicting_resolution():
    """The bootloader comes from firmware and cannot be masked by a shared
    image; resolution is a fallback heuristic. If they disagree, firmware wins."""
    got = exact_codename("skipjack", {"resolution": "400x400",   # says tunny
                                      "bootloader": "skipjack-1.0"})
    assert got == "skipjack", got


def test_bootloader_match_is_case_insensitive_and_needs_no_separator():
    """lenok's string is 'LENOKZ22b' — no dash, different case. Splitting on
    '-' or comparing case-sensitively would both miss it."""
    assert codename_from_bootloader("LENOKZ22b", ["lenok"]) == "lenok"
    assert codename_from_bootloader("rover-03.02.39.03.16",
                                    ["rover", "rubyfish"]) == "rover"


def test_longest_bootloader_match_wins():
    """'catfish_ext-…' starts with 'catfish' too; a first-match rule would
    silently mislabel the 1024MB variant as the 512MB one."""
    got = codename_from_bootloader("catfish_ext-2.1",
                                   ["catfish", "catfish_ext", "catshark"])
    assert got == "catfish_ext", got


def test_unknown_bootloader_falls_back_to_resolution():
    """A watch whose bootloader names nothing we know must not be guessed at —
    it falls through to the resolution heuristic, then to the family base."""
    assert exact_codename("skipjack", {"resolution": "400x400",
                                       "bootloader": "someothervendor-9"}) == "tunny"
    assert exact_codename("skipjack", {"bootloader": "someothervendor-9"}) == "skipjack"


def test_absent_bootloader_changes_nothing():
    """Watches that never report the field keep the previous behaviour."""
    assert exact_codename("skipjack", {"resolution": "400x400"}) == "tunny"
    assert exact_codename("skipjack", {"resolution": "360x360"}) == "skipjack"
