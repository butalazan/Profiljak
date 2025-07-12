import numpy as np
import os
from mrezatelj import *
from risatelj import *
import subprocess
import glob



def write_su2_config(base_path, name, aoa_str, nfoils):
    base_config_path = os.path.join(base_path, f"configure.cfg")
    with open(base_config_path, 'r') as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        # Strip comments and whitespace for detection (optional)
        stripped = line.strip()
        if stripped.startswith("MESH_FILENAME="):
            new_lines.append(f"MESH_FILENAME= {base_path}/{name}/mreze/{name}-{nfoils}_{aoa_str}aoa.su2\n")
        elif stripped.startswith("SOLUTION_FILENAME="):
            new_lines.append(f"SOLUTION_FILENAME= {base_path}/{name}/dats/restart_{name}-{nfoils}_{aoa_str}aoa.dat\n")
        elif stripped.startswith("CONV_FILENAME="):
            new_lines.append(f"CONV_FILENAME= {base_path}/{name}/rezultati/history_{name}-{nfoils}_{aoa_str}aoa\n")
        elif stripped.startswith("RESTART_FILENAME="):
            new_lines.append(f"RESTART_FILENAME= {base_path}/{name}/dats/restart_{name}-{nfoils}_{aoa_str}aoa.dat\n")
        elif stripped.startswith("VOLUME_FILENAME="):
            new_lines.append(f"VOLUME_FILENAME= {base_path}/{name}/vtus/{name}-{nfoils}_{aoa_str}aoa\n")
        elif stripped.startswith("SURFACE_FILENAME="):
            new_lines.append(f"SURFACE_FILENAME= {base_path}/{name}/dats/surface_{name}-{nfoils}_{aoa_str}aoa\n")
        else:
            new_lines.append(line)

    with open(base_config_path, 'w') as f:
        f.writelines(new_lines)



def run_su2(base_path):
    config_file = os.path.join(base_path, f"configure.cfg")
    run_file = os.path.join(base_path, f"bin/SU2_CFD")
    try:
        print(f"Zagon SU2 z {config_file} ...")
        subprocess.run([run_file, config_file], check=True)
        print("\nSimulacija uspešno izvršena.")
    except subprocess.CalledProcessError as e:
        print(f"Error pri zagonu SU2: {e}")




