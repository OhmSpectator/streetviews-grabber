import matplotlib.pyplot as plt

PLOT = False


def plot_init():
    plt.plot()

def set_visualize(plot_value):
    global PLOT
    PLOT = plot_value


def is_plot():
    return PLOT


def get_plt():
    return plt
