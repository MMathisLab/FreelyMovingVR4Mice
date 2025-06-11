import numpy as np
import pandas as pd
import seaborn as sns
import itertools
from scipy.stats import ttest_rel, ttest_ind
import scipy.stats as stats


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


def get_p_values_multi(mean_mouse, x_var = "trial_length", y_var ="velocity"):
   
    p_values = []
    for bin_val in mean_mouse[x_var].unique():
        bin_data = mean_mouse[mean_mouse[x_var] == bin_val]
        apertures = bin_data['aperture'].unique()
        
        # Get all unique pairs of apertures
        for ap1, ap2 in itertools.combinations(apertures, 2):
            ap1_data = bin_data[bin_data['aperture'] == ap1][y_var]
            ap2_data = bin_data[bin_data['aperture'] == ap2][y_var]
            
            t_stat, p_val = ttest_rel(ap1_data, ap2_data)
            #print(f"Bin {bin_val}: Aperture {ap1} vs {ap2} - t = {t_stat:.3f}, p = {p_val:.4f}")
            p_values.append(pd.DataFrame({
                "bin": bin_val,
                "aperture1": ap1,
                "aperture2": ap2,
                "p_value": p_val
            }, index=[0]))
            
    p_value_df=pd.concat(p_values)
    p_value_df["p_value_corr"] = stats.false_discovery_control(p_value_df.p_value)
    return(p_value_df)


def get_multi_performance_p_val(trial_df, y_var):
    mean_mouse = trial_df.groupby(["dataset", "aperture"], as_index=False).mean()
    p_values =[]
    for ap1, ap2 in itertools.combinations(mean_mouse.aperture.unique(), 2):
        ap1_data = mean_mouse[mean_mouse['aperture'] == ap1][y_var]
        ap2_data = mean_mouse[mean_mouse['aperture'] == ap2][y_var]
            
        t_stat, p_val = ttest_rel(ap1_data, ap2_data)
        #print(f"Bin {bin_val}: Aperture {ap1} vs {ap2} - t = {t_stat:.3f}, p = {p_val:.4f}")
        p_values.append(pd.DataFrame({
            "aperture1": ap1,
            "aperture2": ap2,
            "p_value": p_val
        }, index=[0]))
    p_value_df=pd.concat(p_values)
    p_value_df["p_value_corr"] = stats.false_discovery_control(p_value_df.p_value)
    return p_value_df
            
            
            
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

def plot_aperture_heatmap(
    df, 
    value_col="p_value",  # Choose "p_value" or "p_value_corr"
    title="Aperture Comparison Heatmap",
    cmap="viridis_r",     # Color map (low values = dark)
    annot=True,           # Show values in cells
    fmt=".1e",            # Scientific notation for annotations
    figsize=(8, 6),
    symmetric=True,       # Mirror values for symmetry
    cbar_label="p-value",
    mask_nan=True,        # Hide NaN values
    linewidths=0.5        # Border width for cells
):
    """
    Plots a heatmap of aperture comparisons using p-values or corrected p-values.
    
    Parameters:
        df (pd.DataFrame): Input DataFrame with columns: aperture1, aperture2, p_value, p_value_corr.
        value_col (str): Column to plot ("p_value" or "p_value_corr").
        title (str): Plot title.
        cmap (str): Matplotlib/seaborn colormap.
        annot (bool): Whether to annotate cells with values.
        fmt (str): Format string for annotations (e.g., ".1e" for scientific notation).
        figsize (tuple): Figure size (width, height).
        symmetric (bool): If True, mirrors values to make the heatmap symmetric.
        cbar_label (str): Label for the colorbar.
        mask_nan (bool): If True, hides NaN values.
        linewidths (float): Width of cell borders.
    """
    # Get unique apertures and initialize matrix
    apertures = sorted(set(df['aperture1'].unique()).union(df['aperture2'].unique()))
    matrix = pd.DataFrame(np.nan, index=apertures, columns=apertures)
    
    # Fill the matrix
    for _, row in df.iterrows():
        a1, a2, value = row['aperture1'], row['aperture2'], row[value_col]
        matrix.loc[a1, a2] = value
        if symmetric:
            matrix.loc[a2, a1] = value  # Mirror for symmetry
    
    # Plot
    plt.figure(figsize=figsize)
    sns.heatmap(
        matrix,
        annot=annot,
        fmt=fmt,
        cmap=cmap,
        cbar_kws={'label': cbar_label},
        mask=matrix.isna() if mask_nan else None,
        linewidths=linewidths
    )
    plt.title(title)
    plt.xlabel("Aperture 2")
    plt.ylabel("Aperture 1")
    plt.show()
        
       
    