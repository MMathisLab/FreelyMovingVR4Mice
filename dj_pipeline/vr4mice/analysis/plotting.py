import matplotlib.pyplot as plt


def plot_box_rectangle(df_box, box_label, edgecolor='#009B9E', fill=False, alpha=0.6, linewidth=4):
    return plt.Rectangle((df_box[f"{box_label}_box_x_min"], df_box[f"{box_label}_box_z_min"]),
                                abs(df_box[f"{box_label}_box_x_min"] - df_box[f"{box_label}_box_x_max"]), 
                                abs(df_box[f"{box_label}_box_z_min"] - df_box[f"{box_label}_box_z_max"]), 
                                fill=fill, linewidth=linewidth, 
                                edgecolor=edgecolor, alpha=alpha)
    
    
def plot_all_boxes(ax, df_box):
    """ Visualise boxes on tajectory plots."""
    
    start_box = plot_box_rectangle(df_box, box_label="tt", edgecolor='#009B9E')
    left_box = plot_box_rectangle(df_box, box_label="left", edgecolor='#5C0A72')
    right_box = plot_box_rectangle(df_box, box_label="right", edgecolor='#FD672C')
    
    ax.add_patch(start_box)
    ax.add_patch(left_box)
    ax.add_patch(right_box)
    ax.set_xlim(-28, 28)
    ax.set_ylim(-28, 28)
