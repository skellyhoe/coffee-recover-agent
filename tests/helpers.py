import random

from job.workspace import Workspace
from sim.generator import add_product, base_world


def workspace(tmp_path, *products, seed=7, cutoff=None):
    """A workspace with extra unknown products: (code, name, price, n_orders, kwargs...)."""
    world = base_world(seed=seed)
    rng = random.Random(seed)
    for p in products:
        add_product(world, rng, **p)
    if cutoff:
        world["export_cutoff"] = cutoff
    return Workspace.create(tmp_path / "ws", world)
