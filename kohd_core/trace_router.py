# kohd_core/trace_router.py
import math

def _get_node_rc(node_name: str, node_layout: list[list[str]]) -> tuple[int | None, int | None]:
    for r_idx, row in enumerate(node_layout):
        if node_name in row:
            return r_idx, row.index(node_name)
    return None, None

def _sign(val: float) -> int:
    return 1 if val >= 0 else -1

def _points_are_close(p1: tuple[float,float] | None, p2: tuple[float,float] | None, tol: float = 1e-3) -> bool:
    if p1 is None or p2 is None: return p1 == p2
    return abs(p1[0] - p2[0]) < tol and abs(p1[1] - p2[1]) < tol

def calculate_trace_path(
    start_node_name: str,
    end_node_name: str,
    start_ring_level: int,
    end_ring_level: int,
    all_node_positions: dict[str, tuple[float, float]],
    node_layout: list[list[str]], 
    node_radius: float, 
    get_ring_radius_method: callable,
    short_stub_length_factor: float = 0.5 
) -> list[tuple[float, float]]:
    
    s_center_x, s_center_y = all_node_positions[start_node_name]
    e_center_x, e_center_y = all_node_positions[end_node_name]

    s_eff_radius = get_ring_radius_method(start_ring_level)
    e_eff_radius = get_ring_radius_method(end_ring_level)

    dx_centers = e_center_x - s_center_x
    dy_centers = e_center_y - s_center_y

    align_tolerance = 0.1 

    path_points: list[tuple[float,float] | None] = []
    s_on_face: tuple[float, float]
    e_on_face: tuple[float, float]
    p_A: tuple[float, float] # End of start stub
    p_D: tuple[float, float] # Start of end stub (P_A -> P_D is the direct connecting segment)

    stub_len = node_radius * short_stub_length_factor

    # Handle cases where nodes are essentially aligned horizontally or vertically FIRST
    if abs(dx_centers) < align_tolerance: # Vertically aligned centers
        s_on_face = (s_center_x, s_center_y + s_eff_radius * _sign(dy_centers))
        e_on_face = (e_center_x, e_center_y - e_eff_radius * _sign(dy_centers)) 
        path_points = [s_on_face, e_on_face]
    elif abs(dy_centers) < align_tolerance: # Horizontally aligned centers
        s_on_face = (s_center_x + s_eff_radius * _sign(dx_centers), s_center_y)
        e_on_face = (e_center_x - e_eff_radius * _sign(dx_centers), e_center_y) 
        path_points = [s_on_face, e_on_face]
    else:
        # Diagonal case: S_on_face -> P_A -> P_D -> E_on_face
        
        # --- Determine Start Face (s_on_face) and P_A (end of start stub) ---
        is_s_stub_horizontal = abs(dx_centers) >= abs(dy_centers) # Start stub is H if travel is more H
        
        if is_s_stub_horizontal:
            s_on_face = (s_center_x + s_eff_radius * _sign(dx_centers), s_center_y) # E/W face of S
            p_A = (s_on_face[0] + stub_len * _sign(dx_centers), s_on_face[1])       # H-stub from S
        else: # Start stub is Vertical
            s_on_face = (s_center_x, s_center_y + s_eff_radius * _sign(dy_centers)) # N/S face of S
            p_A = (s_on_face[0], s_on_face[1] + stub_len * _sign(dy_centers))       # V-stub from S

        # --- Determine End Face (e_on_face) and P_D (start of end stub) ---
        # e_on_face is the face of E that points towards S's center.
        # The stub P_D -> e_on_face will be orthogonal to this face.
        is_e_stub_horizontal: bool # Will the stub P_D -> e_on_face be horizontal?

        if abs(dx_centers) >= abs(dy_centers): # S is primarily East/West of E, so E receives on E/W face.
            e_face_sign_x = -_sign(dx_centers) # Face of E pointing back to S
            e_on_face = (e_center_x + e_eff_radius * e_face_sign_x, e_center_y) # E/W face of E
            p_D = (e_on_face[0] + stub_len * e_face_sign_x, e_on_face[1])       # H-stub from this E/W face
            is_e_stub_horizontal = True
        else: # S is primarily North/South of E, so E receives on N/S face.
            e_face_sign_y = -_sign(dy_centers) # Face of E pointing back to S
            e_on_face = (e_center_x, e_center_y + e_eff_radius * e_face_sign_y) # N/S face of E
            p_D = (e_on_face[0], e_on_face[1] + stub_len * e_face_sign_y)       # V-stub from this N/S face
            is_e_stub_horizontal = False

        path_points.append(s_on_face)
        if not _points_are_close(s_on_face, p_A):
            path_points.append(p_A)
        
        # Direct connection between P_A and P_D
        if not _points_are_close(p_A, p_D) and not _points_are_close(path_points[-1], p_D):
            path_points.append(p_D)
        
        if not _points_are_close(path_points[-1], e_on_face):
            path_points.append(e_on_face)

    # Clean up: Remove consecutive duplicate points from the final list
    final_path_tuples: list[tuple[float,float]] = []
    # ... (cleanup logic remains the same)
    if path_points:
        first_valid_point = next((pt for pt in path_points if pt is not None), None)
        if first_valid_point is None: 
            s_fallback_face = (s_center_x + s_eff_radius * _sign(dx_centers if abs(dx_centers) > 1e-6 else 1), s_center_y)
            e_fallback_face = (e_center_x - e_eff_radius * _sign(dx_centers if abs(dx_centers) > 1e-6 else 1), e_center_y)
            return [s_fallback_face, e_fallback_face] if not _points_are_close(s_fallback_face, e_fallback_face) else [s_fallback_face]

        final_path_tuples.append(first_valid_point)
        for i in range(path_points.index(first_valid_point) + 1, len(path_points)):
            current_point = path_points[i]
            if current_point is not None and not _points_are_close(current_point, final_path_tuples[-1]):
                final_path_tuples.append(current_point)
    
    # Define s_on_face/e_on_face for fallback if not defined in diagonal block
    # (This block might need to be before the length check for final_path_tuples)
    s_on_face_defined = 's_on_face' in locals() and s_on_face is not None
    e_on_face_defined = 'e_on_face' in locals() and e_on_face is not None

    if not s_on_face_defined:
        s_on_face = (s_center_x + s_eff_radius * _sign(dx_centers if abs(dx_centers) > align_tolerance else 1), s_center_y)
    if not e_on_face_defined:
        e_on_face = (e_center_x - e_eff_radius * _sign(dx_centers if abs(dx_centers) > align_tolerance else 1), e_center_y)


    if len(final_path_tuples) < 2 and not _points_are_close(s_on_face, e_on_face):
        return [s_on_face, e_on_face]
    if not final_path_tuples : 
        return [s_on_face, e_on_face] if not _points_are_close(s_on_face, e_on_face) else [s_on_face]
        
    return final_path_tuples


