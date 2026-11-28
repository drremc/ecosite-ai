"""Cautious Iowa native-plant *shortlists* for candidate restoration areas.

These are not prescriptions, planting plans, seed rates, a substitute for a survey,
or verified biodiversity offsets. Species are only suggested if the mapped
community is Iowa AND the user has supplied sunlight and soil-moisture conditions.
Additional site-specific plant provenance, wetland permitting and ecosystem
reference checks remain essential.
"""
from __future__ import annotations

IOWA_DNR = "https://www.iowadnr.gov/news-release/2025-05-07/adding-iowa-native-plants-landscaping-benefits-native-bees-and-butterflies"
IOWA_DNR_MANAGEMENT = "https://www.iowadnr.gov/programs-services/wildlife-landowner-assistance/planning-management"
IOWA_DRY = "https://yardandgarden.extension.iastate.edu/faq/what-native-perennials-grow-well-dry-soils"
IOWA_WET = "https://yardandgarden.extension.iastate.edu/how-to/native-perennials-moist-wet-soils"
IOWA_SHADE = "https://yardandgarden.extension.iastate.edu/faq/what-are-some-good-native-perennials-shady-site"
XERCES = "https://xerces.org/publications/habitat-installation-guides/upper-midwest-pollinator-meadow"

SOURCE_TITLES = {
    IOWA_DNR: "Iowa DNR — Native plants for bees and butterflies",
    IOWA_DNR_MANAGEMENT: "Iowa DNR — Planting native grasses and forbs",
    IOWA_DRY: "Iowa State Extension — Iowa native plants for dry soils",
    IOWA_WET: "Iowa State Extension — Native plants for moist/wet soils",
    IOWA_SHADE: "Iowa State Extension — Native plants for shady sites",
    XERCES: "Xerces Society — Upper Midwest pollinator meadow guide",
}


def plant(common: str, scientific: str, role: str, source: str) -> dict:
    return {"common":common, "scientific":scientific, "role":role, "source":source}


# All plants are documented for Iowa by the sources above. Specific shortlists
# follow sunlight + broad soil-moisture suitability; they are NOT a precision
# match to a parcel, county, native plant community, elevation, or water regime.
IOWA_PALETTES = {
    ("sun", "dry"): [
        plant("Little bluestem", "Schizachyrium scoparium", "Bunchgrass, shelter and larval habitat", IOWA_DRY),
        plant("Side-oats grama", "Bouteloua curtipendula", "Short native grass and habitat structure", IOWA_DRY),
        plant("Purple prairie clover", "Dalea purpurea", "Flowering legume for native bees", IOWA_DRY),
        plant("Butterfly milkweed", "Asclepias tuberosa", "Monarch host plant; summer nectar", IOWA_DRY),
        plant("Pale purple coneflower", "Echinacea pallida", "Summer flowers for native insects", IOWA_DRY),
        plant("Black-eyed Susan", "Rudbeckia hirta", "Summer blooms, seeds for wildlife", IOWA_DRY),
        plant("Prairie dropseed", "Sporobolus heterolepis", "Clumping grass, native structure", IOWA_DRY),
        plant("Showy goldenrod", "Solidago speciosa", "Late-season pollen and nectar", IOWA_DRY),
    ],
    ("sun", "average"): [
        plant("Golden alexanders", "Zizia aurea", "Spring flowers; supports early pollinators", IOWA_DNR),
        plant("Little bluestem", "Schizachyrium scoparium", "Native bunchgrass for shelter and structure", IOWA_DNR),
        plant("Prairie dropseed", "Sporobolus heterolepis", "Native bunchgrass; insect habitat", IOWA_DNR),
        plant("Wild bergamot", "Monarda fistulosa", "Summer nectar for bees and butterflies", IOWA_DNR),
        plant("Pale purple coneflower", "Echinacea pallida", "Summer blooms for native insects", IOWA_DNR),
        plant("Prairie blazing star", "Liatris pycnostachya", "Late-summer nectar; prefers moist, well-drained soil", IOWA_WET),
        plant("New England aster", "Symphyotrichum novae-angliae", "Late-season flowers for pollinators", IOWA_DNR),
        plant("Side-oats grama", "Bouteloua curtipendula", "Native grass; habitat structure", IOWA_DNR),
    ],
    ("sun", "wet"): [
        plant("Swamp milkweed", "Asclepias incarnata", "Moist-area monarch host and nectar plant", IOWA_WET),
        plant("Prairie blazing star", "Liatris pycnostachya", "Moist, well-drained prairie blooms", IOWA_WET),
        plant("Cardinal flower", "Lobelia cardinalis", "Hummingbird flowers; consistently moist soil", IOWA_WET),
        plant("Fox sedge", "Carex vulpinoidea", "Native sedge for moist ground", IOWA_WET),
        plant("Switchgrass", "Panicum virgatum", "Native grass suitable for moist soil", IOWA_WET),
        plant("Big bluestem", "Andropogon gerardii", "Tall native grass where space allows", IOWA_WET),
    ],
    ("shade", "dry"): [
        plant("Wild columbine", "Aquilegia canadensis", "Spring nectar in partial shade", IOWA_DRY),
        plant("Wild ginger", "Asarum canadense", "Woodland groundcover", IOWA_DRY),
        plant("Wild geranium", "Geranium maculatum", "Spring woodland flowers", IOWA_DRY),
    ],
    ("shade", "average"): [
        plant("Wild columbine", "Aquilegia canadensis", "Spring woodland flowers", IOWA_SHADE),
        plant("Wild ginger", "Asarum canadense", "Low-growing native woodland cover", IOWA_SHADE),
        plant("Wild geranium", "Geranium maculatum", "Spring bloom in a woodland planting", IOWA_SHADE),
    ],
    ("shade", "wet"): [
        plant("Cardinal flower", "Lobelia cardinalis", "Bright flowers for moist partial shade", IOWA_WET),
        plant("Fox sedge", "Carex vulpinoidea", "Native sedge for moist partial shade", IOWA_WET),
        plant("Wild ginger", "Asarum canadense", "Possible native groundcover on shaded moist soil", IOWA_SHADE),
    ],
}


