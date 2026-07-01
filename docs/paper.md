# Benquet, Sainsbury *et al.*

## Visual uncertainty & task demands shape active sensing strategies in mice

This page collects the figure notebooks, supplementary videos, and reproducibility resources for the paper.

## 📝 Citation

Benquet C*, Sainsbury T*, Bruneau L, Lin Y, Cai C, Popova M, Ponder K, Ntanavara L, Froebe R, Tan Z, Fahey P, Franke K, Franco LM, Jones K, Chen Y, Keller R, Pitkow X, Niell CM, Tolias AS, Mathis MW. [Visual uncertainty and task demands shape active sensing strategies in mice.](https://www.cell.com/current-biology/fulltext/S0960-9822(26)00722-0?) *Current Biology*. 20 July 2026. DOI: [10.1016/j.cub.2026.06.011](https://doi.org/10.1016/j.cub.2026.06.011).

## ✨ Highlights

- Mice perform active visual sensing in a free-range virtual reality-based object discrimination task.
- Mice perform infotaxis and select the correct object under variable visibility conditions.
- Trial-by-trial decisions can be decoded from head-body movements and speed, reflecting sensitivity to object occlusion (aperture width).

## 💾 Data Availability and Reproducibility

All figures are generated from the VR4Mice DataJoint database. To reproduce them, first connect to the local database and then run the notebooks. Then, we provide the necessary code for deploying a local copy of our database and reproducing the paper figures and related analyses. 

🔗 Public data release on [Zenodo](https://zenodo.org/uploads/19091270)

To reproduce the figure notebooks end-to-end:

1. Download the database archive from the [Zenodo record](https://zenodo.org/uploads/19091270).
2. Install and configure the DJ pipeline following {ref}`our installation guide <sec:import-sql-dump>`.
3. Run the figure notebooks listed below in order, after the database connection and fetch steps are complete.

## 📊 List of Paper Figures

We provide reference code for plotting all paper figures here. Note that for the paper version, some panels may have been post-processed for the manuscript layout, and the figures might differ in minor typographic details.

```{tableofcontents}
```

## 🎬 Supplementary Videos

The videos below show representative sessions from the supplementary material.

<div style="display: flex; flex-wrap: wrap; gap: 1.5rem; align-items: flex-start; margin-top: 1rem;">
  <figure style="flex: 1 1 360px; min-width: 280px; margin: 0;">
    <video controls playsinline preload="metadata" style="width: 100%; height: auto; display: block; border-radius: 0.5rem; background: #000;">
      <source src="../_static/videos/Video%20S1.mp4" type="video/mp4">
      Your browser does not support the video tag.
    </video>
    <figcaption style="margin-top: 0.75rem;">
      <strong>Video S1. Dual-occlusion session example.</strong><br>
      Left: arena top view; Right: back view. Video playback speed: 0.3&times;.
    </figcaption>
  </figure>

  <figure style="flex: 1 1 360px; min-width: 280px; margin: 0;">
    <video controls playsinline preload="metadata" style="width: 100%; height: auto; display: block; border-radius: 0.5rem; background: #000;">
      <source src="../_static/videos/Video%20S2.mp4" type="video/mp4">
      Your browser does not support the video tag.
    </video>
    <figcaption style="margin-top: 0.75rem;">
      <strong>Video S2. Multi-occlusion session example, related to the multi-occlusion figure.</strong><br>
      Left: arena top view; Right: back view. Video playback speed: 0.3&times;.
    </figcaption>
  </figure>
</div>
