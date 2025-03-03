import numpy as np
import sys

sys.path.append("../../../../")
from elastica import *
from examples.RodContactCase.post_processing import (
    plot_video_with_surface,
    plot_velocity,
    plot_link_writhe_twist,
)


class SolenoidCase(BaseSystemCollection, Constraints, Connections, Forcing, CallBacks):
    pass


solenoid_sim = SolenoidCase()

# Simulation parameters
number_of_rotations = 13
time_start_twist = 10
time_twist = 5 * number_of_rotations
time_relax = 50
final_time = time_relax + time_twist + time_start_twist

base_length = 1.0
n_elem = 100

dt = 0.0025 * base_length / n_elem  # 1E-2
total_steps = int(final_time / dt)
time_step = np.float64(final_time / total_steps)
rendering_fps = 20
step_skip = int(1.0 / (rendering_fps * time_step))

# Rest of the rod parameters and construct rod
base_radius = 0.025
base_area = np.pi * base_radius ** 2
I = np.pi / 4 * base_radius ** 4
volume = base_area * base_length
mass = 1.0
density = mass / volume
nu = 2.0
E = 1e6
poisson_ratio = 0.5
shear_modulus = E / (poisson_ratio + 1.0)

direction = np.array([0.0, 1.0, 0])
normal = np.array([0.0, 0.0, 1.0])
start = np.zeros(
    3,
)

F_pulling_scalar = 300


sherable_rod = CosseratRod.straight_rod(
    n_elem,
    start,
    direction,
    normal,
    base_length,
    base_radius,
    density,
    nu,
    E,
    shear_modulus=shear_modulus,
)


solenoid_sim.append(sherable_rod)

# boundary condition
from elastica._rotations import _get_rotation_matrix