def native_plant_shortlist(state: str | None, sunlight: str = "unknown",
                           soil_moisture: str = "unknown") -> dict:
    """Return condition-specific plant candidates, or an explicit no-data warning.

    State must be identified by the geocoder, not assumed from current map center.
    Sun and soil inputs are self-reported and not derived from satellite imagery.
    """
    state_label = (state or "Not confirmed").strip()
    data = {"state":state_label,"sunlight":sunlight,"soil_moisture":soil_moisture,
            "items":[],"sources":[],"site_conditions_verified":False}
    if state_label.casefold() != "iowa":
        data["note"] = ("Specific native-plant examples are currently curated only for Iowa. "
                        "For this location, ask your state natural-heritage program, local Extension "
                        "office or conservation district for a regionally native plant list.")
        return data
    if sunlight == 'unknown' or soil_moisture == 'unknown':
        data["note"] = ("Iowa plant examples require a sunlight and soil-moisture selection. "
                        "Choose both conditions from a site visit before requesting a plant shortlist.")
        data["sources"] = [{"title":SOURCE_TITLES[IOWA_DNR],"url":IOWA_DNR},
                           {"title":SOURCE_TITLES[IOWA_DNR_MANAGEMENT],"url":IOWA_DNR_MANAGEMENT}]
        return data
    items = [dict(item) for item in IOWA_PALETTES[(sunlight, soil_moisture)]]
    urls = list(dict.fromkeys(item['source'] for item in items))
    urls.extend(x for x in [IOWA_DNR_MANAGEMENT, XERCES] if x not in urls)
    data.update({
        "items":items,
        "sources":[{"title":SOURCE_TITLES[url],"url":url} for url in urls],
        "note":("Conditional Iowa native-plant examples for the selected sun and moisture "
                "conditions. Check county-level native range, seed provenance, soil chemistry, "
                "drainage, utilities, species interactions and ecological reference habitat "
                "before planting; do not plant into high-quality existing habitat."),
    })
    return data


def iowa_reference_groups() -> list[dict]:
    """Preview factual Iowa-native examples grouped by site conditions.

    These are not assigned to any mapped site and cannot be used to calculate
    offsets, feasible planting acreage, or ecological equivalence.
    """
    groups = [
        ('Full sun · dry soils', 'sun', 'dry'),
        ('Full sun · average moisture', 'sun', 'average'),
        ('Full sun · moist soils', 'sun', 'wet'),
        ('Part shade · average moisture', 'shade', 'average'),
    ]
    return [
        {'label': label, 'sunlight': sun, 'soil_moisture': moisture,
         'items': [dict(p) for p in IOWA_PALETTES[(sun, moisture)][:3]]}
        for label, sun, moisture in groups
    ]
