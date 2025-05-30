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
    if p1 is None or p2 is None: return p1 == p2 # If one is None, they are close only if both are None
    return abs(p1[0] - p2[0]) < tol and abs(p1[1] - p2[1]) < tol

# This helper calculates connection point on circumference based on target node's center
def _calculate_circumference_point_towards_target(
    source_node_center: tuple[float, float],
    target_node_center: tuple[float, float], 
    source_ring_level: int,
    node_radius: float, # Base node radius
    get_ring_radius_method: callable
) -> tuple[float, float]:
    
    source_eff_radius = get_ring_radius_method(source_ring_level)
    
    s_center_x, s_center_y = source_node_center
    t_center_x, t_center_y = target_node_center

    vec_x = t_center_x - s_center_x
    vec_y = t_center_y - s_center_y

    if abs(vec_x) < 1e-6 and abs(vec_y) < 1e-6: # Source and target centers are coincident
        # Default connection point (e.g., pointing downwards from source)
        return (s_center_x, s_center_y + source_eff_radius)

    vec_length = math.sqrt(vec_x**2 + vec_y**2)

    if vec_length < 1e-6: # Should be caught by above, but as a safeguard
        return (s_center_x, s_center_y + source_eff_radius)
    
    unit_vec_x = vec_x / vec_length
    unit_vec_y = vec_y / vec_length

    connection_x = s_center_x + unit_vec_x * source_eff_radius
    connection_y = s_center_y + unit_vec_y * source_eff_radius
    
    return (connection_x, connection_y)


