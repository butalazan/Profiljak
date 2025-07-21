import gmsh
import numpy as np

def read_airfoil_coords(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()
    coords = []
    for line in lines:
        if line.strip():
            parts = line.strip().split()
            if len(parts) >= 2:
                try:
                    coords.append([float(parts[0]), float(parts[1])])
                except ValueError:
                    # skip header lines or bad data
                    continue
    return np.array(coords)

def rotate(coords, aoa_deg=0, center=(0.5, 0)):
    aoa = np.radians(aoa_deg)
    R = np.array([[np.cos(aoa), np.sin(aoa)],
                  [-np.sin(aoa),  np.cos(aoa)]])
    shifted = coords - center
    rotated = shifted @ R.T
    return rotated + center

def generate_airfoil_loop(coords, lc):
    pt_tags = []
    for (x, y) in coords:
        pt = gmsh.model.geo.addPoint(x, y, 0, lc)
        pt_tags.append(pt)
    curve = gmsh.model.geo.addSpline(pt_tags + [pt_tags[0]])
    loop = gmsh.model.geo.addCurveLoop([curve])
    return loop, curve

def generate_mesh(airfoil_paths, mesh_path, aoa_deg=0,
                  farfield_radius=10.0, lc_airfoil=0.005, lc_far=1):

    gmsh.initialize()
    gmsh.model.add("multi_airfoils")

    gmsh.model.geo.synchronize()

    # Create farfield circle
    n_far = 50
    far_pt_tags = []
    for i in range(n_far):
        theta = 2 * np.pi * i / n_far
        x = farfield_radius * np.cos(theta)
        y = farfield_radius * np.sin(theta)
        pt = gmsh.model.geo.addPoint(x, y, 0, lc_far)
        far_pt_tags.append(pt)

    farfield_edges = []
    for i in range(n_far):
        p1 = far_pt_tags[i]
        p2 = far_pt_tags[(i + 1) % n_far]
        edge = gmsh.model.geo.addLine(p1, p2)
        farfield_edges.append(edge)

    farfield_loop = gmsh.model.geo.addCurveLoop(farfield_edges)

    # Process each airfoil
    hole_loops = []
    curve_tags = []

    for i, path in enumerate(airfoil_paths):
        coords = read_airfoil_coords(path)
        coords = rotate(coords, aoa_deg, center=(0.5, 0))

        loop, curve = generate_airfoil_loop(coords, lc_airfoil)
        hole_loops.append(loop)
        curve_tags.append(curve)

    # Create the domain with holes
    surface = gmsh.model.geo.addPlaneSurface([farfield_loop] + hole_loops)

    gmsh.model.addPhysicalGroup(1, curve_tags, tag=1)
    gmsh.model.setPhysicalName(1, 1, "airfoil")

    gmsh.model.addPhysicalGroup(1, farfield_edges, tag=2)
    gmsh.model.setPhysicalName(1, 2, "farfield")

    gmsh.model.addPhysicalGroup(2, [surface], tag=3)   # <-- THIS IS THE IMPORTANT LINE
    gmsh.model.setPhysicalName(2, 3, "fluid")

    gmsh.model.geo.synchronize()

    # Boundary layer around all airfoil curves
    bl_field = gmsh.model.mesh.field.add("BoundaryLayer")
    gmsh.model.mesh.field.setNumbers(bl_field, "CurvesList", curve_tags)
    gmsh.model.mesh.field.setNumber(bl_field, "Size", 0.0005)
    gmsh.model.mesh.field.setNumber(bl_field, "Thickness", 0.006)
    gmsh.model.mesh.field.setNumber(bl_field, "Ratio", 1.2)
    gmsh.model.mesh.field.setAsBoundaryLayer(bl_field)

    # Wake refinement
    wake_field = gmsh.model.mesh.field.add("MathEval")
    #gmsh.model.mesh.field.setString(
    #    wake_field,
    #    "F", "0.001 + 0.03 * sqrt(0.01*(x - 0.5)^2 + 2*y^2)"
    #)

    aoa_rad = np.radians(aoa_deg)
    cos_t = np.cos(aoa_rad)
    sin_t = np.sin(aoa_rad)

    rot_expr = (
        f"0.001 + 0.03 * sqrt("
        f"0.01*(({cos_t:.6f}*(x-0.5)-{sin_t:.6f}*(y-0))^2) + "
        f"2*(({sin_t:.6f}*(x-0.5)+{cos_t:.6f}*(y-0))^2)"
        f")"
    )
    #gmsh.model.mesh.field.setString(wake_field, "F", rot_expr)

    wake_box1 = gmsh.model.mesh.field.add("Box")
    gmsh.model.mesh.field.setNumber(wake_box1, "VIn", 0.008)
    gmsh.model.mesh.field.setNumber(wake_box1, "VOut", lc_far)
    gmsh.model.mesh.field.setNumber(wake_box1, "XMin", -0.2)
    gmsh.model.mesh.field.setNumber(wake_box1, "XMax", 2)
    gmsh.model.mesh.field.setNumber(wake_box1, "YMin", -0.4)
    gmsh.model.mesh.field.setNumber(wake_box1, "YMax", 0.4)

    wake_box2 = gmsh.model.mesh.field.add("Box")
    gmsh.model.mesh.field.setNumber(wake_box2, "VIn", 0.03)
    gmsh.model.mesh.field.setNumber(wake_box2, "VOut", lc_far)
    gmsh.model.mesh.field.setNumber(wake_box2, "XMin", -1.2)
    gmsh.model.mesh.field.setNumber(wake_box2, "XMax", 8)
    gmsh.model.mesh.field.setNumber(wake_box2, "YMin", -1.6)
    gmsh.model.mesh.field.setNumber(wake_box2, "YMax", 1.6)


    circle_center = gmsh.model.geo.addPoint(0.45, 0.0, 0, 1.0)
    gmsh.model.geo.synchronize()
    dist_field = gmsh.model.mesh.field.add("Distance")
    gmsh.model.mesh.field.setNumbers(dist_field, "NodesList", [circle_center])
    wake_circle = gmsh.model.mesh.field.add("Threshold")
    gmsh.model.mesh.field.setNumber(wake_circle, "InField", dist_field)
    gmsh.model.mesh.field.setNumber(wake_circle, "SizeMin", 0.004)     # Fine mesh at center
    gmsh.model.mesh.field.setNumber(wake_circle, "SizeMax", lc_far)   # Coarse mesh farther out
    gmsh.model.mesh.field.setNumber(wake_circle, "DistMin", 0.7)      # Inner radius
    gmsh.model.mesh.field.setNumber(wake_circle, "DistMax", 2.0)      # Outer radius (acts like circular box size)


    # Combine refinement fields
    min_field = gmsh.model.mesh.field.add("Min")
    gmsh.model.mesh.field.setNumbers(min_field, "FieldsList", [wake_circle, wake_box1, wake_box2, bl_field])
    gmsh.model.mesh.field.setAsBackgroundMesh(min_field)

    gmsh.model.mesh.generate(2)
    gmsh.write(mesh_path)
    print(f"Mreža je shranjena v: {mesh_path}")
    gmsh.finalize()




"""if __name__ == "__main__":
    airfoil_files = [
        "C:/Users/zanbu/OneDrive/Desktop/mesh/jxgs04.dat",
        "C:/Users/zanbu/OneDrive/Desktop/mesh/slat.dat"
    ]

    aoa = 10  # set to desired angle of attack

    generate_mesh(
        airfoil_paths=airfoil_files,
        mesh_path=f"C:/Users/zanbu/OneDrive/Desktop/mesh/themesh_aoa{aoa}.su2",
        aoa_deg=aoa
    )"""
