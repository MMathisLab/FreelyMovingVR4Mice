import numpy as np
from math import pi

class OneEuroFilter:
    def __init__(self, t0, x0, dx0=None, min_cutoff=1.0, beta=0.0,
                 d_cutoff=1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_prev = x0
        if dx0 is None:
            dx0 = np.zeros_like(x0)
        self.dx_prev = dx0
        self.t_prev = t0

    @staticmethod
    def smoothing_factor(t_e, cutoff):
        r = 2 * pi * cutoff * t_e
        return r / (r + 1)

    @staticmethod
    def exponential_smoothing(alpha, x, x_prev):
        return alpha * x + (1 - alpha) * x_prev

    def __call__(self, t, x):
        t_e = t - self.t_prev

        a_d = self.smoothing_factor(t_e, self.d_cutoff)
        dx = (x - self.x_prev) / t_e
        dx_hat = self.exponential_smoothing(a_d, dx, self.dx_prev)

        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = self.smoothing_factor(t_e, cutoff)
        x_hat = self.exponential_smoothing(a, x, self.x_prev)

        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = t

        return x_hat