import pyvista as pv
import numpy as np
import glob
import os
import subprocess
from matplotlib import pyplot as plt
import matplotlib.gridspec as gridspec
import pandas as pd


camera_position = [(1.0, 0.0, 5.0),  # position
                   (0.8, 0.0, 0.0),  # focal point
                   (0.0, 1.0, 0.0)]  # view up

dt = 3E-3
frames = 5

def generate_weighted_points(n_points, center=(0.5, 0), core_size=(3.0, 1.0), domain=[-1, 2.2, -1, 1]):
    x_min, x_max, y_min, y_max = domain
    cx, cy = center
    sx, sy = core_size

    # Gaussian "preference" function centered on (0.5, 0)
    def density(x, y):
        dx = (x - cx) / (0.5 * sx)
        dy = (y - cy) / (0.5 * sy)
        return np.exp(-0.5 * (dx**2 + dy**2))  # peak at center, falls off smoothly

    accepted = []
    attempts = 0
    max_attempts = 10 * n_points  # stop trying after this many rejections

    while len(accepted) < n_points and attempts < max_attempts:
        x_rand = np.random.uniform(x_min, x_max)
        y_rand = np.random.uniform(y_min, y_max)
        prob = density(x_rand, y_rand)
        if np.random.rand() < prob:
            accepted.append((x_rand, y_rand))
        attempts += 1

    accepted = np.array(accepted)
    z = np.zeros(len(accepted))
    return np.column_stack((accepted[:, 0], accepted[:, 1], z))


def rotate_point(x, y, aoa_deg, center=(0.5, 0)):
    theta = np.radians(aoa_deg)
    cos_t = np.cos(theta)
    sin_t = np.sin(theta)
    x0, y0 = center
    xr = cos_t * (x - x0) + sin_t * (y - y0) + x0
    yr = -sin_t * (x - x0) + cos_t * (y - y0) + y0
    return xr, yr


