"""Formulation mathematics.

Every function here is pure, exact under `Decimal`, and total: given inputs
it either returns a value or raises. None of them guesses.

WHY `Decimal` AND NOT `float`, RESTATED WHERE IT BITES. A polyester filler
at 34.75% is a controlled quantity. In binary floating point 34.75 is
representable but 0.1 is not, and a batch scaled through float arithmetic
drifts by parts-per-billion that then fail an exact reconciliation against
a weighed mass. `CLAUDE.md` §5 forbids float for percentages, masses and
densities; these signatures enforce it rather than trusting callers.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation

__all__ = [
    "Component",
    "SubmissionBlock",
    "binder_to_filler_ratio",
    "cost_per_kg",
    "fraction_to_percent",
    "normalize_to_100",
    "scale_to_batch",
    "solids_content",
    "stoichiometric_hardener_parts",
    "theoretical_density",
    "total_percentage",
    "validate_for_submission",
    "voc_content_g_per_l",
]

HUNDRED = Decimal("100")
ZERO = Decimal("0")


def _dec(value: object, field: str) -> Decimal:
    """Accept Decimal, int or str. Reject float, loudly.

    A `float` is refused rather than converted. `Decimal(0.1)` is
    0.1000000000000000055511151231257827, and accepting one here would
    convert a caller's bug into a plausible-looking number that nothing
    downstream could detect.
    """
    if isinstance(value, float):
        raise TypeError(
            f"{field} was a float. Percentages, masses and densities are "
            f"Decimal (CLAUDE.md §5) — pass Decimal('{value}') or a string."
        )
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, str)):
        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"{field} is not a number: {value!r}") from exc
    raise TypeError(f"{field} must be Decimal, int or str, not {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class Component:
    """One line of a formula.

    `percentage` is mass percent of the total formula. `role` drives the
    binder/filler and resin/hardener ratios and is deliberately a plain
    string rather than an enum here: the authoritative role vocabulary is a
    database table, and duplicating it as a Python enum would be a second
    list to keep in step (the failure this codebase keeps hitting).
    """

    material_code: str
    percentage: Decimal
    role: str = "other"
    density_g_cm3: Decimal | None = None
    solids_fraction: Decimal | None = None
    voc_fraction: Decimal | None = None
    cost_per_kg: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "percentage", _dec(self.percentage, "percentage"))
        if self.percentage < ZERO:
            raise ValueError(f"{self.material_code}: percentage cannot be negative")
        for field in ("density_g_cm3", "solids_fraction", "voc_fraction", "cost_per_kg"):
            raw = getattr(self, field)
            if raw is not None:
                object.__setattr__(self, field, _dec(raw, field))
        if self.density_g_cm3 is not None and self.density_g_cm3 <= ZERO:
            raise ValueError(f"{self.material_code}: density must be positive")
        for field in ("solids_fraction", "voc_fraction"):
            raw = getattr(self, field)
            if raw is not None and not (ZERO <= raw <= Decimal("1")):
                raise ValueError(f"{self.material_code}: {field} must be between 0 and 1")


def _require(components: list[Component]) -> None:
    if not components:
        raise ValueError("a formula needs at least one component")


# ---------------------------------------------------------------- totals


def fraction_to_percent(fraction: Decimal | int | str) -> Decimal:
    """A 0-1 fraction as a percentage, exactly.

    WHY A THREE-LINE FUNCTION LIVES IN THE ENGINE.

    It is one multiplication, and it was written here because the
    alternative kept being written somewhere worse. `fraction * 100` has
    now been caught TWICE in review on this project -- once in a React
    component and once in a build script -- and `CLAUDE.md` rule 2 gives
    deterministic calculation on a controlled quantity to Python without
    an exception for easy arithmetic.

    In JavaScript the same expression is genuinely wrong rather than
    merely misplaced: `0.35 * 100` is 35.000000000000004, and a solids
    content is a controlled figure on a technical datasheet.

    Exact under `Decimal`, and the trailing scale is preserved --
    `Decimal("0.3500") * 100` is `35.0000`, which keeps the significant
    figures the laboratory actually recorded rather than silently
    rounding them away.
    """
    value = _dec(fraction, "fraction")
    if not (ZERO <= value <= Decimal("1")):
        raise ValueError(f"a fraction must be between 0 and 1, not {value}")
    return value * HUNDRED


def total_percentage(components: list[Component]) -> Decimal:
    """Exact sum of component percentages."""
    _require(components)
    return sum((c.percentage for c in components), start=ZERO)


@dataclass(frozen=True, slots=True)
class SubmissionBlock:
    """One reason a formula may not be submitted.

    A list of these, rather than a bool. `CLAUDE.md` §8 lists four distinct
    hard blocks, and collapsing them into "invalid" tells the chemist
    nothing about which one to fix.
    """

    code: str
    message: str


def validate_for_submission(
    components: list[Component],
    *,
    tolerance: Decimal = Decimal("0.01"),
    restricted_materials: frozenset[str] = frozenset(),
    require_density: bool = False,
    failed_safety_checks: tuple[str, ...] = (),
) -> list[SubmissionBlock]:
    """Hard submission validation. Empty list means submittable.

    `CLAUDE.md` §8: submission is hard-blocked when the total percentage is
    outside tolerance, required material data is missing, a restricted
    material is used, or a critical safety check fails. Returned rather
    than raised, because the UI must show *every* reason at once — a form
    that reveals one blocker per attempt is how a chemist learns to distrust
    the software.

    🔴 THE FOURTH BLOCK USED TO BE MISSING while this docstring listed it.
    A formula totalling 100% with complete data and no restricted material
    was reported SUBMITTABLE even with a failed critical safety check —
    the one block whose absence is dangerous rather than merely wrong.
    Raised by Codex, and it is the exact defect class this codebase names
    most often: a comment describing a guarantee the code does not provide.

    `failed_safety_checks` is passed IN rather than evaluated here. Safety
    checks are domain rules over material hazard data, not arithmetic, and
    this module is pure calculation with no I/O — inventing them here would
    put a compliance decision inside a maths function.
    """
    _require(components)
    blocks: list[SubmissionBlock] = []

    total = total_percentage(components)
    if abs(total - HUNDRED) > tolerance:
        blocks.append(
            SubmissionBlock(
                "TOTAL_OUT_OF_TOLERANCE",
                f"Components total {total}%, outside the ±{tolerance}% tolerance around 100%.",
            )
        )

    seen: set[str] = set()
    for c in components:
        if c.material_code in seen:
            blocks.append(
                SubmissionBlock(
                    "DUPLICATE_COMPONENT",
                    f"{c.material_code} appears more than once. Two lines for one "
                    f"material make the percentage ambiguous.",
                )
            )
        seen.add(c.material_code)

        if c.material_code in restricted_materials:
            blocks.append(
                SubmissionBlock(
                    "RESTRICTED_MATERIAL",
                    f"{c.material_code} is restricted and may not be used without "
                    f"an approved exemption.",
                )
            )

        if require_density and c.density_g_cm3 is None:
            blocks.append(
                SubmissionBlock(
                    "MISSING_MATERIAL_DATA",
                    f"{c.material_code} has no density, so theoretical density "
                    f"cannot be calculated.",
                )
            )

    for check in failed_safety_checks:
        blocks.append(
            SubmissionBlock(
                "SAFETY_CHECK_FAILED",
                f"Critical safety check failed: {check}. This cannot be waived at submission.",
            )
        )

    return blocks


def normalize_to_100(components: list[Component]) -> list[Component]:
    """Scale every percentage so the total is EXACTLY 100.

    The last component absorbs the rounding residue, so the result sums to
    100 exactly rather than to 99.999999. Anything else would leave a
    formula that normalisation had just "fixed" still failing its own total
    check.
    """
    _require(components)
    total = total_percentage(components)
    if total <= ZERO:
        raise ValueError("cannot normalise a formula whose components total zero")

    scaled: list[Component] = []
    running = ZERO
    for c in components[:-1]:
        pct = (c.percentage * HUNDRED / total).quantize(Decimal("0.0001"))
        running += pct
        # `dataclasses.replace`, not `Component(**{**_as_dict(c), ...})`.
        # The dict form widens every field to `object`, so mypy could not
        # check a single argument and rejected the call outright — six errors
        # for what is one idea. `replace` keeps the field types and still
        # re-runs __post_init__, which is where the Decimal and range
        # validation lives.
        scaled.append(replace(c, percentage=pct))

    # Clamped, for the same reason and with worse consequences than in
    # scale_to_batch: `HUNDRED - running` going negative makes
    # Component.__post_init__ raise "percentage cannot be negative", so the
    # function whose whole job is to FIX a total crashes on the way out.
    # Reproduced by the Supervisor in 13 random trials.
    last = components[-1]
    residue = HUNDRED - running
    scaled.append(replace(last, percentage=residue if residue > ZERO else ZERO))
    return scaled


# ------------------------------------------------------------- batching


def scale_to_batch(
    components: list[Component],
    batch_mass_kg: Decimal | int | str,
    *,
    places: Decimal = Decimal("0.001"),
    tolerance: Decimal = Decimal("0.01"),
) -> dict[str, Decimal]:
    """Component masses for a batch, summing EXACTLY to the batch mass.

    THE INVARIANT THIS EXISTS FOR, from the source: *for any valid 100%
    formula and any positive batch quantity, the sum of component masses
    equals the batch mass.* Rounding each component independently breaks
    that — ten components rounded to the gram can drift several grams from
    the target, and a technician reconciling a weigh-up against the sheet
    then finds a discrepancy the software created.

    So every component but the last is rounded, and the last takes the
    remainder. The residue lands on ONE line, visibly, instead of being
    smeared invisibly across all of them.

    🔴 AN OFF-100% FORMULA IS REFUSED, NOT QUIETLY RENORMALISED.
    This divided by the ACTUAL total, so a formula stated at 98.5% produced
    masses for a 100% formula: a component written as 36.00% came out as
    9.137 kg of 25 kg, which is 36.55%. The stated percentage and the mass
    were then displayed in adjacent columns. That is exactly the invented
    discrepancy the paragraph above says this function exists to prevent —
    committed inside the same function that says so. Raised by the
    Supervisor, which reproduced it against the shipped draft version.

    A formula outside tolerance cannot be submitted (§8) and therefore has
    no business producing a weigh-up sheet. Normalise it deliberately with
    `normalize_to_100` first if that is what you mean.
    """
    _require(components)
    mass = _dec(batch_mass_kg, "batch_mass_kg")
    if mass <= ZERO:
        raise ValueError("batch mass must be positive")

    # DUPLICATE CODES ARE REFUSED, because the return type cannot represent
    # them. The result is keyed by material_code, so two lines for the same
    # material silently overwrote each other and the returned masses summed
    # to LESS than the batch — quietly breaking the one invariant this
    # function exists to guarantee, in the one case its property test never
    # generated (the generator makes unique codes). Raised by Codex.
    #
    # Refused rather than summed: two lines for one material is already a
    # DUPLICATE_COMPONENT submission blocker, so silently merging them here
    # would let a weigh-up be produced for a formula that cannot be
    # submitted.
    codes = [c.material_code for c in components]
    duplicates = sorted({code for code in codes if codes.count(code) > 1})
    if duplicates:
        raise ValueError(
            "cannot scale a formula with duplicated components: " + ", ".join(duplicates)
        )

    total = total_percentage(components)
    if total <= ZERO:
        raise ValueError("cannot scale a formula whose components total zero")
    if abs(total - HUNDRED) > tolerance:
        raise ValueError(
            f"cannot scale a formula totalling {total}% — outside the "
            f"±{tolerance}% tolerance around 100%. Normalise it first if that "
            f"is intended; scaling it silently would produce masses that "
            f"contradict the stated percentages."
        )

    # THE REMAINDER GOES ON THE LARGEST LINE, NOT THE LAST.
    #
    # The Supervisor offered two fixes for a remainder that can go negative:
    # clamp it, or move it to the largest line. Clamping was tried first and
    # is WRONG — Hypothesis found it immediately. Clamping a -0.001 residue
    # to zero makes the masses sum to 0.495 for a 0.494 kg batch, so it
    # trades a negative mass for a broken total: the one invariant this
    # function exists to guarantee, sacrificed to fix a cosmetic symptom of
    # the same underlying problem.
    #
    # The largest line is the one that can absorb a few rounding steps
    # without going anywhere near zero. It is chosen by percentage, not by
    # position, so the residue lands where it is proportionally smallest.
    largest = max(range(len(components)), key=lambda i: components[i].percentage)

    out: dict[str, Decimal] = {}
    running = ZERO
    for i, c in enumerate(components):
        if i == largest:
            continue
        part = (c.percentage / total * mass).quantize(places)
        out[c.material_code] = part
        running += part

    remainder = mass - running
    if remainder < ZERO:
        # Not reachable with any realistic batch, and refused rather than
        # fudged when it is. It means the batch is too small to express at
        # this precision across this many components — every line has
        # rounded up to the same step and their sum has overshot. Producing
        # a weigh-up here would mean printing either a negative mass or a
        # total that is not the batch, and both are worse than saying so.
        raise ValueError(
            f"a {mass} kg batch cannot be expressed to {places} across "
            f"{len(components)} components — the rounding residue exceeds the "
            f"batch. Use a larger batch or a finer precision."
        )
    out[components[largest].material_code] = remainder
    return out


# ---------------------------------------------------------- properties


def theoretical_density(components: list[Component]) -> Decimal:
    """Blend density in g/cm³, assuming volumes are additive.

    For a blend specified by MASS, volumes add and masses add, so

        1 / rho_blend = sum( w_i / rho_i )

    with `w_i` the mass fraction. A plain mass-weighted average of
    densities is the common mistake and is wrong in the other direction —
    it overstates the density of any blend containing a light filler, which
    is exactly the case this product exists to optimise.

    Volume additivity is an assumption, not a law: it ignores packing
    effects and air entrainment, which is why this is called THEORETICAL
    density and why `CLAUDE.md` rule 3 requires it to be displayed as
    calculated, never as measured.
    """
    _require(components)
    missing = [c.material_code for c in components if c.density_g_cm3 is None]
    if missing:
        raise ValueError(f"density unknown for: {', '.join(sorted(missing))}")

    total = total_percentage(components)
    if total <= ZERO:
        raise ValueError("cannot compute density for a formula totalling zero")

    inverse = ZERO
    for c in components:
        assert c.density_g_cm3 is not None  # noqa: S101 - narrowed above
        inverse += (c.percentage / total) / c.density_g_cm3
    if inverse <= ZERO:
        raise ValueError("degenerate density calculation")
    return HUNDRED / (inverse * HUNDRED)


def _mass_in_roles(components: list[Component], roles: frozenset[str]) -> Decimal:
    return sum((c.percentage for c in components if c.role in roles), start=ZERO)


BINDER_ROLES = frozenset({"resin", "binder", "hardener", "catalyst"})
FILLER_ROLES = frozenset({"filler", "extender", "pigment"})


def binder_to_filler_ratio(components: list[Component]) -> Decimal:
    """Binder mass divided by filler mass.

    Raises when there is no filler rather than returning infinity or zero:
    a ratio against nothing is not a number a chemist can act on, and a
    silent 0 would read as "no binder".
    """
    _require(components)
    binder = _mass_in_roles(components, BINDER_ROLES)
    filler = _mass_in_roles(components, FILLER_ROLES)
    if filler <= ZERO:
        raise ValueError("no filler in this formula — a binder:filler ratio is undefined")
    return binder / filler


def stoichiometric_hardener_parts(
    epoxy_equivalent_weight: Decimal | int | str,
    amine_hydrogen_equivalent_weight: Decimal | int | str,
) -> Decimal:
    """Parts of hardener per 100 parts of resin, by mass, at stoichiometry.

        parts = 100 * AHEW / EEW

    Both equivalent weights are grams per equivalent, so the ratio is
    dimensionless and the result is directly the phr figure a formulator
    writes on a datasheet.
    """
    eew = _dec(epoxy_equivalent_weight, "epoxy_equivalent_weight")
    ahew = _dec(amine_hydrogen_equivalent_weight, "amine_hydrogen_equivalent_weight")
    if eew <= ZERO or ahew <= ZERO:
        raise ValueError("equivalent weights must be positive")
    return HUNDRED * ahew / eew


def solids_content(components: list[Component]) -> Decimal:
    """Non-volatile content as a mass percentage of the whole formula.

    A component with no stated solids fraction is treated as **100% solid**
    only when it is also stated to have no VOC; otherwise it is an error.
    Assuming solidity for unknown data is how a coating's solids figure
    ends up flattering itself.
    """
    _require(components)
    total = total_percentage(components)
    if total <= ZERO:
        raise ValueError("cannot compute solids for a formula totalling zero")

    unknown = [
        c.material_code for c in components if c.solids_fraction is None and c.voc_fraction is None
    ]
    if unknown:
        raise ValueError("solids fraction unknown for: " + ", ".join(sorted(unknown)))

    solids = ZERO
    for c in components:
        fraction = c.solids_fraction
        if fraction is None:
            # Stated VOC but no stated solids: the non-volatile remainder.
            assert c.voc_fraction is not None  # noqa: S101 - narrowed above
            fraction = Decimal("1") - c.voc_fraction
        solids += c.percentage / total * fraction
    return solids * HUNDRED


def voc_content_g_per_l(components: list[Component]) -> Decimal:
    """Volatile organic content in grams per litre of the blend.

    VOC is regulated per unit VOLUME, so the blend density is required —
    a mass fraction alone cannot answer the question a regulator asks.

        g/L = voc_mass_fraction * rho_blend(g/cm3) * 1000
    """
    _require(components)
    total = total_percentage(components)
    if total <= ZERO:
        raise ValueError("cannot compute VOC for a formula totalling zero")

    unknown = [c.material_code for c in components if c.voc_fraction is None]
    if unknown:
        raise ValueError("VOC fraction unknown for: " + ", ".join(sorted(unknown)))

    voc_fraction = ZERO
    for c in components:
        assert c.voc_fraction is not None  # noqa: S101 - narrowed above
        voc_fraction += c.percentage / total * c.voc_fraction

    density = theoretical_density(components)
    return voc_fraction * density * Decimal("1000")


def cost_per_kg(components: list[Component]) -> Decimal:
    """Raw-material cost of one kilogram of the formula.

    Raw material only. It is deliberately NOT called `cost`, because a
    figure labelled that would be read as a landed cost including labour,
    energy, packaging and yield loss — and would be wrong by a wide margin.
    """
    _require(components)
    total = total_percentage(components)
    if total <= ZERO:
        raise ValueError("cannot compute cost for a formula totalling zero")

    unknown = [c.material_code for c in components if c.cost_per_kg is None]
    if unknown:
        raise ValueError("cost unknown for: " + ", ".join(sorted(unknown)))

    cost = ZERO
    for c in components:
        assert c.cost_per_kg is not None  # noqa: S101 - narrowed above
        cost += c.percentage / total * c.cost_per_kg
    return cost
