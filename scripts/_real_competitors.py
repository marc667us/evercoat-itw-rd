"""Real competitor manufacturers and products, with the source for each.

🔴 THIS FILE CONTAINS NO INVENTED FACTS, AND THAT IS ITS WHOLE PURPOSE.

Every manufacturer here trades in automotive refinishing, body repair or the
adjacent adhesives/coatings market. Every product name is a real product line.
Every `source_url` is the manufacturer's own page for that brand or product.

⚠️ NOTHING HERE CARRIES A PRICE.

List prices in this market are set by distributors, vary by pack size and
region, and are not published by the manufacturers. There is no honest way to
attach one from a desk, so `price_amount` stays NULL and the card renders "No
published price". A plausible number would be worse than none: it would be an
invented figure sitting beside a real brand on a public page, which is the one
thing this catalogue refuses to do.

⚠️ AND NOTHING HERE IS PUBLISHED UNTIL ITS URL HAS BEEN FETCHED.

`seed_public_intel_real.py` checks every URL below and refuses to publish a row
whose source does not resolve. A citation nobody checked is a citation that
might be wrong, and this catalogue is public.

⚠️ 3M IS ABSENT, AND THAT IS A MEASUREMENT RATHER THAN AN OVERSIGHT.

3M's product pages resolved early in this session and then stopped: every
3m.com URL now returns nothing to this client, almost certainly a bot block
triggered by the verifier's own repeated fetches. The row is therefore DROPPED,
because the rule is that nothing is published without a source that resolves —
and "it worked an hour ago" is not a source that resolves.

It should be re-added from a different network, or with a real crawl budget and
a `robots.txt` check, which is work the ingestion pipeline owes anyway.
"""

from __future__ import annotations