def read_su2_mesh(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()

    points = []
    triangles = []

    n_points = 0
    n_elements = 0
    ndim = 2

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("NDIME"):
            ndim = int(line.split('=')[-1].strip())

        elif line.startswith("NPOIN"):
            n_points = int(line.split('=')[1].split()[0])
            print(f"Reading {n_points} points...")
            for j in range(i+1, i+1+n_points):
                parts = lines[j].strip().split()
                x, y = float(parts[0]), float(parts[1])
                points.append((x, y))
            i += n_points

        elif line.startswith("NELEM"):
            n_elements = int(line.split('=')[1].split()[0])
            print(f"Reading {n_elements} elements...")
            for j in range(i+1, i+1+n_elements):
                parts = lines[j].strip().split()
                etype = int(parts[0])
                if etype == 5:  # triangle
                    tri = [int(p) for p in parts[1:4]]
                    triangles.append(tri)
            i += n_elements

        i += 1

    return np.array(points), np.array(triangles)


def plot_polje(vtus_dir, fig_dir, airf_name, aoa_deg, aoa_str, nfoils):

    def configure_camera(camera_position=camera_position, zoom=0.9):
        plotter.view_xy()
        plotter.camera.SetParallelProjection(True)
        plotter.camera.parallel_scale = zoom  # adjust zoom level
        plotter.camera_position = camera_position


    # Find and sort all flow_*.vtu files
    files = sorted(glob.glob(os.path.join(vtus_dir, f"{airf_name}-{nfoils}_{aoa_str}aoa*.vtu")))
    print(f"Najdenih {len(files)} vtu datotek.")
    print(f"\nShranjujem v mapo: {fig_dir}")

    n_seeds = 500
    points = generate_weighted_points(n_seeds)
    seed = pv.PolyData(points)

    # Create plotter
    plotter = pv.Plotter(off_screen=True, window_size=[800, 500])

    for i, filename in enumerate(files):
        print(f"Procesiram {filename} ...")
        mesh = pv.read(filename)

        # Compute velocity magnitude
        velocity = mesh.point_data['Velocity']
        vel_mag = np.linalg.norm(velocity, axis=1)
        mesh.point_data['Velocity_Magnitude'] = vel_mag
        mesh.set_active_vectors('Velocity')

        pressure = mesh.point_data['Pressure'] 
        mesh.point_data['delta p'] = pressure  
        p_mean = np.mean(pressure)
        p_std = np.std(pressure)
        clim = [p_mean - 1 * p_std, p_mean + 1 * p_std]

        # Generate streamlines from random seed points
        streamlines = mesh.streamlines_from_source(
            source=seed,
            vectors='Velocity',
            integration_direction='both',
            initial_step_length=0.05,
            max_steps=30,
            terminal_speed=1e-5
        )
        #streamlines_tube = streamlines.tube(radius=0.002)

        # Plot and render
        plotter.clear()
        plotter.add_mesh(mesh, scalars='delta p', clim=clim, cmap='viridis', opacity=0.7)
        #plotter.add_mesh(mesh, scalars='Tlak [Pa]', clim=clim, cmap='viridis', opacity=0.7, show_scalar_bar=False)
        plotter.add_mesh(streamlines, line_width=0.1, color='black')
        plotter.add_text(f"{airf_name}, {aoa_deg}aoa;    Čas: {i*frames*dt:.2f}s", font_size=10)        # Čas: {i*10*8e-5:.3f}s - čas. korak 8e-5, vtu shrani na 20 korakov!
        plotter.add_axes()
        plotter.view_xy()
        configure_camera()
        plotter.render()

        plotter.screenshot(os.path.join(fig_dir, f"{airf_name}-{nfoils}_{aoa_str}aoa_frame_{i:04d}.png"))


def plot_zoom(vtus_dir, fig_dir, airf_name, aoa_deg, aoa_str, nfoils):

    def configure_camera(camera_position=camera_position, zoom=0.9):
        plotter.view_xy()
        plotter.camera.SetParallelProjection(True)
        plotter.camera.parallel_scale = zoom  # adjust zoom level
        plotter.camera_position = camera_position

    # Find and sort all flow_*.vtu files
    files = sorted(glob.glob(os.path.join(vtus_dir, f"{airf_name}-{nfoils}_{aoa_str}aoa*.vtu")))
    print(f"Najdenih {len(files)} vtu datotek.")
    print(f"\nShranjujem v mapo: {fig_dir}")

    n_seeds = 3500
    points = generate_weighted_points(n_seeds)
    seed = pv.PolyData(points)

    # Create plotter
    plotter = pv.Plotter(off_screen=True, window_size=[800, 500])

    for i, filename in enumerate(files):
        print(f"Procesiram {filename} ...")
        mesh = pv.read(filename)

        # Compute velocity magnitude
        velocity = mesh.point_data['Velocity']
        vel_mag = np.linalg.norm(velocity, axis=1)
        mesh.point_data['Velocity_Magnitude'] = vel_mag
        mesh.set_active_vectors('Velocity')

        pressure = mesh.point_data['Pressure'] 
        mesh.point_data['delta p'] = pressure  
        p_mean = np.mean(pressure)
        p_std = np.std(pressure)
        clim = [p_mean - 1 * p_std, p_mean + 1 * p_std]

        # Generate streamlines from random seed points
        streamlines = mesh.streamlines_from_source(
            source=seed,
            vectors='Velocity',
            integration_direction='both',
            initial_step_length=0.05,
            max_steps=30,
            terminal_speed=1e-5
        )
        #streamlines_tube = streamlines.tube(radius=0.002)

        # Plot and render
        plotter.clear()
        plotter.add_mesh(mesh, scalars='delta p', clim=clim, cmap='viridis', opacity=0.7, show_scalar_bar=False)
        plotter.add_mesh(streamlines, line_width=0.1, color='black')
        #plotter.add_mesh(streamlines_tube, color='black', opacity=0.1)
        plotter.add_text(f"{airf_name}, {aoa_deg}aoa;    Čas: {i*frames*dt:.2f}s", font_size=10)        # Čas: {i*10*8e-5:.3f}s - čas. korak 8e-5, vtu shrani na 20 korakov!
        #plotter.add_text(f"Ćas: {i*20*9e-5:.3f}s", font_size=10)
        plotter.add_axes()
        plotter.view_xy()
        x_zoom, y_zoom = rotate_point(0.0, 0.0, aoa_deg)
        cam_pos1 = [(1.0, 0.0, 5.0),  # position
                        (x_zoom+0.15, y_zoom, 0.0),  # focal point
                        (0.0, 1.0, 0.0)]  # view up
        configure_camera(cam_pos1, 0.25)
        plotter.render()

        plotter.screenshot(os.path.join(fig_dir, f"{airf_name}-{nfoils}_{aoa_str}aoa_zoom1frame_{i:04d}.png"))


        # Plot and render
        plotter.clear()
        plotter.add_mesh(mesh, scalars='delta p', clim=clim, cmap='viridis', opacity=0.7, show_scalar_bar=False)
        plotter.add_mesh(streamlines, line_width=0.1, color='black')
        #plotter.add_mesh(streamlines_tube, color='black', opacity=0.1)
        plotter.add_text(f"{airf_name}, {aoa_deg}aoa;    Čas: {i*frames*dt:.2f}s", font_size=10)        # Čas: {i*10*8e-5:.3f}s - čas. korak 8e-5, vtu shrani na 20 korakov!
        #plotter.add_text(f"Ćas: {i*20*9e-5:.3f}s", font_size=10)
        plotter.add_axes()
        plotter.view_xy()
        x_zoom, y_zoom = rotate_point(1.0, 0.0, aoa_deg)
        cam_pos1 = [(1.0, 0.0, 5.0),  # position
                        (x_zoom, y_zoom+0.1, 0.0),  # focal point
                        (0.0, 1.0, 0.0)]  # view up
        configure_camera(cam_pos1, 0.25)
        plotter.render()

        plotter.screenshot(os.path.join(fig_dir, f"{airf_name}-{nfoils}_{aoa_str}aoa_zoom2frame_{i:04d}.png"))


def plot_mreza(mesh_file, out_dir, airf_name, aoa_deg, nfoils):
    points, triangles = read_su2_mesh(mesh_file)


    zoom_size = 0.2
    aoa_deg=15
    fig = plt.figure(figsize=(11, 8))
    gs = gridspec.GridSpec(2, 2, height_ratios=[2, 1])

    # --- TOP: full view ---
    ax_top = fig.add_subplot(gs[0, :])
    ax_top.triplot(points[:, 0], points[:, 1], triangles, color='black', linewidth=0.2)
    ax_top.set_title("Mreža")
    ax_top.set_xlim(-0.15, 1.2)
    ax_top.set_ylim(-0.35, 0.35)
    ax_top.set_aspect("equal")

    # --- BOTTOM LEFT: leading edge zoom ---
    ax_lead = fig.add_subplot(gs[1, 0])
    ax_lead.triplot(points[:, 0], points[:, 1], triangles, color='black', linewidth=0.2)

    x_zoom, y_zoom = rotate_point(0.0, 0.0, aoa_deg)
    ax_lead.set_xlim(x_zoom - zoom_size * (1 - 0.3), x_zoom + zoom_size * (1 + 0.3))
    ax_lead.set_ylim(y_zoom - zoom_size * (1 - 0.2)*0.55, y_zoom + zoom_size * (1 + 0.2)*0.55)
    ax_lead.set_aspect("equal")

    # --- BOTTOM RIGHT: trailing edge zoom ---
    ax_trail = fig.add_subplot(gs[1, 1])
    ax_trail.triplot(points[:, 0], points[:, 1], triangles, color='black', linewidth=0.2)

    x_zoom, y_zoom = rotate_point(1.0, 0.0, aoa_deg)
    ax_trail.set_xlim(x_zoom - zoom_size, x_zoom + zoom_size)
    ax_trail.set_ylim(y_zoom - zoom_size * (1 - 0.2)*0.55, y_zoom + zoom_size * (1 + 0.2)*0.55)
    ax_trail.set_aspect("equal")

    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, f"{airf_name}-{nfoils}_{aoa_deg}aoa_mreza.png"))


