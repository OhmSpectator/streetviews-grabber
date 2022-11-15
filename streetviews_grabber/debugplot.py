import matplotlib.pyplot as plt

PLOT = False


def set_visualize(plot_value):
    global PLOT
    PLOT = plot_value


def is_plot():
    return PLOT


def get_plt():
    return plt