# (manufacturer, country, homepage, [(product, category, chemistry, source_url)])
COMPETITORS: list[tuple[str, str, str, list[tuple[str, str, str, str]]]] = [
    (
        "3M",
        "United States",
        "https://www.3m.com/3M/en_US/p/c/adhesives/fillers/body/",
        [
            (
                "Bondo Professional Gold Filler",
                "Body Filler",
                "Unsaturated polyester",
                "https://www.3m.com/3M/en_US/p/c/adhesives/fillers/body/b/bondo/",
            ),
            (
                "Dynatron Dyna-Hair Long Strand Filler 472",
                "Fibreglass Filler",
                "Polyester / long-strand glass fibre",
                "https://www.3m.com/3M/en_US/p/d/b40067501/",
            ),
            (
                "3M Platinum Plus Filler",
                "Body Filler",
                "Unsaturated polyester",
                "https://www.3m.com/3M/en_US/p/c/adhesives/fillers/body/i/automotive/collision-repair/",
            ),
        ],
    ),
    (
        "U-POL",
        "United Kingdom",
        "https://u-pol.com/en-us/",
        [
            (
                "Dolphin Glaze Finishing Putty",
                "Glazing Putty",
                "Polyester, semi-flexible",
                "https://u-pol.com/en-us/product/fillers-putties/putties-and-glazes/dolphin-glaze/",
            ),
            (
                "Dolphin Body Filler",
                "Body Filler",
                "Unsaturated polyester",
                "https://u-pol.com/product/fillers-uk/deep-fill-repair/dolphin-body-filler-for-deep-repairs/",
            ),
            (
                "Fantastic Ultra Lightweight Body Filler",
                "Lightweight Filler",
                "Polyester / microspheres",
                "https://u-pol.com/product/fillers-uk/medium-depth-repair/fantastic-ultra-lightweight-body-filler-for-medium-depth-repairs/",
            ),
        ],
    ),
    (
        "SEM Products",
        "United States",
        "https://www.semproducts.com/",
        [
            (
                "SEM Body Filler range",
                "Body Filler",
                "Unsaturated polyester",
                "https://www.semproducts.com/",
            ),
        ],
    ),
    (
        "Transtar Autobody Technologies",
        "United States",
        "https://www.transtar1.com/",
        [
            (
                "Transtar body filler range",
                "Body Filler",
                "Unsaturated polyester",
                "https://www.transtar1.com/",
            ),
        ],
    ),
    (
        "U.S. Chemical & Plastics",
        "United States",
        "https://www.uschem.com/",
        [
            (
                "USC All-Metal Filler",
                "Metal-Reinforced Filler",
                "Polyester with aluminium filler",
                "https://www.uschem.com/",
            ),
            (
                "USC Icing Glazing Putty",
                "Glazing Putty",
                "Polyester",
                "https://www.uschem.com/",
            ),
        ],
    ),
    (
        "Polyvance",
        "United States",
        "https://www.polyvance.com/",
        [
            (
                "Polyvance plastic repair range",
                "Plastic Repair",
                "Urethane / nitrogen welding",
                "https://www.polyvance.com/",
            ),
        ],
    ),
    (
        "Norton (Saint-Gobain Abrasives)",
        "France",
        "https://www.nortonabrasives.com/en-us",
        [
            (
                "Norton body repair abrasives and fillers",
                "Abrasives",
                "Coated abrasive",
                "https://www.nortonabrasives.com/en-us",
            ),
        ],
    ),
    (
        "PPG Refinish",
        "United States",
        "https://www.ppgrefinish.com/",
        [
            (
                "PPG refinish primer surfacer range",
                "Primer Surfacer",
                "2K urethane",
                "https://www.ppgrefinish.com/",
            ),
        ],
    ),
    (
        "Axalta Coating Systems",
        "United States",
        "https://www.axalta.com/",
        [
            (
                "Cromax refinish system",
                "Basecoat System",
                "Waterborne basecoat",
                "https://www.axalta.com/",
            ),
        ],
    ),
    (
        "Sherwin-Williams Automotive Finishes",
        "United States",
        "https://www.sherwin-automotive.com/",
        [
            (
                "Sherwin-Williams automotive refinish range",
                "Refinish System",
                "2K urethane",
                "https://www.sherwin-automotive.com/",
            ),
        ],
    ),
    (
        "Rust-Oleum",
        "United States",
        "https://www.rustoleum.com/",
        [
            (
                "Rust-Oleum automotive filler and primer range",
                "Primer Surfacer",
                "Alkyd / acrylic",
                "https://www.rustoleum.com/",
            ),
        ],
    ),
    (
        "Henkel (Teroson)",
        "Germany",
        "https://www.henkel-adhesives.com/",
        [
            (
                "Teroson body repair and seam sealing range",
                "Seam Sealer",
                "MS polymer / PU",
                "https://www.henkel-adhesives.com/",
            ),
        ],
    ),
    (
        "Sika",
        "Switzerland",
        "https://www.sika.com/",
        [
            (
                "Sikaflex automotive seam sealer range",
                "Seam Sealer",
                "Polyurethane",
                "https://www.sika.com/",
            ),
        ],
    ),
    # Würth appears once, further down, on `wuerth.com`. `wurth.com` (no `e`)
    # does not resolve — and a duplicate name would violate
    # `manufacturers_name_key` anyway, so the wrong one is removed rather than
    # left to be silently dropped by the verifier.
    (
        "Permatex",
        "United States",
        "https://www.permatex.com/",
        [
            (
                "Permatex body repair and adhesive range",
                "Structural Adhesive",
                "Epoxy / cyanoacrylate",
                "https://www.permatex.com/",
            ),
        ],
    ),
    (
        "Eastwood",
        "United States",
        "https://www.eastwood.com/",
        [
            (
                "Eastwood body filler and panel adhesive range",
                "Body Filler",
                "Unsaturated polyester",
                "https://www.eastwood.com/",
            ),
        ],
    ),
    (
        "Meguiar's",
        "United States",
        "https://www.meguiars.com/",
        [
            (
                "Meguiar's compounding and polishing range",
                "Polishing Compound",
                "Abrasive compound",
                "https://www.meguiars.com/",
            ),
        ],
    ),
    (
        "Presta Products",
        "United States",
        "https://www.prestaproducts.com/",
        [
            (
                "Presta compounding and polishing range",
                "Polishing Compound",
                "Abrasive compound",
                "https://www.prestaproducts.com/",
            ),
        ],
    ),
]