if __name__ == '__main__':
    # ... (Test cases remain the same)
    mock_node_positions = {
        'ABC': (50, 50), 'DEF': (150, 50), 'GHI': (250, 50),
        'JKL': (50, 150), 'MNO': (150, 150), 'PQR': (250, 150),
        'STU': (50, 250), 'VWX': (150, 250), 'YZ': (250, 250)
    }
    mock_node_layout = [ 
        ['ABC', 'DEF', 'GHI'],
        ['JKL', 'MNO', 'PQR'],
        ['STU', 'VWX', 'YZ']
    ]
    mock_node_radius = 20.0
    TEMP_MAX_RINGS_TO_DRAW_MOCK = 2 
    TEMP_RING_NODE_INSET_FACTOR_MOCK = 0.7
    def mock_get_ring_radius(ring_level: int) -> float:
        if ring_level == 0: return mock_node_radius 
        elif ring_level > 0:
            actual_ring_to_calc = min(ring_level, TEMP_MAX_RINGS_TO_DRAW_MOCK)
            inset_factor = TEMP_RING_NODE_INSET_FACTOR_MOCK - ((actual_ring_to_calc - 1) * 0.25)
            return mock_node_radius * max(0.1, inset_factor)
        return mock_node_radius

    print("--- Trace Router Tests (Reverted middle segment to direct P_A -> P_D connection) ---")
    stub_factor_test = 0.5 # User mentioned "initial segment a bit longer"

    test_cases = [
        ("ABC", "DEF", 0, 0, "H-aligned"),
        ("ABC", "JKL", 0, 0, "V-aligned"),
        ("MNO", "STU", 0, 0, "MNO to STU (Image example base)"), 
        ("STU", "GHI", 0, 0, "STU to GHI (Image example base)"), 
        ("ABC", "MNO", 0, 0, "Diagonal 1 (main, dx_centers=dy_centers)"), 
        ("ABC", "PQR", 0, 0, "Diagonal 2 (wide, dx_centers > dy_centers)"), 
        ("ABC", "VWX", 0, 0, "Diagonal 3 (tall, dy_centers > dx_centers)"), 
        # ... other test cases ...
    ]

    for start, end, r1, r2, desc in test_cases:
        path = calculate_trace_path(
            start, end, r1, r2, 
            mock_node_positions, mock_node_layout, 
            mock_node_radius, mock_get_ring_radius, 
            short_stub_length_factor=stub_factor_test
        )
        display_path = [(round(p[0],1), round(p[1],1)) for p in path]
        print(f"Path {start}(R{r1}) to {end}(R{r2}) ({desc}, stub_len={stub_factor_test*mock_node_radius:.1f}): {display_path}")