import numpy as np
import pandas as pd
import seaborn as sns


def tukey_results_to_matrix(results):
    """
    Convert Tukey HSD test results into a symmetric matrix of p-values.

    Parameters:
    -----------
    results : statsmodels TukeyHSDResults object
        The results object from pairwise_tukeyhsd()

    Returns:
    --------
    tuple: (p_df, mask)
        p_df: DataFrame of p-values with group labels
        mask: Boolean mask for upper triangle (for visualization)
    """
    # Extract summary data (skip header row)
    summary_data = results._results_table.data[1:]

    # Get unique groups
    groups = np.unique(results.groupsunique)
    n_groups = len(groups)

    # Create matrix of ones (default p-value=1 for identical groups)
    p_matrix = np.ones((n_groups, n_groups))

    # Fill matrix with p-values from results
    for row in summary_data:
        group1, group2, p_value = row[0], row[1], row[3]

        i = np.where(groups == group1)[0][0]
        j = np.where(groups == group2)[0][0]

        p_matrix[i, j] = p_value
        p_matrix[j, i] = p_value  # Make symmetric

    # Create mask for upper triangle
    mask = np.triu(np.ones_like(p_matrix, dtype=bool))

    # Create labeled DataFrame
    p_df = pd.DataFrame(p_matrix, index=groups, columns=groups)

    return p_df, mask


def plot_training_stats_heatmap(ax, results):
    p_df, mask = tukey_results_to_matrix(results)

    # Plot heatmap
    sns.heatmap(
        p_df,
        mask=mask,
        annot=True,
        fmt=".3f",
        cmap="viridis_r",
        vmin=0,
        vmax=0.05,
        linewidths=0.5,
        cbar_kws={"label": "p-value"},
        ax=ax,
    )
    stage_positions = np.arange(6) + 0.5
    stage_labels = ["First", "Middle", "Last", "First", "Middle", "Last"]
    stage_colors = ["#3FB47C", "#3FB47C", "#1F6F49", "#FF1493", "#FF1493", "#FF1493"]

    ax.set_xticks(stage_positions)
    ax.set_xticklabels(stage_labels, rotation=0, fontsize=12)
    ax.set_yticks(stage_positions)
    ax.set_yticklabels(stage_labels, rotation=0, fontsize=12)
    for i, label in enumerate(ax.get_yticklabels()):
        label.set_color(stage_colors[i])
    for j, label in enumerate(ax.get_xticklabels()):
        label.set_color(stage_colors[j])
