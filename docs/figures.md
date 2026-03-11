# Figures

This section provides reference notebooks for figures and analyses from the paper:

**Visual uncertainty and task demands shape active sensing strategies in mice**

## Authors

Célia Benquet*, Thomas Sainsbury*, Léo Bruneau, Yang Lin, Chenchen Cai, Mariia Popova, Kayla Ponder, Lydia Ntanavara, Rachel Froebe, Zheng Tan, Paul Fahey, Katrin Franke, Luis M. Franco, Keaton Jones, Yizhou Chen, Reece Keller, Xaq Pitkow, Cristopher M. Niell, Andreas S. Tolias, Mackenzie Weygandt Mathis

\* Equal contribution.

## Highlights

- Mice perform active visual sensing in a free-range virtual reality-based object discrimination task.
- Mice perform infotaxis and select the correct object under variable visibility conditions.
- Trial-by-trial decisions can be decoded from head-body movements and speed, reflecting sensitivity to object occlusion (aperture width).

## Summary

In natural environments, animals actively sample visual information to guide behavior. Sensory feedback is dynamic and often requires active movement, whether scanning this page with saccades or walking through a cluttered environment. Although mice have relatively low-acuity vision, they still rely on sight for critical behaviors including navigation and prey capture.

This work introduces a virtual reality object discrimination task to study visual decision-making under naturalistic conditions. The results show that mice perform infotaxis by actively seeking informative viewpoints to guide choices, and that this strategy is modulated by the amount of available visual information. Together, these findings indicate that mice use principled active strategies to resolve visual uncertainty, highlighting a key role for information-seeking in natural vision.

## Data Availability and Reproducibility

In this section, we provide reference code for reproducing the paper figures and related analyses. All figures are generated from the VR4Mice DataJoint (DJ) database.

The notebooks are not offline by default: they query database tables at runtime.

*Public data release: Zotero dataset link coming soon.*

To reproduce the figure notebooks end-to-end:

1. Download the database data on Zotero.
2. Install and configure the DJ pipeline following our guidelines.
3. Run the figure notebooks listed below in order, after the database connection and fetch steps are complete.

You can run notebooks locally if your local environment can connect to the DJ database (either a local database deployment or a remote server with credentials). Without database access, the notebooks will fail.

## List of Paper Figures

We provide reference code for plotting all paper figures here. Note that for the paper version, panels might have been post-edited, and the figures might differ in minor typographic details.

```{tableofcontents}
```