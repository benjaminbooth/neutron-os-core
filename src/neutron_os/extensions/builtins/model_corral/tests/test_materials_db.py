"""Tests for the verified nuclear material compositions database."""

from __future__ import annotations

import pytest


class TestMaterialDatabase:
    def test_get_known_material(self):
        from neutron_os.extensions.builtins.model_corral.materials_db import get_material

        mat = get_material("UZrH-20")
        assert mat is not None
        assert mat.density == 6.0
        assert mat.category == "fuel"
        assert len(mat.isotopes) > 0

    def test_get_unknown_returns_none(self):
        from neutron_os.extensions.builtins.model_corral.materials_db import get_material

        assert get_material("nonexistent-material") is None

    def test_list_all_materials(self):
        from neutron_os.extensions.builtins.model_corral.materials_db import list_materials

        materials = list_materials()
        assert len(materials) >= 10
        names = {m.name for m in materials}
        assert "UZrH-20" in names
        assert "SS304" in names
        assert "H2O" in names
        assert "B4C" in names

    def test_list_by_category(self):
        from neutron_os.extensions.builtins.model_corral.materials_db import list_materials

        fuels = list_materials(category="fuel")
        assert len(fuels) >= 2
        assert all(m.category == "fuel" for m in fuels)

        structural = list_materials(category="structural")
        assert len(structural) >= 1

    def test_search_materials(self):
        from neutron_os.extensions.builtins.model_corral.materials_db import search_materials

        results = search_materials("uranium")
        assert len(results) >= 1

        results = search_materials("steel")
        assert len(results) >= 1
        assert results[0].name == "SS304"

    def test_material_names(self):
        from neutron_os.extensions.builtins.model_corral.materials_db import material_names

        names = material_names()
        assert isinstance(names, list)
        assert len(names) >= 10
        assert names == sorted(names)  # alphabetically sorted


class TestMCNPCardGeneration:
    def test_uzrh_mcnp_card(self):
        from neutron_os.extensions.builtins.model_corral.materials_db import get_material

        mat = get_material("UZrH-20")
        card = mat.mcnp_cards(mat_number=1)

        assert "m1" in card
        assert "92235.80c" in card  # U-235
        assert "92238.80c" in card  # U-238
        assert "1001.80c" in card  # H-1
        assert "mt1" in card  # S(alpha,beta)
        assert "zr-h.40t" in card

    def test_water_mcnp_card(self):
        from neutron_os.extensions.builtins.model_corral.materials_db import get_material

        mat = get_material("H2O")
        card = mat.mcnp_cards(mat_number=3)

        assert "m3" in card
        assert "1001.80c" in card
        assert "8016.80c" in card
        assert "mt3" in card
        assert "lwtr.20t" in card

    def test_ss304_weight_fractions(self):
        from neutron_os.extensions.builtins.model_corral.materials_db import get_material

        mat = get_material("SS304")
        card = mat.mcnp_cards(mat_number=5)

        assert "m5" in card
        assert mat.fraction_type == "weight"
        # Weight fractions should have negative sign in MCNP
        assert "-" in card

    def test_no_sab_for_uo2(self):
        from neutron_os.extensions.builtins.model_corral.materials_db import get_material

        mat = get_material("UO2-3.1")
        card = mat.mcnp_cards(mat_number=2)

        assert "mt2" not in card  # UO2 doesn't need S(a,b)

    def test_b4c_absorber(self):
        from neutron_os.extensions.builtins.model_corral.materials_db import get_material

        mat = get_material("B4C")
        card = mat.mcnp_cards(mat_number=10)

        assert "5010.80c" in card  # B-10 (absorber)
        assert "5011.80c" in card  # B-11

    def test_card_includes_provenance(self):
        from neutron_os.extensions.builtins.model_corral.materials_db import get_material

        mat = get_material("MSRE-salt")
        card = mat.mcnp_cards(mat_number=1)

        assert "ORNL-4541" in card  # source reference in comment

    def test_all_materials_generate_valid_cards(self):
        from neutron_os.extensions.builtins.model_corral.materials_db import list_materials

        for mat in list_materials():
            card = mat.mcnp_cards(mat_number=1)
            assert "m1" in card, f"{mat.name} didn't generate a valid card"
            assert len(card.splitlines()) >= 3


class TestMPACTCardGeneration:
    def test_mpact_material_card(self):
        from neutron_os.extensions.builtins.model_corral.materials_db import get_material

        mat = get_material("UZrH-20")
        card = mat.mpact_card()

        assert "mat" in card
        assert "UZrH-20" in card
        assert "92235.80c" in card


class TestMaterialProperties:
    def test_msre_salt_composition(self):
        """MSRE salt should have LiF-BeF2-ZrF4-UF4 components."""
        from neutron_os.extensions.builtins.model_corral.materials_db import get_material

        mat = get_material("MSRE-salt")
        zaids = {iso.zaid.split(".")[0] for iso in mat.isotopes}

        assert "3007" in zaids  # Li-7
        assert "4009" in zaids  # Be-9
        assert "9019" in zaids  # F-19
        assert "92235" in zaids  # U-235

    def test_materials_are_frozen(self):
        from neutron_os.extensions.builtins.model_corral.materials_db import get_material

        mat = get_material("H2O")
        with pytest.raises(AttributeError):
            mat.density = 999.0  # frozen dataclass

    def test_to_dict_serializable(self):
        from neutron_os.extensions.builtins.model_corral.materials_db import get_material

        mat = get_material("UZrH-20")
        d = mat.to_dict()
        assert d["name"] == "UZrH-20"
        assert d["density"] == 6.0
        assert d["num_isotopes"] > 0
