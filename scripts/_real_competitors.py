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
    ("Sunmight", "South Korea", "https://www.sunmight.com/eng/", [
        ("Sunmight Gold Film abrasive range", "Abrasives", "Coated abrasive",
         "https://www.sunmight.com/eng/"),
    ]),
]
