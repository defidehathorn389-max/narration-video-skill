"""Checks the non-uniform time-coordinate model, without rendering a video."""
import numpy as np

MODELS = [
    ([0, .25, .5, .75, 1], [0, 6, 15, 45, 60]),
    ([0, .2, .4, .65, .85, 1], [0, 18, 22, 50, 54, 60]),
]

def inverse_time(minutes, model):
    xs, ts = MODELS[model]
    if not 0 <= minutes <= 60:
        raise ValueError('Time coordinate must be in [0, 60]')
    return float(np.interp(minutes, ts, xs))

for model, (xs, ts) in enumerate(MODELS):
    assert xs[0] == 0 and xs[-1] == 1
    assert ts[0] == 0 and ts[-1] == 60
    assert all(b > a for a, b in zip(xs, xs[1:]))
    assert all(b > a for a, b in zip(ts, ts[1:]))
    for t in np.linspace(0, 30, 101):
        left, right = inverse_time(t, model), inverse_time(60-t, model)
        assert left <= right + 1e-10
    assert abs(inverse_time(30, model)-inverse_time(60-30, model)) < 1e-10

assert abs(inverse_time(30, 0) - .625) < 1e-10
assert abs(inverse_time(30, 0) - .5) > .1
# Second rope: one end already burned for 30 minutes; now light the other.
for delta in np.linspace(0, 15, 101):
    left = inverse_time(30+delta, 1)
    right = inverse_time(60-delta, 1)
    assert left <= right + 1e-10
assert abs(inverse_time(45, 1)-inverse_time(60-15, 1)) < 1e-10
assert 30+15 == 45
print('PASS: both non-uniform models are monotonic; rope 1 meets off-center at 30 min; rope 2 finishes at 45 min total.')