if __name__ == "__main__":

    print(r"""=================================================================
    ____             _____ __  _       __  
   / __ \_________  / __(_) / (_)___ _/ /__
  / /_/ / ___/ __ \/ /_/ / / / / __ `/ //_/
 / ____/ /  / /_/ / __/ / / / / /_/ / ,<   
/_/   /_/   \____/_/ /_/_/_/ /\__,_/_/|_|  
                        /___/              
program za numerično analizo profilov v 2D
=================================================================""")

    # Get directory of the script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"\nTrenutna mapa: {script_dir}")


    # __________________________________________________________________________
    # INPUT FILES

    airf_name = input("Vnesi ime mape s profili: ").strip()
    data_folder = os.path.join(script_dir, airf_name)

    if not os.path.isdir(data_folder):
        print(f"⚠️  Mapa '{airf_name}' ne obstaja. Izhod.")
        exit()

    airfoil_files = glob.glob(os.path.join(data_folder, "*.dat"))
    airfoil_files += glob.glob(os.path.join(data_folder, "*.txt"))

    if len(airfoil_files) == 0:
        print("⚠️  V mapi ni .dat/.txt profilov. Izhod.")
        exit()

    print("Najdeni profili:")
    for file in airfoil_files:
        print("  ", os.path.basename(file))

    nfoils = len(airfoil_files)

    
    # Create 'meshes' subfolder if it doesn't exist
    dats_dir = os.path.join(data_folder, "dats")
    os.makedirs(dats_dir, exist_ok=True)
    vtus_dir = os.path.join(data_folder, "vtus")
    os.makedirs(vtus_dir, exist_ok=True)
    mesh_dir = os.path.join(data_folder, "mreze")
    os.makedirs(mesh_dir, exist_ok=True)
    fig_dir = os.path.join(data_folder, "slike")
    os.makedirs(fig_dir, exist_ok=True)
    rezultati_dir = os.path.join(data_folder, "rezultati")
    os.makedirs(rezultati_dir, exist_ok=True)




    #__________________________________________________________________________
    # AOA
    try:
        aoa = float(input("\nVnesi vpadni kot v stopinjah: ").strip() or 0.0)
    except ValueError:
        print("Napačen vnos. Nastavljam AoA = 0.0")
        aoa = 0.0

    sign = 'm' if aoa < 0 else ''
    aoa_code = abs(int(round(aoa * 10)))
    aoa_str = f"{sign}{aoa_code:03d}"

    # __________________________________________________________________________
    # REYNOLDS POPRAVEK
    try:
        print("\nIzračun Reynoldsa (default = 90000)")
        chord_input = input("Vnesi dolžino profila [m] (opcijsko): ").strip()
        velocity_input = input("Vnesi hitrost toka [m/s] (opcijsko): ").strip()

        if chord_input and velocity_input:
            chord_length = float(chord_input)
            velocity = float(velocity_input)

            # Constants for air at 500 m
            rho = 1.1673     # kg/m^3
            mu = 1.78e-5     # Pa·s
            Re = (rho * velocity * chord_length) / mu

            print(f"\n Re = {Re:.2e}")
            reynolds_available = True
        else:
            print("\nReynolds ostane nespremenjen.")
            reynolds_available = False

    except ValueError:
        print(" Reynolds ostane nespremenjen.")
        reynolds_available = False




    # _______________________________________________________________________
    # RISANJE PROFILA (SAFETY)

    plot_airfoils(airfoil_files, rezultati_dir, airf_name, nfoils)


    # _______________________________________________________________________
    # MESHING

    mesh_file = os.path.join(mesh_dir, f"{airf_name}-{nfoils}_{aoa_str}aoa.su2")
    #print("mesh_dir", mesh_dir)
    print("Generiram mrežo:", mesh_file)
    generate_mesh(
        airfoil_paths=airfoil_files,
        mesh_path=mesh_file,
        aoa_deg=aoa)
    
    plot_mreza(mesh_file, rezultati_dir, airf_name, aoa_str, nfoils)

    
    """    # ______________________________________________________________________
    # POPRAVEK REYNOLDSA V CONFIG.cfg

    if reynolds_available:
        # Write config and run SU2
        base_config = os.path.join(script_dir, "base_config.cfg")
        config_0 = os.path.join(script_dir, f"{data_folder}_0aoa.cfg")
        config_aoa = os.path.join(script_dir, f"{data_folder}_{int(aoa)}aoa.cfg")

    POPRAVI!!
    base_config_path = os.path.join(base_path, f"configure.cfg")
    with open(base_config_path, 'r') as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        # Strip comments and whitespace for detection (optional)
        stripped = line.strip()
        if stripped.startswith("MACH_NUMBER="):
            new_lines.append(f"MESH_FILENAME= {base_path}/{name}/mreze/{name}-{nfoils}_{aoa_str}aoa.su2\n")
        elif stripped.startswith("REYNOLDS_LENGTH="):
            new_lines.append(f"SOLUTION_FILENAME= {base_path}/{name}/dats/restart_{name}-{nfoils}_{aoa_str}aoa.dat\n")
        else:
            new_lines.append(line)

    with open(base_config_path, 'w') as f:
        f.writelines(new_lines)
        """


    write_su2_config(script_dir, airf_name, aoa_str, nfoils)


    # _______________________________________________________________________
    # ZAGON SOLVERJA

    run_su2(script_dir)

    # _______________________________________________________________________
    # POST

    plot_polje(vtus_dir, fig_dir, airf_name, aoa_str, nfoils)
    plot_zoom(vtus_dir, fig_dir, airf_name, aoa, aoa_str, nfoils)

    plot_koeffs(rezultati_dir, airf_name, aoa_str, nfoils)

    video(fig_dir, rezultati_dir, airf_name, aoa_str, nfoils)
    
    print("\nObdelava zaključena.\n")