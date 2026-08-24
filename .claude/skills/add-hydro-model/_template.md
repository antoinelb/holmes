# <!-- Replace with full model name, e.g. "HYMOD Model" --> Model

<!--
  CANONICAL TEMPLATE for docs/concepts/hydro/<name>.md

  This is the single source of truth for the hydro concept-page schema.
  When the add-hydro-model skill creates a new page, it copies this file
  into docs/concepts/hydro/<name>.md and fills in the placeholders.

  Lives under .claude/skills/ (not docs/) so MkDocs never publishes it and
  students never see an empty stub.

  Six required sections, in order:
    1. Overview
    2. Key Concepts
    3. How It Works
    4. Parameters
    5. Mathematical Formulation
    6. References

  Writing style:
  - Prose at undergraduate level — this is course material, not API reference.
  - Equations use MathJax: $...$ inline, $$...$$ block.
  - Variable notation must match Perrin's thesis annex (X_1, X_2, S, R, etc.),
    NOT HOOPLA Matlab names (HM16_x(1)).
  - Parameter bounds must match the BOUNDS constant in the Rust source file
    (src/holmes-rs/src/hydro/<name>.rs). They are code-authoritative; docs
    follow the code.
-->

## Overview

<!--
  2-4 short paragraphs. Cover:
  - Full name, origin, developer, typical use case.
  - Structural summary in one sentence ("represents a catchment as N reservoirs
    connected by X").
  - Why a student might choose this model over others (parsimony? explicit
    process representation? historical significance?).
-->

## Key Concepts

<!--
  5-8 bullet points defining the vocabulary a student needs to read the rest
  of the page. Each bullet is one term in **bold** followed by a one-sentence
  plain-language definition. Avoid equations here — save them for the
  Mathematical Formulation section.

  Typical terms: the reservoirs (soil store, routing store, groundwater store),
  the key physical processes (percolation, saturation excess, recession), and
  any model-specific abstractions (unit hydrographs, sigmoid splits, etc.).
-->

- **Term**: Definition.
- **Term**: Definition.

## How It Works

<!--
  Narrative walk-through of one time step, in 5-7 numbered "Step N" paragraphs.
  Each step references the parameters by symbol (X_1, X_2, ...) so the reader
  can link the prose to the Parameters table below. Keep each step to 2-4
  sentences — save the equations for the Mathematical Formulation section.

  Standard step sequence for most hydro models:
    1. Net inputs (wet vs. dry determination)
    2. Production / soil-moisture accounting
    3. Percolation or infiltration split
    4. Flow partitioning between pathways
    5. Routing (unit hydrograph or linear reservoir or ...)
    6. Groundwater exchange (if applicable)
    7. Total streamflow assembly
-->

**Step 1: <title>**. Description.

**Step 2: <title>**. Description.

## Parameters

<!--
  Markdown table with EXACTLY these columns in this order:
    Parameter | Description | Range | Units | Physical Interpretation
  The Range column must match the BOUNDS constant in the Rust source file.
  Units are "mm", "days", "-" (dimensionless), or "mm/day" — avoid prose.

  After the table, include 3-5 "Understanding the parameters" bullets giving
  practical calibration guidance ("X_1 is usually 100-500 mm", "X_3 controls
  recession", etc.). This is where the student learns what to expect during
  manual calibration, and is the most pedagogically valuable part of the page.
-->

The <model name> has N calibratable parameters:

| Parameter | Description | Range | Units | Physical Interpretation |
|-----------|-------------|-------|-------|------------------------|
| $X_1$ |  |  |  |  |
| $X_2$ |  |  |  |  |

**Understanding the parameters:**

-
-
-

## Mathematical Formulation

<!--
  The rigorous reference section. Structure as subsections:
    - Initialization (starting reservoir states)
    - Net precipitation / PET (partitioning)
    - One subsection per reservoir or process (e.g. "Soil Store", "Routing Store")
    - Unit hydrographs (if any)
    - Total streamflow

  All equations in $$...$$ blocks. Use \leftarrow for state updates. Use
  \max(\cdot, 0) explicitly — don't leave positivity constraints implicit.
  Use the same symbols as the Parameters table ($X_1$, etc.), not Matlab
  indexing.
-->

### Initialization

$$S_0 = \frac{X_1}{2}$$

### <Process Name>

$$<equation>$$

### Total Streamflow

$$Q = \ldots$$

## References

<!--
  Primary citation is almost always Perrin's thesis (already in the repo at
  perrin/these_annexe.pdf) plus the original model paper if different. Use
  APA-style full citations with DOI links where available.

  If the model has a widely-cited implementation paper (e.g. for GR4J the 2003
  Perrin paper), cite that too. Two or three references is typical — don't
  turn this into a bibliography.
-->

- Author, A. (YEAR). *Title*. Journal, Volume(Issue), pages. [DOI](https://doi.org/...)
- Perrin, C. (2000). *Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative* (PhD thesis). INPG, Grenoble.