def plot_koeffs(rezultati_dir, airf_name, aoa_str, nfoils):
    history_file = rezultati_dir + f"/history_{airf_name}-{nfoils}_{aoa_str}aoa.csv"
    df = pd.read_csv(history_file)
    df.columns = df.columns.str.strip().str.replace('"', '')
    print(df.keys)


    dt = 5*0.9e-4
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    fig.suptitle('Aero-Koeficienti', fontsize=16)

    # Subplot 1: CL
    axes[0, 0].plot(df['Cur_Time'], df['CL'], label='CL')
    #axes[0, 0].set_title('$C_L$')
    axes[0, 0].set_xlabel("$t$ [s]")
    axes[0, 0].set_ylabel('$C_L$')
    axes[0, 0].grid(True)
    cl_avg = np.mean(df['CL'])
    cl_rms = np.sqrt(np.mean(df['CL']**2))
    try: axes[0, 0].set_ylim(cl_avg - cl_rms, cl_avg + cl_rms)
    except: pass

    # Subplot 2: CD
    axes[0, 1].plot(df['Cur_Time'], df['CD'], label='CD')
    #axes[0, 1].set_title('$C_D$')
    axes[0, 1].set_xlabel("$t$ [s]")
    axes[0, 1].set_ylabel('$C_D$')
    axes[0, 1].grid(True)
    cl_avg = np.mean(df['CL'])
    cl_rms = np.sqrt(np.mean(df['CD']**2))
    #axes[0, 1].set_ylim(cl_avg - cl_rms, cl_avg + cl_rms)

    # Subplot 3: CL/CD Ratio
    df['CL/CD'] = df['CL'] / df['CD'].replace(0, float('nan'))
    axes[1, 0].plot(df['Cur_Time'], df['CL/CD'], label='CL/CD')
    #axes[1, 0].set_title('$C_L/C_D$')
    axes[1, 0].set_xlabel("$t$ [s]")
    axes[1, 0].set_ylabel('$C_L/C_D$')
    axes[1, 0].grid(True)

    # Subplot 4: CMz
    axes[1, 1].plot(df['Cur_Time'], df['CMz'], label='CMz')
    #axes[1, 1].set_title('$C_M$')
    axes[1, 1].set_xlabel("$t$ [s]")
    axes[1, 1].set_ylabel('$C_M$')
    axes[1, 1].grid(True)
    cl_avg = np.mean(df['CMz'])
    cl_rms = np.sqrt(np.mean(df['CL']**2))
    #axes[1, 1].set_ylim(cl_avg - cl_rms, cl_avg + cl_rms)

    # Layout adjustment
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    #fig.savefig(folder + "/rezultati/koeficienti.png", dpi=300) 
    fig.savefig(os.path.join(rezultati_dir, f"{airf_name}-{nfoils}_{aoa_str}aoa_koeficienti.png"))






    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    fig.suptitle('Časovno povprečeni koeficienti', fontsize=16)

    # Subplot 1: CL (averaged)
    axes[0, 0].plot(df['Cur_Time'], df['tavg[CL]'], label='CL')
    #axes[0, 0].set_title('$\\overline{C_L}$')
    axes[0, 0].set_xlabel("$t$ [s]")
    axes[0, 0].set_ylabel('$\\overline{C_L}$')
    axes[0, 0].grid(True)

    # Subplot 2: CD (averaged)
    axes[0, 1].plot(df['Cur_Time'], df['tavg[CD]'], label='CD')
    #axes[0, 1].set_title('$\\overline{C_D}$')
    axes[0, 1].set_xlabel("$t$ [s]")
    axes[0, 1].set_ylabel('$\\overline{C_D}$')
    axes[0, 1].grid(True)

    # Subplot 3: CL/CD Ratio (averaged)
    df['tavg[CL/CD]'] = df['tavg[CL]'] / df['tavg[CD]'].replace(0, float('nan'))
    axes[1, 0].plot(df['Cur_Time'], df['tavg[CL/CD]'], label='CL/CD')
    #axes[1, 0].set_title('$\\overline{C_L} / \\overline{C_D}$')
    axes[1, 0].set_xlabel("$t$ [s]")
    axes[1, 0].set_ylabel('$\\overline{C_L} / \\overline{C_D}$')
    axes[1, 0].grid(True)

    # Subplot 4: CMz (averaged)
    axes[1, 1].plot(df['Cur_Time'], df['tavg[CMz]'], label='CMz')
    #axes[1, 1].set_title('$\\overline{C_M}$')
    axes[1, 1].set_xlabel("$t$ [s]")
    axes[1, 1].set_ylabel('$\\overline{C_M}$')
    axes[1, 1].grid(True)

    # Save the figure
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.savefig(os.path.join(rezultati_dir, f"{airf_name}-{nfoils}_{aoa_str}aoa_koeficienti_avg.png"))







    fig2, axes = plt.subplots(3, 2, figsize=(12, 12))
    fig2.suptitle("Konvergenca", fontsize=16)

    # Subplot 1: rho residual
    axes[0, 0].plot(df['Time_Iter'], df['Inner_Iter'])
    axes[0, 0].set_xlabel('iteracija')
    axes[0, 0].set_ylabel('Notranji stepi')
    axes[0, 0].grid(True)

    # Subplot 2: rhoU residual
    axes[0, 1].semilogy(df['Inner_Iter'], df['rms[P]'])
    axes[0, 1].set_xlabel('iteracija')
    axes[0, 1].set_ylabel('rms[P]')
    #axes[0, 0].grid(True)

    # Subplot 3: rhoU residual
    #axes[1, 0].semilogy(df['Time_Iter'], df['rms[E]'])
    axes[1, 0].semilogy(df['Time_Iter'], df['rms[nu]'])
    axes[1, 0].set_xlabel('iteracija')
    axes[1, 0].set_ylabel('rms[E]')
    #axes[0, 1].grid(True)

    # Subplot 4: rhoV residual
    axes[1, 1].semilogy(df['Time_Iter'], df['rms[V]'], label="$rms v_x$")
    axes[1, 1].semilogy(df['Time_Iter'], df['rms[U]'], label="$rms v_y$")
    axes[1, 1].set_xlabel('iteracija')
    axes[1, 1].set_ylabel('rms[U, V]')
    #axes[1, 0].grid(True)

    # Subplot 5: rhoE residual
    axes[2, 0].semilogy(df['Time_Iter'], df['rms[nu]'])
    axes[2, 0].set_xlabel('iteracija')
    axes[2, 0].set_ylabel('rms[nu]')
    #axes[1, 1].grid(True)


    # Subplot 6: Buffet
    axes[2, 1].plot(df['Time_Iter'], df['Buffet'], label="lokal.")
    axes[2, 1].plot(df['Time_Iter'], df['tavg[Buffet]'], label="tavg")
    axes[2, 1].set_xlabel('iteracija')
    axes[2, 1].set_ylabel('Buffet')
    axes[2, 1].grid(True)
    axes[2, 1].legend()

    fig2.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig2.savefig(os.path.join(rezultati_dir, f"{airf_name}-{nfoils}_{aoa_str}aoa_konvergenca.png"))