class SelonoidsBC(ConstraintBase):
    """ """

    def __init__(
        self,
        position_start,
        position_end,
        director_start,
        director_end,
        twisting_time,
        time_twis_start,
        number_of_rotations,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.twisting_time = twisting_time
        self.time_twis_start = time_twis_start

        theta = 2.0 * number_of_rotations * np.pi

        angel_vel_scalar = theta / self.twisting_time

        direction = -(position_end - position_start) / np.linalg.norm(
            position_end - position_start
        )

        axis_of_rotation_in_material_frame = director_end @ direction
        axis_of_rotation_in_material_frame /= np.linalg.norm(
            axis_of_rotation_in_material_frame
        )

        self.final_end_directors = (
            _get_rotation_matrix(
                -theta, axis_of_rotation_in_material_frame.reshape(3, 1)
            ).reshape(3, 3)
            @ director_end
        )  # rotation_matrix wants vectors 3,1

        self.ang_vel = angel_vel_scalar * axis_of_rotation_in_material_frame

        self.position_start = position_start
        self.director_start = director_start

    def constrain_values(self, rod, time):
        if time > self.twisting_time + self.time_twis_start:
            rod.position_collection[..., 0] = self.position_start
            rod.position_collection[0, -1] = 0.0
            rod.position_collection[2, -1] = 0.0

            rod.director_collection[..., 0] = self.director_start
            rod.director_collection[..., -1] = self.final_end_directors

    def constrain_rates(self, rod, time):
        if time > self.twisting_time + self.time_twis_start:
            rod.velocity_collection[..., 0] = 0.0
            rod.omega_collection[..., 0] = 0.0

            rod.velocity_collection[..., -1] = 0.0
            rod.omega_collection[..., -1] = 0.0

        elif time < self.time_twis_start:
            rod.velocity_collection[..., 0] = 0.0
            rod.omega_collection[..., 0] = 0.0

        else:
            rod.velocity_collection[..., 0] = 0.0
            rod.omega_collection[..., 0] = 0.0

            rod.velocity_collection[0, -1] = 0.0
            rod.velocity_collection[2, -1] = 0.0
            rod.omega_collection[..., -1] = -self.ang_vel

            rod.velocity_collection[2, int(rod.n_elems / 2)] -= 1e-4


solenoid_sim.constrain(sherable_rod).using(
    SelonoidsBC,
    constrained_position_idx=(0, -1),
    constrained_director_idx=(0, -1),
    time_twis_start=time_start_twist,
    twisting_time=time_twist,
    number_of_rotations=number_of_rotations,
)

solenoid_sim.add_forcing_to(sherable_rod).using(
    EndpointForces,
    np.zeros(
        3,
    ),
    F_pulling_scalar * direction,
    ramp_up_time=time_start_twist - 1,
)

# Add self contact to prevent penetration
solenoid_sim.connect(sherable_rod, sherable_rod).using(SelfContact, k=1e4, nu=10)

# Add callback functions for plotting position of the rod later on
class RodCallBack(CallBackBaseClass):
    """ """

    def __init__(self, step_skip: int, callback_params: dict):
        CallBackBaseClass.__init__(self)
        self.every = step_skip
        self.callback_params = callback_params

    def make_callback(self, system, time, current_step: int):
        if current_step % self.every == 0:
            self.callback_params["time"].append(time)
            self.callback_params["step"].append(current_step)
            self.callback_params["position"].append(system.position_collection.copy())
            self.callback_params["radius"].append(system.radius.copy())
            self.callback_params["com"].append(system.compute_position_center_of_mass())
            self.callback_params["com_velocity"].append(
                system.compute_velocity_center_of_mass()
            )

            total_energy = (
                system.compute_translational_energy()
                + system.compute_rotational_energy()
                + system.compute_bending_energy()
                + system.compute_shear_energy()
            )
            self.callback_params["total_energy"].append(total_energy)
            self.callback_params["directors"].append(system.director_collection.copy())

            return


post_processing_dict = defaultdict(list)  # list which collected data will be append
# set the diagnostics for rod and collect data
solenoid_sim.collect_diagnostics(sherable_rod).using(
    RodCallBack,
    step_skip=step_skip,
    callback_params=post_processing_dict,
)

# finalize simulation
solenoid_sim.finalize()

# Run the simulation
time_stepper = PositionVerlet()
integrate(time_stepper, solenoid_sim, final_time, total_steps)

# plotting the videos
filename_video = "solenoid.mp4"
plot_video_with_surface(
    [post_processing_dict],
    video_name=filename_video,
    fps=rendering_fps,
    step=1,
    vis3D=True,
    vis2D=True,
    x_limits=[-0.5, 0.5],
    y_limits=[-0.1, 1.4],
    z_limits=[-0.5, 0.5],
)

# Compute topological quantities
time = np.array(post_processing_dict["time"])
position_history = np.array(post_processing_dict["position"])
radius_history = np.array(post_processing_dict["radius"])
director_history = np.array(post_processing_dict["directors"])

# Compute twist density
theta = 2.0 * number_of_rotations * np.pi
angel_vel_scalar = theta / time_twist

twist_time_interval_start_idx = np.where(time > time_start_twist)[0][0]
twist_time_interval_end_idx = np.where(time < (time_relax + time_twist))[0][-1]

twist_density = (
    (time[twist_time_interval_start_idx:twist_time_interval_end_idx] - time_start_twist)
    * angel_vel_scalar
    * base_radius
)

# Compute link-writhe-twist
normal_history = director_history[:, 0, :, :]
segment_length = 10 * base_length

type_of_additional_segment = "next_tangent"

total_twist, local_twist = compute_twist(position_history, normal_history)

total_link = compute_link(
    position_history,
    normal_history,
    radius_history,
    segment_length,
    type_of_additional_segment,
)

total_writhe = compute_writhe(
    position_history, segment_length, type_of_additional_segment
)

# Plot link-writhe-twist
plot_link_writhe_twist(
    twist_density,
    total_twist[twist_time_interval_start_idx:twist_time_interval_end_idx],
    total_writhe[twist_time_interval_start_idx:twist_time_interval_end_idx],
    total_link[twist_time_interval_start_idx:twist_time_interval_end_idx],
)

# Save simulation data
import os

save_folder = os.path.join(os.getcwd(), "data")
os.makedirs(save_folder, exist_ok=True)
np.savez(
    os.path.join(save_folder, "solenoid_case_data.npz"),
    time=time,
    position_history=position_history,
    radius_history=radius_history,
    director_history=director_history,
    base_length=np.array(base_length),
    twist_density=twist_density,
    total_twist=total_twist,
    total_writhe=total_writhe,
    total_link=total_link,
)