def calculate_trace_path(
    start_node_name: str,
    end_node_name: str,
    start_ring_level: int,
    end_ring_level: int,
    all_node_positions: dict[str, tuple[float, float]],
    node_layout: list[list[str]], 
    node_radius: float, 
    get_ring_radius_method: callable,
    short_stub_length_factor: float = 0.5 # Default stub length factor
) -> list[tuple[float, float]]:
    
    s_center = all_node_positions[start_node_name]
    e_center = all_node_positions[end_node_name]

    # 1. Calculate s_circum and e_circum based on direct vector between node centers
    s_circum = _calculate_circumference_point_towards_target(
        s_center, e_center, start_ring_level, node_radius, get_ring_radius_method
    )
    e_circum = _calculate_circumference_point_towards_target(
        e_center, s_center, end_ring_level, node_radius, get_ring_radius_method # Reversed for correct direction
    )

    # Check for direct alignment or very close points
    # These checks are based on the s_circum and e_circum points
    is_directly_horizontal = abs(s_circum[1] - e_circum[1]) < 1e-3
    is_directly_vertical = abs(s_circum[0] - e_circum[0]) < 1e-3
    points_coincident = _points_are_close(s_circum, e_circum)

    path_points: list[tuple[float,float] | None]

    if points_coincident: # If circumference points ended up being the same
        return [s_circum] # Path of one point
    
    if is_directly_horizontal or is_directly_vertical:
        path_points = [s_circum, e_circum]
    else:
        # Diagonal Pathing: Short-Long-Short (S_circum -> P1 -> P2 -> E_circum)
        sx, sy = s_circum
        ex, ey = e_circum
        
        dx_circ_to_circ = ex - sx # Delta between circumference connection points
        dy_circ_to_circ = ey - sy

        stub_len = node_radius * short_stub_length_factor
        
        p1: tuple[float, float] # End of first stub
        p2: tuple[float, float] # Start of second stub (P1-P2 is the "long" segment)

        if abs(dx_circ_to_circ) >= abs(dy_circ_to_circ): # Path is wider than tall, or square
            # Initial stub is horizontal from S_circum
            p1 = (sx + stub_len * _sign(dx_circ_to_circ), sy)
            # Final stub is vertical to E_circum (P2 is offset vertically from e_circum)
            p2 = (ex, ey - stub_len * _sign(dy_circ_to_circ))
        else: # Path is taller than wide
            # Initial stub is vertical from S_circum
            p1 = (sx, sy + stub_len * _sign(dy_circ_to_circ))
            # Final stub is horizontal to E_circum (P2 is offset horizontally from e_circum)
            p2 = (ex - stub_len * _sign(dx_circ_to_circ), ey)

        path_points = [s_circum]
        if not _points_are_close(s_circum, p1):
            path_points.append(p1)
        
        # If P1 and P2 are very close, it means stubs met or crossed.
        # The path effectively becomes S_circum -> P1 (or P2) -> E_circum.
        if not _points_are_close(p1, p2): 
            if not _points_are_close(path_points[-1], p2):
                path_points.append(p2)
        
        if not _points_are_close(path_points[-1], e_circum):
            path_points.append(e_circum)
            
        # Fallback if the logic resulted in a degenerate path (e.g., just S-E for a diagonal)
        # This can happen if stub_len is too large relative to dx_circ_to_circ/dy_circ_to_circ
        # or if P1/P2 end up coincident or collinear in a way that simplifies to S-E.
        is_simple_s_e = (len(path_points) == 2 and 
                           _points_are_close(path_points[0], s_circum) and 
                           _points_are_close(path_points[1], e_circum))
                           
        if is_simple_s_e and not (is_directly_horizontal or is_directly_vertical):
             # If it simplified to S_circum-E_circum but wasn't originally H/V, use simple L-bend.
             intermediate_corner = (ex, sy) # H-first L-bend from s_circum
             path_points = [s_circum, intermediate_corner, e_circum]

    # Clean up consecutive duplicate points from the final list
    final_path_tuples: list[tuple[float,float]] = []
    if path_points:
        current_first_point = path_points[0]
        if current_first_point is None: # Should not happen if logic above is sound
            return [s_circum, e_circum] if not _points_are_close(s_circum, e_circum) else [s_circum]
        
        final_path_tuples.append(current_first_point)
        for i in range(1, len(path_points)):
            current_point = path_points[i]
            if current_point is not None and not _points_are_close(current_point, final_path_tuples[-1]):
                final_path_tuples.append(current_point)
    
    # Ensure path has at least two distinct points if s_circum and e_circum were different
    if len(final_path_tuples) < 2 and not _points_are_close(s_circum, e_circum):
        return [s_circum, e_circum]
    if not final_path_tuples: # Absolute fallback
        return [s_circum, e_circum] if not _points_are_close(s_circum, e_circum) else [s_circum]
        
    return final_path_tuples


if __name__ == '__main__':
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

    print("--- Trace Router Tests (Reverted to \"Off-Center\" S-P1-P2-E Diagonals) ---")
    stub_factor_test = 0.5 # User: "make the initial segment a bit longer"

    test_cases = [
        ("ABC", "DEF", 0, 0, "H-aligned"),
        ("ABC", "JKL", 0, 0, "V-aligned"),
        ("ABC", "MNO", 0, 0, "Diagonal 1 (main, dx_circ=dy_circ)"), 
        ("MNO", "STU", 0, 0, "MNO to STU (Image example base)"), 
        ("STU", "GHI", 0, 0, "STU to GHI (Image example base)"), 
        ("ABC", "PQR", 0, 0, "Diagonal 2 (wide, dx_circ > dy_circ)"), 
        ("ABC", "VWX", 0, 0, "Diagonal 3 (tall, dy_circ > dx_circ)"), 
        ("GHI", "JKL", 0, 0, "Diagonal 4 (TR to ML)"),
        ("DEF", "JKL", 0, 0, "Diagonal 5 (TC to ML)"),
        ("YZ", "STU", 0, 0, "H-aligned variation BR to BL"),
        ("ABC", "YZ", 0, 0, "Full Diagonal TL to BR"),
        ("GHI", "STU", 0, 0, "Full Diagonal TR to BL"),
        ("ABC", "MNO", 1, 1, "Diagonal with Rings R1-R1"),
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