def video(fig_dir, out_dir, airf_name, aoa_deg, nfoils):

    # Adjust to match your filenames
    cmd = [
        "ffmpeg",
        "-framerate", "24",
        "-i", os.path.join(fig_dir, f"{airf_name}-{nfoils}_{aoa_deg}aoa_frame_%04d.png"),
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        os.path.join(out_dir, f"{airf_name}-{nfoils}_{aoa_deg}aoa.mp4")
    ]
    subprocess.run(cmd)

    cmd1 = [
        "ffmpeg",
        "-framerate", "24",
        "-i", os.path.join(fig_dir, f"{airf_name}-{nfoils}_{aoa_deg}aoa_zoom1frame_%04d.png"),
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        os.path.join(out_dir, f"{airf_name}-{nfoils}_{aoa_deg}aoa_zoom1frame_prednji.mp4")
    ]
    cmd2 = [
        "ffmpeg",
        "-framerate", "24",
        "-i", os.path.join(fig_dir, f"{airf_name}-{nfoils}_{aoa_deg}aoa_zoom2frame_%04d.png"),
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        os.path.join(out_dir, f"{airf_name}-{nfoils}_{aoa_deg}aoa_zoom2frame_zadnji.mp4")
    ]
    subprocess.run(cmd1)
    subprocess.run(cmd2)


