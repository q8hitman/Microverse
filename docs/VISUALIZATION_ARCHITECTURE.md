# Visualization architecture (v0.5)

The microscope must show what the model computed, continuously, with no fake dynamics.
The models compute **biomass per litre**, not individuals, so every drawn organism is a
**representative of a cohort**. The UI says so: the legend gives a sample factor, the footer says
"each drawn cell represents a cohort", and the inspector says how many cells per mL one drawn cell represents.

```
Trajectory ──state_at(t)──► Specimen ──targets──► VisualPopulation (per species, per field)
 (solver rows)  (linear       (fields,             • persistent Agent ids, positions, velocities
                interpolation) fixed sample        • reconcile(target): division / lysis / grazing /
                               factor per run)       leaving / entering — nothing appears from nowhere
                                                   • motion by motility type (real time)
                                                   • separation (cells are solid)
                     ▲                                     │
       Workspace: QElapsedTimer dt, playback speed,        ▼
       pause, replay, slider          SpecimenView + specimen_paint (Qt): morphology, 3 modes,
                                      zoom/pan, inspector, overlays, legend, scale bar
```

## Modules

| File | Role | Qt? |
|---|---|---|
| `core/trajectory.py` | `Trajectory.state_at(t)`: linear interpolation between solver output rows (rendering only) | no |
| `library/morphology.py` | `MorphSpec` for all 30 organisms: shape, dimensions, arrangement, chain length, motility, speed, division style, features, size variation, colour, provenance and reference | no |
| `viz/population.py` | `Agent` and `VisualPopulation`: identities, transitions, motion, separation | no |
| `viz/specimen.py` | `Specimen` and `Track`: fields, sample factor, predator lists, inspection, modes | no |
| `viz/scene.py`, `viz/yogurt_scene.py`, `viz/community_scene.py` | Lab-specific specimens (which variable → which species, which field) | no |
| `ui/specimen_paint.py` | Procedural drawing of each shape, its division stage and its lysis, in three looks | yes |
| `ui/specimen_view.py` | Shared widget: panels, legend, zoom/pan, click-to-inspect, overlays, scale bar | yes |
| `ui/microscope_widget.py`, `ui/yogurt_widget.py`, `ui/community_widget.py` | Side panels (chemostat vessel, milk jar and pH meter, community vessel) | yes |

## Rules

1. **Identity.** Each agent keeps its id for its whole life. In a division the mother keeps her id and
   the daughters get new ids with `parent` set. There is no other way to make a new agent, except
   `ENTERING` from outside the field when the species has no cell in view (drifting or swimming in).
2. **Counts follow the model through biology.** Every frame: `gap = target − (counted cells + divisions
   already under way)`.
   * If the gap is positive, mature cells start dividing, each in its species' style.
   * If it is negative, cells are lost: eaten by the nearest visible predator (if one can eat them),
     swimming out of view (motile cells near the edge), or lysing (swelling, then fading). In chains, the
     last cell lyses.
   * A hysteresis of ±0.75 cells prevents flicker around a fractional target.
3. **Speed.** A division never takes longer than 0.6 × the population's current doubling time
   (estimated from the smoothed d ln(target)/dt). At high playback speed transitions therefore shorten
   (to at least 0.1 s) instead of falling behind, and in-progress divisions are re-timed.
4. **Two clocks.** Biology follows simulation time; motion uses real time (`motion_scale`: real, ½, ¼,
   still). While paused the target is constant, so nothing new is born or dies. Transitions already needed
   are finished, so a slider jump settles in about a second and then stays still.
5. **One sample factor per run.** It is chosen once from the peak of the whole trajectory (a power of 2,
   so the peak fills about 85 % of the drawing budget). Drawn counts are therefore proportional to modelled
   density at every moment, and early phases of a run can show few cells, honestly.
6. **No teleporting.** Walls reflect (coverslip edges). Separation pushes overlapping cells apart, and
   non-motile daughters drift apart over about 3 s, like a mixed sample.

## Reproduction styles (`MorphSpec.division`)

