import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import plotly.graph_objects as go


def _sensitivity_contour_plot(x,
                              y,
                              contour_values,
                              unadjusted_value,
                              scenario_x,
                              scenario_y,
                              scenario_value,
                              include_scenario,
                              benchmarks=None,
                              fill=True):

    if fill:
        text_col = 'white'
        contours_coloring = 'heatmap'
    else:
        text_col = 'black'
        contours_coloring = 'lines'

    # create figure
    axis_names = ['cf_d', 'cf_y ', 'Bound']
    fig = go.Figure()
    # basic contour plot
    hov_temp = axis_names[0] + ': %{x:.3f}' + '<br>' + axis_names[1] + ': %{y:.3f}' + '</b>' +\
        '<br>' + axis_names[2]
    fig.add_trace(go.Contour(z=contour_values,
                             x=x,
                             y=y,
                             hovertemplate=hov_temp + ': %{z:.3f}' + '</b>',
                             contours=dict(coloring=contours_coloring,
                                           showlabels=True,
                                           labelfont=dict(size=12, color=text_col)),
                             name='Contour'))

    if include_scenario:
        fig.add_trace(go.Scatter(x=[scenario_x],
                                 y=[scenario_y],
                                 mode="markers+text",
                                 marker=dict(size=10, color='red', line=dict(width=2, color=text_col)),
                                 hovertemplate=hov_temp + f': {round(scenario_value, 3)}' + '</b>',
                                 name='Scenario',
                                 textfont=dict(color=text_col, size=14),
                                 text=['<b>Scenario</b>'],
                                 textposition="top right",
                                 showlegend=False))

    # add unadjusted
    fig.add_trace(go.Scatter(x=[0],
                             y=[0],
                             mode="markers+text",
                             marker=dict(size=10, color='red', line=dict(width=2, color=text_col)),
                             hovertemplate=hov_temp + f': {round(unadjusted_value, 3)}' + '</b>',
                             name='Unadjusted',
                             text=['<b>Unadjusted</b>'],
                             textfont=dict(color=text_col, size=14),
                             textposition="top right",
                             showlegend=False))

    # add benchmarks
    if benchmarks is not None:
        fig.add_trace(go.Scatter(x=benchmarks['cf_d'],
                                 y=benchmarks['cf_y'],
                                 customdata=benchmarks['value'].reshape(-1, 1),
                                 mode="markers+text",
                                 marker=dict(size=10, color='red', line=dict(width=2, color=text_col)),
                                 hovertemplate=hov_temp + ': %{customdata[0]:.3f}' + '</b>',
                                 name="Benchmarks",
                                 textfont=dict(color=text_col, size=14),
                                 text=list(map(lambda s: "<b>" + s + "</b>", benchmarks['name'])),
                                 textposition="top right",
                                 showlegend=False))
    fig.update_layout(title=None,
                      xaxis_title=axis_names[0],
                      yaxis_title=axis_names[1])

    fig.update_xaxes(range=[0, np.max(x)])
    fig.update_yaxes(range=[0, np.max(y)])

    return fig



def _sensitivity_contour_plot_static(x,
                              y,
                              contour_values,
                              unadjusted_value,
                              scenario_x,
                              scenario_y,
                              scenario_value,
                              include_scenario,
                              benchmarks=None,
                              fill=True):
    
    X, Y = np.meshgrid(x, y)
    Z = np.reshape(contour_values, X.shape)

    fig, ax = plt.subplots(figsize=(6, 6))  # Create a square figure

    # create contour plot
    CS = ax.contour(X, Y, Z, colors='black')

    # # find zero level
    # zero_level = np.where(np.isclose(CS.levels, 0))[0][0]
    # print(zero_level)

    # # change zero contour line to be red and thicker
    # CS.collections[zero_level].set_color('red')
    # CS.collections[zero_level].set_linewidth(2)
    # CS.collections[zero_level].set_linestyle('dotted')

    ax.clabel(CS, inline=1, fontsize=10)

    if include_scenario:
        ax.plot(scenario_x, scenario_y, 'ro')  # Red dot
        ax.text(scenario_x, scenario_y, 'Scenario', color='red')


    # add unadjusted
    ax.plot(0, 0, '^', markersize=8, markerfacecolor='black', markeredgecolor='black')  # Diamond marker
    ax.text(0+0.004, 0+0.004, "Unadj.", color='black', fontweight='bold', 
    bbox=dict(facecolor='white', edgecolor='white', boxstyle='round,pad=0.2', linewidth=0.5), zorder=5)

    if benchmarks is not None:
        for bench_x, bench_y, bench_name in zip(benchmarks['cf_d'], benchmarks['cf_y'], benchmarks['name']):
            ax.plot(bench_x, bench_y, 'D', markersize=8, markerfacecolor='red', markeredgecolor='black')  # Diamond marker
            ax.text(bench_x+0.004, bench_y+0.004, bench_name, color='black', fontweight='bold', 
                bbox=dict(facecolor='white', edgecolor='white', boxstyle='round,pad=0.2', linewidth=0.5), zorder=5)

    ax.set_title('Contour Plot')
    ax.set_xlabel('Partial R2 of unobs. confounder(s) with the treatment')
    ax.set_ylabel('Partial R2 of unobs. confounder(s) with the outcome')
    ax.set_xlim([-0.005, np.max(x)])
    ax.set_ylim([-0.005, np.max(y)])

    plt.show()