def read_airfoil_coords(path):
    """Reads airfoil coordinates from a .dat file."""
    coords = []
    with open(path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2:
                try:
                    x, y = map(float, parts)
                    coords.append([x, y])
                except ValueError:
                    continue  # skip non-numeric lines
    return np.array(coords)

def rotate_coords(coords, angle_deg, center=(0.5, 0.0)):
    """Rotates coordinates around a given center by angle in degrees."""
    angle_rad = np.radians(angle_deg)
    cos_t, sin_t = np.cos(angle_rad), np.sin(angle_rad)
    cx, cy = center
    shifted = coords - np.array([cx, cy])
    rotated = np.dot(shifted, np.array([[cos_t, -sin_t], [sin_t, cos_t]]))
    return rotated + np.array([cx, cy])

def plot_airfoils(dat_paths, out_dir, airf_name, nfoils):
    """Plots all airfoils from a list of .dat files, rotated by aoa_deg."""
    plt.figure(figsize=(10, 5))
    for path in dat_paths:
        coords = read_airfoil_coords(path)
        if coords.size == 0:
            print(f"Opomba: ni podatkov v {path}")
            continue
        #coords = rotate_coords(coords, aoa_deg)
        plt.plot(coords[:, 0], coords[:, 1], ".", label=path.split('/')[-1])
    
    plt.gca().set_aspect('equal')
    plt.title(f"profil")
    plt.xlabel("x")
    plt.ylabel("y")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"{airf_name}-{nfoils}_profil.png"))

# #Uporaba
#airfoil_files = ["naca0012.dat", "naca4412.dat", "clarky.dat"]
#plot_airfoils(airfoil_files, aoa_deg=5)