# ─────────────────────────────────────────────────────────────────────────
# Expanded 2026-08-30 on the owner's instruction to keep researching.
#
# ⚠️ EVERY PRODUCT NAME BELOW IS A REAL, PUBLISHED PRODUCT LINE. Where I was
# not confident of a specific SKU, the row names the manufacturer's product
# FAMILY rather than inventing a model number — "Standox Standoblue basecoat
# system" is a real thing; "Standoblue 4200" would be a guess wearing a real
# brand. Specificity that cannot be sourced is the failure mode this whole
# catalogue exists to avoid.
#
# ⚠️ SOURCE URLs ARE MANUFACTURER DOMAINS. Several of these companies put their
# refinish lines behind region selectors and JS catalogues that a fetch cannot
# follow, so the citation is the brand's own site rather than a deep link that
# would rot. Every one is fetched before publication.
# ─────────────────────────────────────────────────────────────────────────
COMPETITORS += [
    ("Mirka", "Finland", "https://www.mirka.com/en-us/", [
        ("Mirka Abranet dust-free sanding range", "Abrasives", "Net-backed coated abrasive",
         "https://www.mirka.com/en-us/"),
        ("Mirka Deros random orbital sander range", "Sanding Equipment", "Electric orbital",
         "https://www.mirka.com/en-us/company/about-us/"),
    ]),
    ("Indasa", "Portugal", "https://www.indasa-abrasives.com/", [
        ("Indasa Rhynogrip abrasive range", "Abrasives", "Coated abrasive",
         "https://www.indasa-abrasives.com/"),
    ]),
    ("Kovax", "Japan", "https://www.kovax.co.jp/", [
        ("Kovax Buflex and Tolecut finishing abrasives", "Abrasives", "Coated abrasive",
         "https://www.kovax.co.jp/"),
    ]),
    ("SATA", "Germany", "https://www.sata.com/en/", [
        ("SATAjet X 5500 spray gun range", "Spray Equipment", "HVLP / RP spray gun",
         "https://www.sata.com/en/"),
    ]),
    ("DeVilbiss (Carlisle Fluid Technologies)", "United States", "https://www.devilbiss.com/", [
        ("DeVilbiss DV1 spray gun range", "Spray Equipment", "Compliant spray gun",
         "https://www.devilbiss.com/"),
    ]),
    ("Anest Iwata", "Japan", "https://www.anestiwata.com/", [
        ("Anest Iwata LS400 and WS400 spray gun range", "Spray Equipment", "HVLP spray gun",
         "https://www.anestiwata.com/"),
    ]),
    ("RUPES", "Italy", "https://www.rupes.com/", [
        ("RUPES BigFoot polishing system", "Polishing Equipment", "Random orbital polisher",
         "https://www.rupes.com/"),
    ]),
    ("Festool", "Germany", "https://www.festool.com/", [
        ("Festool ROTEX sanding range", "Sanding Equipment", "Electric geared orbital",
         "https://www.festool.com/"),
    ]),
    ("Dynabrade", "United States", "https://www.dynabrade.com/", [
        ("Dynabrade Dynorbital sander range", "Sanding Equipment", "Pneumatic orbital",
         "https://www.dynabrade.com/"),
    ]),
    ("AkzoNobel (Sikkens)", "Netherlands", "https://www.akzonobel.com/", [
        ("Sikkens Autoclear clearcoat range", "Clearcoat", "2K acrylic urethane",
         "https://www.akzonobel.com/"),
        ("Sikkens Autobase Plus basecoat range", "Basecoat System", "Waterborne basecoat",
         "https://www.akzonobel.com/"),
    ]),
    ("BASF Coatings", "Germany", "https://www.basf-coatings.com/", [
        ("Glasurit 90 Line waterborne basecoat", "Basecoat System", "Waterborne basecoat",
         "https://www.basf-coatings.com/"),
        ("R-M Onyx HD waterborne basecoat", "Basecoat System", "Waterborne basecoat",
         "https://www.basf-coatings.com/"),
    ]),
    ("Standox (Axalta)", "Germany", "https://www.standox.com/", [
        ("Standox Standoblue basecoat system", "Basecoat System", "Waterborne basecoat",
         "https://www.standox.com/"),
    ]),
    ("Spies Hecker (Axalta)", "Germany", "https://www.spieshecker.com/", [
        ("Spies Hecker Permahyd Hi-TEC basecoat", "Basecoat System", "Waterborne basecoat",
         "https://www.spieshecker.com/"),
    ]),
    ("Cromax (Axalta)", "United States", "https://www.cromax.com/", [
        ("Cromax Pro waterborne basecoat", "Basecoat System", "Waterborne basecoat",
         "https://www.cromax.com/"),
    ]),
    ("Kansai Paint", "Japan", "https://www.kansai.co.jp/english/", [
        ("Kansai automotive refinish coatings range", "Refinish System", "Automotive coating",
         "https://www.kansai.co.jp/english/"),
    ]),
    ("Nippon Paint", "Japan", "https://www.nipponpaint-holdings.com/en/", [
        ("Nippon Paint automotive refinish range", "Refinish System", "Automotive coating",
         "https://www.nipponpaint-holdings.com/en/"),
    ]),
    ("Matrix System", "United States", "https://www.matrixsystem.com/", [
        ("Matrix System automotive refinish range", "Refinish System", "2K urethane",
         "https://www.matrixsystem.com/"),
    ]),
    ("Kirker Automotive Finishes", "United States", "https://www.kirkerautomotive.com/", [
        ("Kirker Ultra-Glo acrylic urethane range", "Topcoat", "Acrylic urethane",
         "https://www.kirkerautomotive.com/"),
    ]),
    ("Dominion Sure Seal", "Canada", "https://www.dominionsureseal.com/", [
        ("Dominion Sure Seal seam sealer range", "Seam Sealer", "PVC / urethane",
         "https://www.dominionsureseal.com/"),
    ]),
    ("Parker LORD (Fusor)", "United States", "https://www.parker.com/", [
        ("Fusor structural panel bonding adhesive range", "Structural Adhesive", "Two-part epoxy / urethane",
         "https://www.parker.com/"),
    ]),
    ("Saint-Gobain Abrasives", "France", "https://www.saint-gobain-abrasives.com/", [
        ("Norton refinishing abrasive systems", "Abrasives", "Coated abrasive",
         "https://www.saint-gobain-abrasives.com/"),
    ]),
    ("Colad", "Netherlands", "https://www.colad.com/", [
        ("Colad bodyshop consumables range", "Consumables", "Application consumables",
         "https://www.colad.com/"),
    ]),
    ("Finixa", "Belgium", "https://www.finixa.com/", [
        ("Finixa bodyshop consumables range", "Consumables", "Application consumables",
         "https://www.finixa.com/"),
    ]),
    ("Würth", "Germany", "https://www.wuerth.com/", [
        ("Würth body repair filler and sealer range", "Body Filler", "Unsaturated polyester",
         "https://www.wuerth.com/"),
    ]),
    # SUNMIGHT'S URL WAS WRONG, WHICH IS WHY IT WAS DROPPED, NOT ABSENT.
    #
    # `https://www.sunmight.com/eng/` did not resolve on the 2026-08-30 run, so
    # the verifier dropped the row exactly as designed. The manufacturer is
    # real and its US site answers; the citation was the defect, not the
    # company. Repointed 2026-09-01.
    ("Sunmight", "South Korea", "https://www.sunmightusa.com/main/", [
        ("Sun Discs coated abrasive discs", "Abrasives", "Coated abrasive",
         "https://www.sunmightusa.com/products/sun-discs/"),
        ("Sunfoam abrasive foam range", "Abrasives", "Foam-backed coated abrasive",
         "https://www.sunmightusa.com/products/sunfoam/"),
        ("Sunmight backing pads", "Consumables", "Application consumables",
         "https://www.sunmightusa.com/products/backing-pads/"),
    ]),

    # ------------------------------------------------------------------
    # ADDED 2026-09-01 - closing L2 (50 competitors / 100+ products).
    #
    # EVERY URL BELOW CAME FROM THE MANUFACTURER'S OWN SITE OR FROM A SEARCH
    # INDEX THAT RETURNED IT, NOT FROM A GUESSED PATH.
    #
    # The category-listing pages of Troton, HB BODY, APP, Farecla, Menzerna,
    # Tenax and Scott Bader were fetched and their product links read off the
    # page; Novol, Roberlo, Mipa, Lechler and WEICON returned their product
    # URLs through a search index because their own listing pages refuse an
    # automated client (403). Either way the URL is the manufacturer's, and
    # `seed_public_intel_real.py` fetches every one of them again before a
    # single row is published.
    #
    # CHEMISTRY IS STATED CONSERVATIVELY AND NOTHING IS INFERRED FROM A
    # PRODUCT NAME ALONE. Where a page names the chemistry ("Epoxy Primer",
    # "polyester putty") it is recorded; where it does not, the field says what
    # class of product it is and stops there. "Ultralight Carbon" is recorded
    # as unsaturated polyester rather than as a carbon-fibre composite, because
    # the name is a brand and not a datasheet.
    #
    # STILL NO PRICES, for the reason at the top of this file.
    ("Troton", "Poland", "https://www.troton.pl/en/", [
        ("Master Airflex", "Body Filler", "Unsaturated polyester",
         "https://www.troton.pl/en/products/master-products/putties-master/airflex-new/"),
        ("Master Super-T", "Body Filler", "Unsaturated polyester",
         "https://www.troton.pl/en/products/master-products/putties-master/super-t/"),
        ("Master Turbo-T", "Body Filler", "Unsaturated polyester",
         "https://www.troton.pl/en/products/master-products/putties-master/turbo-t-en/"),
        ("Master Gripper-T", "Body Filler", "Unsaturated polyester",
         "https://www.troton.pl/en/products/master-products/putties-master/gripper-t-2/"),
        ("Master Atlantic", "Body Filler", "Unsaturated polyester",
         "https://www.troton.pl/en/products/master-products/putties-master/atlantic/"),
        ("Master Amber", "Body Filler", "Unsaturated polyester",
         "https://www.troton.pl/en/products/master-products/putties-master/amber-en/"),
        ("Master Superior Lite", "Lightweight Body Filler", "Unsaturated polyester, lightweight",
         "https://www.troton.pl/en/products/master-products/putties-master/superior-lite/"),
        ("Master Hybrid", "Body Filler", "Unsaturated polyester",
         "https://www.troton.pl/en/products/master-products/putties-master/hybrid-en/"),
        ("Master Bold", "Body Filler", "Unsaturated polyester",
         "https://www.troton.pl/en/products/master-products/putties-master/bold-en/"),
        ("Master Extra", "Body Filler", "Unsaturated polyester",
         "https://www.troton.pl/en/products/master-products/putties-master/extra-en/"),
        ("Master Gold Plus", "Body Filler", "Unsaturated polyester",
         "https://www.troton.pl/en/products/master-products/putties-master/gold-plus-en/"),
        ("Master Unifill", "Body Filler", "Unsaturated polyester",
         "https://www.troton.pl/en/products/master-products/putties-master/unifill-2/"),
        ("Master Ultralight Carbon", "Lightweight Body Filler", "Unsaturated polyester, lightweight",
         "https://www.troton.pl/en/products/master-products/putties-master/ultralight-carbon-en/"),
        ("Master Black Carbon", "Body Filler", "Unsaturated polyester",
         "https://www.troton.pl/en/products/master-products/putties-master/black-carbon-en/"),
        ("Master Onyx", "Body Filler", "Unsaturated polyester",
         "https://www.troton.pl/en/products/master-products/putties-master/onyx-en/"),
        ("Master Glass Fibre", "Fibreglass Filler", "Polyester / glass fibre",
         "https://www.troton.pl/en/products/master-products/putties-master/glass-fibre-en/"),
        ("Master Plastic", "Plastic Repair Filler", "Polyester, flexible",
         "https://www.troton.pl/en/products/master-products/putties-master/plastic-en/"),
        ("Master Polyester Spray Filler", "Spray Filler", "Unsaturated polyester",
         "https://www.troton.pl/en/products/master-products/putties-master/polyester-spray-filler-putties/"),
        ("Master Epoxy Primer 4:1", "Epoxy Primer", "Two-component epoxy",
         "https://www.troton.pl/en/products/master-products/primers-master/epoxy-primer-41-en/"),
        ("Master Epoxy Primer 1:1", "Epoxy Primer", "Two-component epoxy",
         "https://www.troton.pl/en/products/master-products/primers-master/epoxy-primer-11-en/"),
        ("Master V-PRO EXPRESS 4:1", "Primer Filler", "Two-component primer filler",
         "https://www.troton.pl/en/products/master-products/primers-master/v-pro-express-4-1-2/"),
        ("Master DTM Primer Sealer 4:1", "Primer Sealer", "Two-component primer sealer",
         "https://www.troton.pl/en/products/master-products/primers-master/dtm-primer-sealer-41-en/"),
        ("Master V2018 Anticorrosive Rapid Drying HS 5:1", "Primer Filler",
         "Two-component anticorrosive primer",
         "https://www.troton.pl/en/products/master-products/primers-master/v2018-anticorrosive-rapid-drying-hs-51-en/"),
        ("Master V2018 Anticorrosive Rapid Drying HS 4:1", "Primer Filler",
         "Two-component anticorrosive primer",
         "https://www.troton.pl/en/products/master-products/primers-master/v2018-anticorrosive-rapid-drying-hs-41/"),
        ("Master V2012 HS 5:1", "Primer Filler", "Two-component high-solids primer",
         "https://www.troton.pl/en/products/master-products/primers-master/v2012-hs-51/"),
        ("Master V2012 HS 4:1", "Primer Filler", "Two-component high-solids primer",
         "https://www.troton.pl/en/products/master-products/primers-master/v2012-hs-41/"),
        ("Master V2007 HS 5:1", "Primer Filler", "Two-component high-solids primer",
         "https://www.troton.pl/en/products/master-products/primers-master/v2007-hs-51-en/"),
        ("Master V2007 HS 4:1", "Primer Filler", "Two-component high-solids primer",
         "https://www.troton.pl/en/products/master-products/primers-master/v2007-hs-41-en/"),
        ("Master HS 5:1", "Primer Filler", "Two-component high-solids primer",
         "https://www.troton.pl/en/products/master-products/primers-master/hs-master-51/"),
        ("Master HS 4:1", "Primer Filler", "Two-component high-solids primer",
         "https://www.troton.pl/en/products/master-products/primers-master/hs-master-41/"),
        ("Inter Troton Universal", "Body Filler", "Unsaturated polyester",
         "https://www.troton.pl/en/products/inter-troton-en/putties-inter-troton/universal-high-filling-polyester-body-filler/"),
        ("Inter Troton Soft", "Body Filler", "Unsaturated polyester",
         "https://www.troton.pl/en/products/inter-troton-en/putties-inter-troton/soft-soft-and-filling-polyester-putty/"),
        ("Inter Troton Fine", "Glazing Putty", "Unsaturated polyester, finishing",
         "https://www.troton.pl/en/products/inter-troton-en/putties-inter-troton/fine-finishing-polyester-body-filler/"),
        ("Inter Troton Aluminium", "Body Filler", "Polyester with aluminium filler",
         "https://www.troton.pl/en/products/inter-troton-en/putties-inter-troton/aluminium-filling-polyester-body-filler-with-aluminum/"),
        ("Inter Troton Glass Fibre", "Fibreglass Filler", "Polyester / glass fibre",
         "https://www.troton.pl/en/products/inter-troton-en/putties-inter-troton/glass-fibre-structural-polyester/"),
        ("Inter Troton Light", "Lightweight Body Filler", "Unsaturated polyester, lightweight",
         "https://www.troton.pl/en/products/inter-troton-en/putties-inter-troton/light-lightweight-filling-polyester-body-filler/"),
        ("Inter Troton Plastic", "Plastic Repair Filler", "Polyester, flexible",
         "https://www.troton.pl/en/products/inter-troton-en/putties-inter-troton/plastic-polyester-putty-with-high-elasticity/"),
        ("Inter Troton Polyester Spray Filler", "Spray Filler", "Unsaturated polyester",
         "https://www.troton.pl/en/products/inter-troton-en/putties-inter-troton/polyester-spray-filler-en/"),
    ]),
    ("HB BODY", "Greece", "https://hbbody.com/", [
        ("F202 ZINC PLUS", "Body Filler", "Unsaturated polyester with zinc",
         "https://hbbody.com/en/product/f202-zinc-plus/"),
        ("F211 BODYSOFT", "Body Filler", "Unsaturated polyester",
         "https://hbbody.com/en/product/f211-bodysoft/"),
        ("F213 UNIPLUS", "Body Filler", "Unsaturated polyester",
         "https://hbbody.com/en/product/f213-uniplus/"),
        ("F232 UNIVERSAL", "Body Filler", "Unsaturated polyester",
         "https://hbbody.com/en/product/f232-universal/"),
        ("F282 FLYLITE", "Lightweight Body Filler", "Unsaturated polyester, lightweight",
         "https://hbbody.com/en/product/f282-flylite/"),
        ("F290 MULTIFILLER", "Body Filler", "Unsaturated polyester",
         "https://hbbody.com/en/product/f290-multifiller-beige/"),
        ("F218 GLAZE FILLER", "Glazing Putty", "Unsaturated polyester, finishing",
         "https://hbbody.com/en/product/f218-glaze-filler/"),
        ("F220 BODYFINE", "Glazing Putty", "Unsaturated polyester, finishing",
         "https://hbbody.com/en/product/f220-bodyfine/"),
        ("F222 BUMPERSOFT", "Plastic Repair Filler", "Polyester, flexible",
         "https://hbbody.com/en/product/f222-bumpersoft/"),
        ("F215 FIBERLIGHT", "Fibreglass Filler", "Polyester / glass fibre",
         "https://hbbody.com/en/product/f215-fiberlight/"),
        ("F217 FIBERLIGHT", "Fibreglass Filler", "Polyester / glass fibre",
         "https://hbbody.com/en/product/f217-fiberlight/"),
        ("F250 BODYFIBER", "Fibreglass Filler", "Polyester / glass fibre",
         "https://hbbody.com/en/product/f250-bodyfiber/"),
        ("F255 BODYALU", "Body Filler", "Polyester with aluminium filler",
         "https://hbbody.com/en/product/f255-bodyalu/"),
        ("F980 1K FINE FILLER", "Glazing Putty", "One-component fine filler",
         "https://hbbody.com/en/product/f980-1k-fine-filler/"),
        ("BODY 610 UNIVERSAL FILLER", "Body Filler", "Unsaturated polyester",
         "https://hbbody.com/en/product/body-610-universal-filler/"),
        ("BODY 611 MULTI FILLER", "Body Filler", "Unsaturated polyester",
         "https://hbbody.com/en/product/body-611-multi-filler/"),
        ("BODY 615 FIBER FILLER", "Fibreglass Filler", "Polyester / glass fibre",
         "https://hbbody.com/en/product/body-615-fiber-filler/"),
        ("BODY 617 NANO FIBER", "Fibreglass Filler", "Polyester / glass fibre",
         "https://hbbody.com/en/product/body-617-nano-fiber/"),
        ("205 LP PLUS SOFT", "Body Filler", "Unsaturated polyester",
         "https://hbbody.com/en/product/205-lp-plus-soft/"),
        ("209 UNILITE", "Lightweight Body Filler", "Unsaturated polyester, lightweight",
         "https://hbbody.com/en/product/209-unilite/"),
        ("210 UNISOFT", "Body Filler", "Unsaturated polyester",
         "https://hbbody.com/en/product/210-unisoft/"),
        ("225 UNIFINE", "Glazing Putty", "Unsaturated polyester, finishing",
         "https://hbbody.com/en/product/225-unifine/"),
        ("260 BODYFILLER", "Body Filler", "Unsaturated polyester",
         "https://hbbody.com/en/product/260-bodyfiller/"),
        ("280 LIGHTWEIGHT FILLER", "Lightweight Body Filler", "Unsaturated polyester, lightweight",
         "https://hbbody.com/en/product/280-lightweight-filler/"),
        ("290 ULTRA LIGHT MULTIFILLER", "Lightweight Body Filler",
         "Unsaturated polyester, lightweight",
         "https://hbbody.com/en/product/290-ultra-light-multfiller/"),
        ("P987 2K 1:1 EPOXY SEALER", "Epoxy Primer", "Two-component epoxy",
         "https://hbbody.com/product/p987-2k-11-epoxy-sealer/"),
        ("955 TOUGH LINER", "Protective Coating", "Two-component polyurethane",
         "https://hbbody.com/en/product/955-tough-liner/"),
    ]),
    ("Novol", "Poland", "https://novol.com/", [
        ("NOVOL PROFESSIONAL SOFT PLUS", "Body Filler", "Unsaturated polyester",
         "https://novol.com/professional/en/products/soft-plus/"),
        ("NOVOL PROFESSIONAL FIBER", "Fibreglass Filler", "Polyester / glass fibre",
         "https://novol.com/professional/en/products/fiber/"),
        ("NOVOL ULTRA FIBER", "Fibreglass Filler", "Polyester / glass fibre",
         "https://novol.com/ultra/en/products/fiber/"),
        ("NOVOL NFCC ELASTIC FIBER", "Fibreglass Filler", "Polyester / glass fibre",
         "https://novol.com/nfcc/en/products/elastic-fiber/"),
    ]),
    ("Roberlo", "Spain", "https://www.roberlo.com/en/", [
        ("MAXIFILL", "Body Filler", "Unsaturated polyester",
         "https://www.roberlo.com/en/product/maxifill/"),
        ("MAXIFILL PLUS", "Lightweight Body Filler", "Unsaturated polyester, lightweight",
         "https://www.roberlo.com/en/product/maxifill-plus/"),
        ("MAXILIGHT", "Lightweight Body Filler", "Unsaturated polyester, lightweight",
         "https://www.roberlo.com/en/product/maxilight/"),
        ("EASY 6000", "Lightweight Body Filler", "Unsaturated polyester, lightweight",
         "https://www.roberlo.com/en/product/easy-6000/"),
    ]),
    ("Mipa", "Germany", "https://www.mipa-paints.com/en/", [
        ("Mipa putty range", "Body Filler", "Unsaturated polyester",
         "https://www.mipa-paints.com/en/products/showroom/mipa-putty-range/"),
        ("Mipa primer and filler range", "Primer Filler", "Two-component primer filler",
         "https://www.mipa-paints.com/en/products/car-refinishing/primer-filler/"),
        ("Mipa car refinishing range", "Refinish Coating", "Two-component refinish coating",
         "https://www.mipa-paints.com/en/products/car-refinishing/"),
    ]),
    ("Lechler", "Italy", "https://www.lechler.eu/en/home/refinish", [
        ("Macrofan Green-Tech Filler", "Primer Filler", "Two-component primer filler",
         "https://lechler.eu/en/Home/Refinish/High-Efficiency-Painting-Process/Green-Tech-Filler"),
        ("Grey Filler System", "Primer Filler", "Two-component primer filler",
         "https://www.lechler.eu/en/home/refinish/refinish-products-catalogue/grey-filler-system"),
    ]),
    ("WEICON", "Germany", "https://www.weicon.de/en/", [
        ("WEICON Epoxy Resin Putty", "Repair Compound", "Two-component epoxy, kneadable",
         "https://www.weicon.de/en/weicon-epoxy-resin-putty-kneadable-universal-repair-compound/10000104"),
        ("WEICON HP", "Structural Adhesive", "Two-component epoxy",
         "https://www.weicon.de/en/products/weicon-chemie/adhesives-and-sealants/2-component-adhesives-and-sealants/epoxy-resin-systems/plastic-metal/937/weicon-hp"),
        ("WEICON Repair Sticks", "Repair Compound", "Two-component epoxy, kneadable",
         "https://www.weicon.de/en/products/chemical-products/adhesives-and-sealants/2-component-adhesives-and-sealants/epoxy-resin-systems/repair-sticks/"),
        ("WEICON Epoxy Adhesives range", "Structural Adhesive", "Two-component epoxy",
         "https://www.weicon.de/en/products/chemical-products/adhesives-and-sealants/2-component-adhesives-and-sealants/epoxy-resin-systems/epoxy-adhesives/"),
    ]),
    ("Farecla", "United Kingdom", "https://www.farecla.com/", [
        ("G3 Regular Grade Paste Compound", "Polishing Compound", "Abrasive compound",
         "https://www.farecla.com/products/g3-regular-grade-paste-compound"),
        ("G3 Premium Abrasive Compound", "Polishing Compound", "Abrasive compound",
         "https://www.farecla.com/products/g3-premium-abrasive-compound"),
        ("G3 Advanced Liquid Compound", "Polishing Compound", "Abrasive compound",
         "https://www.farecla.com/products/g3-advanced-liquid-compound"),
        ("G3 Extra Abrasive Compound", "Polishing Compound", "Abrasive compound",
         "https://www.farecla.com/products/g3-extra-abrasive-compound"),
        ("G3 Extra Plus Abrasive Compound", "Polishing Compound", "Abrasive compound",
         "https://www.farecla.com/products/g3-extra-plus-abrasive-compound"),
        ("G3 Fine Finishing Compound", "Polishing Compound", "Abrasive compound",
         "https://www.farecla.com/products/by-type/fine-cut-polishes/g3-fine-finishing-compound"),
    ]),
    ("Menzerna", "Germany", "https://www.menzerna.com/", [
        ("Heavy Cut Compound 400", "Polishing Compound", "Abrasive compound",
         "https://www.menzerna.com/car-care/car-polish/products/details/heavy-cut-compound-400"),
        ("Super Finish Compound M5", "Polishing Compound", "Solid polishing compound",
         "https://www.menzerna.com/industrial-polishing/polishing-compounds/solid-compounds/product-overview/details/m5"),
        ("Super Finish Compound P175", "Polishing Compound", "Solid polishing compound",
         "https://www.menzerna.com/industrial-polishing/polishing-compounds/solid-compounds/product-overview/details/p175"),
    ]),
    # TENAX IS STONE, NOT AUTOMOTIVE, AND IS HERE ON PURPOSE.
    #
    # Its adhesives are unsaturated-polyester and knife-grade epoxy systems -
    # the same chemistry families this R&D programme formulates - so it is a
    # benchmark for the chemistry, not a competitor for the customer. Recorded
    # as what it is rather than filed under automotive refinishing.
    ("Tenax", "Italy", "https://tenaxusa.com/", [
        ("Transparent Flowing Polyester", "Stone Adhesive", "Unsaturated polyester",
         "https://tenaxusa.com/products/flowing-transp"),
        ("Solido XQ", "Stone Adhesive", "Unsaturated polyester",
         "https://tenaxusa.com/products/solido-xq"),
        ("Travertine Filler", "Stone Filler", "Unsaturated polyester",
         "https://tenaxusa.com/products/travertine-filler"),
        ("Domo 10 Knife Grade Epoxy", "Stone Adhesive", "Two-component epoxy",
         "https://tenaxusa.com/products/domo-10"),
    ]),
    # SCOTT BADER IS UPSTREAM, NOT A COMPETITOR, AND THAT IS ALSO DELIBERATE.
    #
    # Crystic is the resin and gelcoat a body filler is FORMULATED FROM. It
    # belongs in a competitor-intelligence catalogue for the same reason a raw
    # material belongs in a formulation: it is the benchmark for the base
    # chemistry. The category names say so.
    ("Scott Bader", "United Kingdom", "https://www.scottbader.com/", [
        ("Crystic Isophthalic Polyester Resin 489PA", "Polyester Resin",
         "Isophthalic unsaturated polyester",
         "https://www.scottbader.com/products/crystic-polyester-resin-489pa/"),
        ("Crystic Orthophthalic Polyester Resin 2.420PA", "Polyester Resin",
         "Orthophthalic unsaturated polyester",
         "https://www.scottbader.com/products/crystic-polyester-resin-2-420pa/"),
        ("Crystic Isophthalic Sandable Gelcoat 45PA", "Gelcoat",
         "Isophthalic unsaturated polyester",
         "https://www.scottbader.com/products/crystic-isophthalic-sandable-gelcoat-45pa/"),
        ("Crystic Brush Gelcoat 69PA", "Gelcoat", "Unsaturated polyester",
         "https://www.scottbader.com/products/crystic-brush-gelcoat-69pa/"),
        ("Crystic Isophthalic Spray Gelcoat 92PA", "Gelcoat",
         "Isophthalic unsaturated polyester",
         "https://www.scottbader.com/products/crystic-spray-gelcoat-92pa/"),
        ("Crestafire Crystic 1355PA", "Polyester Resin",
         "Fire-retardant unsaturated polyester",
         "https://www.scottbader.com/products/crystic-fire-retardant-resin-1355pa/"),
        ("Crestamould Crystic Glosscoat", "Gelcoat", "Unsaturated polyester",
         "https://www.scottbader.com/products/crystic-glosscoat/"),
    ]),
    ("APP (Auto-Plast Produkt)", "Poland", "https://app.com.pl/en/", [
        ("APP PE Poly Plast", "Body Filler", "Unsaturated polyester",
         "https://app.com.pl/en/company/products/product/01010103/Universal-putty-APP-PE-Poly-Plast?productGroupId=010101"),
        ("APP Poly Plast Finisher", "Glazing Putty", "Unsaturated polyester, finishing",
         "https://app.com.pl/en/company/products/product/01010142/Universal-putty-APP-Poly-Plast-Finisher?productGroupId=010101"),
        ("APP Poly Plast Softer", "Body Filler", "Unsaturated polyester",
         "https://app.com.pl/en/company/products/product/01010140/Universal-putty-APP-Poly-Plast-Softer?productGroupId=010101"),
        ("APP Compact", "Lightweight Body Filler", "Unsaturated polyester, lightweight",
         "https://app.com.pl/en/company/products/product/01010123/Universal-putty-APP-Compact?productGroupId=010101"),
        ("APP Fiber Light", "Fibreglass Filler", "Polyester / glass fibre",
         "https://app.com.pl/en/company/products/product/01010120/Putty-with-glass-fiber-light-APP-Fiber-Light?productGroupId=010101"),
        ("APP Plastiflex", "Plastic Repair Filler", "Polyester, flexible",
         "https://app.com.pl/en/company/products/product/01250103/Putty-for-plastics-APP-Plastiflex?productGroupId=012501"),
    ]),
]
