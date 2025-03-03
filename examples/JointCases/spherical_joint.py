__doc__ = """Spherical(Free) joint example, for detailed explanation refer to Zhang et. al. Nature Comm.  
methods section."""

import numpy as np
import sys

# FIXME without appending sys.path make it more generic
sys.path.append("../../")
from elastica import *
from examples.JointCases.joint_cases_postprocessing import (
    plot_position,
    plot_video,
    plot_video_xy,
    plot_video_xz,
)


class SphericalJointSimulator(
    BaseSystemCollection, Constraints, Connections, Forcing, CallBacks
):
    pass


spherical_joint_sim = SphericalJointSimulator()

# setting up test params
n_elem = 10
direction = np.array([0.0, 0.0, 1.0])
normal = np.array([0.0, 1.0, 0.0])
roll_direction = np.cross(direction, normal)
base_length = 0.2
base_radius = 0.007
base_area = np.pi * base_radius ** 2
density = 1750
nu = 1e-3
E = 3e7
poisson_ratio = 0.5
shear_modulus = E / (poisson_ratio + 1.0)

start_rod_1 = np.zeros((3,))
start_rod_2 = start_rod_1 + direction * base_length

# Create rod 1
rod1 = CosseratRod.straight_rod(
    n_elem,
    start_rod_1,
    direction,
    normal,
    base_length,
    base_radius,
    density,
    nu,
    E,
    shear_modulus=shear_modulus,
)
spherical_joint_sim.append(rod1)
# Create rod 2
rod2 = CosseratRod.straight_rod(
    n_elem,
    start_rod_2,
    direction,
    normal,
    base_length,
    base_radius,
    density,
    nu,
    E,
    shear_modulus=shear_modulus,
)
spherical_joint_sim.append(rod2)

# Apply boundary conditions to rod1.
spherical_joint_sim.constrain(rod1).using(
    OneEndFixedBC, constrained_position_idx=(0,), constrained_director_idx=(0,)
)

# Connect rod 1 and rod 2
spherical_joint_sim.connect(
    first_rod=rod1, second_rod=rod2, first_connect_idx=-1, second_connect_idx=0
).using(
    FreeJoint, k=1e5, nu=0
)  # k=kg/s2 nu=kg/s 1e-2

# Add forces to rod2
spherical_joint_sim.add_forcing_to(rod2).using(
    EndpointForcesSinusoidal,
    start_force_mag=0,
    end_force_mag=5e-3,
    ramp_up_time=0.2,
    tangent_direction=direction,
    normal_direction=normal,
)


# Callback functions
# Add call backs
class TestJoints(CallBackBaseClass):
    """
    Call back function for testing joints
    """

    def __init__(self, step_skip: int, callback_params: dict):
        CallBackBaseClass.__init__(self)
        self.every = step_skip
        self.callback_params = callback_params

    def make_callback(self, system, time, current_step: int):
        if current_step % self.every == 0:
            self.callback_params["time"].append(time)
            self.callback_params["step"].append(current_step)
            self.callback_params["position"].append(system.position_collection.copy())
            self.callback_params["velocity"].append(system.velocity_collection.copy())
            return


pp_list_rod1 = defaultdict(list)
pp_list_rod2 = defaultdict(list)


spherical_joint_sim.collect_diagnostics(rod1).using(
    TestJoints, step_skip=1000, callback_params=pp_list_rod1
)
spherical_joint_sim.collect_diagnostics(rod2).using(
    TestJoints, step_skip=1000, callback_params=pp_list_rod2
)

spherical_joint_sim.finalize()
timestepper = PositionVerlet()
# timestepper = PEFRL()

final_time = 10
dl = base_length / n_elem
dt = 1e-5
total_steps = int(final_time / dt)
print("Total steps", total_steps)
integrate(timestepper, spherical_joint_sim, final_time, total_steps)

PLOT_FIGURE = True
SAVE_FIGURE = False
PLOT_VIDEO = True

# plotting results
if PLOT_FIGURE:
    filename = "spherical_joint_test_last_node_pos_xy.png"
    plot_position(pp_list_rod1, pp_list_rod2, filename, SAVE_FIGURE)

if PLOT_VIDEO:
    filename = "spherical_joint_test.mp4"
    plot_video(pp_list_rod1, pp_list_rod2, video_name=filename, margin=0.2, fps=100)
    plot_video_xy(
        pp_list_rod1, pp_list_rod2, video_name=filename + "_xy.mp4", margin=0.2, fps=100
    )
    plot_video_xz(
        pp_list_rod1, pp_list_rod2, video_name=filename + "_xz.mp4", margin=0.2, fps=100
    )