| Style | Organisms | What is drawn |
|---|---|---|
| binary fission | E. coli, L. bulgaricus, Pseudomonas, Synechococcus, Halobacterium… | rod elongates to ≈1.5×, constricts in the middle, two daughters |
| chain fission | S. thermophilus, Lactococcus, Leuconostoc, L. plantarum, Bacillus, Acetobacter, Azotobacter | cells of a chain divide together; chain breaks above its typical length, with no drawn cell moving |
| packet fission | Methanosarcina | packets in alternating planes |
| budding | S. cerevisiae, K. lactis | bud grows at a pole to ≈⅔, then separates |
| autospores | Chlorella | mother swells, 2–4 autospores appear inside, then are released |
| coenobium | Scenedesmus | a daughter colony forms beside the mother colony |
| diatom valve | Navicula | split along the valve plane; daughter 3 % smaller (MacDonald–Pfitzer rule) |
| transverse fission | Tetrahymena, Paramecium | front and back halves pinch apart |
| longitudinal fission | Euglena, Vorticella | splits along the length |
| amoeboid fission | Amoeba | pseudopodia retract, the cell rounds up and pinches into two |
| parthenogenesis | Brachionus, Philodina | egg grows on the female, then a small juvenile appears behind her |
| hyphal extension | Aspergillus, Penicillium, Rhizopus | a new branch starts behind the tip and extends; hyphae never move |

## Movement styles (`MorphSpec.motility`)

| Style | Organisms | Model |
|---|---|---|
| none | most cocci, yeasts, algae | Brownian motion (Stokes–Einstein, D = 0.22/r µm²/s), plus drift after division |
| run & tumble | E. coli, B. subtilis | runs ≈1 s at 25 µm/s, tumbles ≈0.12 s with large reorientation (Berg 2004) |
| run & reverse | P. putida | runs ≈1.5 s, reversals of ≈180° |
| slow swim | Acetobacter, Azotobacter, Halobacterium | weak, wandering swimming |
| ciliary | Tetrahymena, Paramecium | fast, constant turning (helical path in 2-D), metachronal cilia |
| flagellar | Euglena | forward, with a side-to-side wobble; metaboly |
| amoeboid | Amoeba | ≈2 µm/s, very persistent direction, pseudopodia |
| gliding | Navicula | back and forth along the long axis, reversing every 8–20 s |
| sessile | Vorticella | anchored stalk that contracts every 8–25 s |
| corona / creeping | Brachionus / Philodina | swimming with wide turns / creep-and-pause |
| hyphal | moulds | no movement |

Velocities relax towards the target direction, so there are no instantaneous jumps in motion.

## Display modes (same state, three looks)

* **Realistic**: brightfield background with vignetting and natural colours. Internal structures: chloroplasts,
  pyrenoid, eyespot, macronucleus, pulsing contractile vacuoles, food vacuoles, diatom raphe and striae,
  rotifer corona, mastax and gut, yeast vacuole and bud scars, fungal conidiophores, penicillus and sporangia.
* **Microscope**: phase contrast (dark cells with bright halos). The yoghurt lab shows a Gram stain instead
  (both species Gram-positive, purple).
* **Explanation overlays**: dividing cells ringed green, dying or leaving cells ringed red, grazing drawn as a
  line to the predator. Bacterial flagella appear **only** here, labelled schematic, because at ≈20 nm
  wide they are invisible in light microscopy.

## Interaction

The mouse wheel zooms (1–12×) around the pointer and dragging pans. A double-click resets the view, and the
scale bar adapts to the zoom. Clicking an organism opens the inspector: species, unit id, state and
progress, length, cells per chain, cells per mL it represents, motility, division style and shape source.

## Performance (measured on the development PC, Python 3.12)

| | v0.4 scene update | v0.5 scene update | v0.5 paint (one frame) |
|---|---|---|---|
| Chemostat (≈200 drawn) | 0.08 ms | 0.8 ms | 4.6 ms |
| Yoghurt | 0.05 ms | 0.2 ms | 1.9 ms |
| Community, 5 species | 0.19 ms | 2.1 ms | 3.9 ms |

All of this is well inside the 33 ms frame budget at 30 fps, and a test enforces a scene update below 8 ms.
Drawing is capped (260 small and 60 large units per species). Separation uses vectorised NumPy and costs
O(n²) per species, which is fine at these caps. If populations of thousands are ever drawn, add a spatial
grid there first.

## Known limitations

* Positions, paths and the exact timing of each division are illustrative. Only the **number** of drawn cells
  (× sample factor) is model output.
* Spatial structure is not modelled (well-mixed models), so clusters seen on screen are not predictions.
* Predation across fields is shown as a **visiting grazer**: while a small-field prey population is falling and
  its predator (from the large field) is present, one predator swims across the 100× field (slowed to ¼ speed)
  and nearby prey are drawn into it. The visitor is not counted and is labelled "summary of grazing" in the
  Explanation mode. Prey far from any mouth are lost by lysis or by leaving the view instead.
* Bacterial endospores, gas vesicles and capsules are drawn only where noted; sporulation is not modelled.
