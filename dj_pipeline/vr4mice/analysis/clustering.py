import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.decomposition import PCA
import umap

import analysis.visual_discrim_functions as vs


def interpolate_data(df, n_points=200):
    
    return vs.interpolate(df, n_points=n_points, value_columns=["y", "x", "norm_x", "norm_y", "velocity", "head_dir",
                                                              "aperture", "trial_R_choice", "trial_length", 
                                                              "trial_rewarded", "trial_tortuosity", "trial_traj_path_length",
                                                              "trial_init_x", "trial_end_x", "trial_init_y"])
    
    
def cluster(res, method: str = "pca", return_data =False):
    """Compute dimensionality reduction using the method provided.
    
    NOTE(celia): to later refactorize, really ugly;

    Args:
        res: Interpolated data. All trials have the same size.
        method: The dimensionality reduction algorithm to use (either pca or umap for now)

    Returns:
        the latents computed with the required `method`.
    """
    
    data_x = np.concatenate(res.groupby(["mouse_name", "date", "attempt", "trial" ]).norm_x.apply(np.array).values).reshape(-1,200)
    data_y = np.concatenate(res.groupby(["mouse_name", "date", "attempt", "trial"]).norm_y.apply(np.array).values).reshape(-1,200)
    data_head_dir = np.concatenate(res.groupby(["mouse_name", "date", "attempt", "trial"]).head_dir.apply(np.array).values).reshape(-1,200)
    velocity = np.concatenate(res.groupby(["mouse_name", "date", "attempt", "trial"]).velocity.apply(np.array).values).reshape(-1,200)

    data = np.concatenate([data_x, data_y], axis=1) #NOTE(celia): to adapt based on the data to include
    
    if method == "umap":
        standard_embedding = umap.UMAP(random_state=42,n_neighbors=30, min_dist=0).fit_transform(data)
    elif method == "pca":
        pca = PCA(n_components=2)
        standard_embedding = pca.fit_transform(data)
        #print(pca.explained_variance_ratio_)
    else: 
        raise NotImplementedError(f"{method}")
    if return_data == True:
        return data
    else:
        return standard_embedding



def plot_clustering(df,
                    method: str = "pca",
                    colors=["Set1", "cool", "cool", "viridis"], 
                    axes_labels = ["choice", "init_x", "init_y", "tortuosity"],
                    method_name="PC"):
    """Plot the results of the clustering used to compute standard_embedding and color per labels.

    Args:
        standard_embedding: the latent components computed with the dimensionality reduction
            algorithm of the users choice (see in `clustering.py`).
        labels: List of labels, to use for coloring the embedding, the function will create one plot
            per element of the `labels` list.
        colors: List of colormap, associated to each labels.
        axes_labels: List of names of each labels.

    Returns:
        The figure with `len(labels)` axes. 
    """
    # Interpolate data and compute the dimensionality reduction
    res = interpolate_data(df)
    standard_embedding = cluster(res, method=method)
    
    # Compute labels
    #NOTE(celia): to modularize later... super ugly
    trial_tortuosity = res.groupby(["mouse_name", "date", "attempt", "trial"]).trial_tortuosity.apply("first").values
    trial_rewarded = res.groupby(["mouse_name", "date", "attempt", "trial"]).trial_rewarded.apply("first").values
    trial_length = res.groupby(["mouse_name", "date", "attempt", "trial"]).trial_length.apply("first").values

    res["mouse_id"] = pd.factorize(res["mouse_name"])[0]
    mouse_id = res.groupby(["mouse_name", "date", "attempt", "trial"]).mouse_id.apply("first").values
    trial_id = res.groupby(["mouse_name", "date", "attempt", "trial"]).trial.apply("first").values
    trial_R_choice = res.groupby(["mouse_name", "date", "attempt", "trial"]).trial_R_choice.apply("first").values
    aperture = res.groupby(["mouse_name", "date", "attempt", "trial"]).aperture.apply("first").values
    trial_init_x = res.groupby(["mouse_name", "date", "attempt", "trial"]).trial_init_x.apply("first").values
    trial_init_y = res.groupby(["mouse_name", "date", "attempt", "trial"]).trial_init_y.apply("first").values
    trial_end_x = res.groupby(["mouse_name", "date", "attempt", "trial"]).trial_end_x.apply("first").values
    head_dir = res.groupby(["mouse_name", "date", "attempt", "trial"]).head_dir.apply("first").values

    res["date_id"] = pd.factorize(res["date"])[0]
    date_id = res.groupby(["mouse_name", "date", "attempt", "trial"]).date_id.apply("first").values

    labels = [trial_R_choice, trial_init_x, trial_init_y, trial_tortuosity] #NOTE(celia): can change that accordingly
    
    # Create the figure
    fig, axes = plt.subplots(1,len(labels),figsize=(20, 5))
    axes = axes.flatten()

    for i in range(len(labels)):
        # trial_R_choice, trial_init_x, trial_init_y, trial_length
        axes[i].scatter(standard_embedding[:, 0], standard_embedding[:, 1], c=labels[i], s=0.3, cmap=colors[i])

        axes[i].set_title(axes_labels[i])
        axes[i].set_xlabel(f"{method_name}1")
        axes[i].set_ylabel(f"{method_name}2")

    #plt.savefig("umpa.svg")
    #plt.show()
    
    return fig