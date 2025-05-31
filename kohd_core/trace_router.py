# kohd_translator/kohd_core/trace_router.py
import math

# Threshold for considering points equal
POINT_CLOSE_TOLERANCE = 1e-3
# Tolerance for alignment checks (e.g. H/V alignment)
ALIGN_TOLERANCE = 0.1
# Minimum acceptable stub length, to prevent zero or negative length stubs
MIN_STUB_LENGTH_THRESHOLD_FACTOR = 0.05 # Factor of node_radius

def _get_node_rc(node_name: str, node_layout: list[list[str]]) -> tuple[int | None, int | None]:
    for r_idx, row in enumerate(node_layout):
        try:
            c_idx = row.index(node_name)
            return r_idx, c_idx
        except ValueError:
            continue
    return None, None

def _sign(val: float) -> int:
    if abs(val) < 1e-9: 
        return 1 
    return 1 if val > 0 else -1

def _points_are_close(p1: tuple[float,float] | None, p2: tuple[float,float] | None, tol: float = POINT_CLOSE_TOLERANCE) -> bool:
    if p1 is None or p2 is None: return p1 == p2
    return abs(p1[0] - p2[0]) < tol and abs(p1[1] - p2[1]) < tol

def _dist_sq(p1: tuple[float,float], p2: tuple[float,float]) -> float:
    """Calculates the squared distance between two points."""
    return (p1[0] - p2[0])**2 + (p1[1] - p2[1])**2

def _segment_intersects_circle(p1: tuple[float,float], p2: tuple[float,float], 
                               circle_center: tuple[float,float], circle_radius: float,
                               line_only: bool = False) -> bool:
    """Checks if a line segment (p1, p2) intersects a circle.
       If line_only is True, checks intersection of the infinite line through p1,p2.
    """
    cc_x, cc_y = circle_center
    r_sq = circle_radius**2

    if not line_only:
        if _dist_sq(p1, circle_center) <= r_sq: return True
        if _dist_sq(p2, circle_center) <= r_sq: return True

    p1_x, p1_y = p1
    p2_x, p2_y = p2
    dp_x = p2_x - p1_x
    dp_y = p2_y - p1_y

    if abs(dp_x) < 1e-9 and abs(dp_y) < 1e-9: 
        return False 

    # Avoid division by zero if segment has zero length (already checked by dp_x/dp_y check)
    len_sq_p2_p1 = dp_x**2 + dp_y**2
    if len_sq_p2_p1 < 1e-12: return False


    t = ((cc_x - p1_x) * dp_x + (cc_y - p1_y) * dp_y) / len_sq_p2_p1
    closest_x, closest_y = p1_x + t * dp_x, p1_y + t * dp_y
    dist_to_closest_sq = _dist_sq((closest_x, closest_y), circle_center)

    if dist_to_closest_sq > r_sq + 1e-9: # Add tolerance for float comparison
        return False 

    if line_only:
        return True
        
    if t >= -1e-9 and t <= 1.0 + 1e-9: # Add tolerance for t check
        return True
    
    return False


def calculate_trace_path(
    start_node_name: str,
    end_node_name: str,
    start_ring_level: int,
    end_ring_level: int,
    all_node_positions: dict[str, tuple[float, float]],
    node_layout: list[list[str]], 
    node_radius: float,
    get_ring_radius_method: callable,
    obstacle_node_coords: list[tuple[float,float]] | None = None, 
    short_stub_length_factor: float = 0.5,
    start_offset_idx: int = 0,
    end_offset_idx: int = 0,
    offset_factor: float = 0.25
) -> list[tuple[float, float]]:

    s_center_x, s_center_y = all_node_positions[start_node_name]
    e_center_x, e_center_y = all_node_positions[end_node_name]

    s_eff_radius = get_ring_radius_method(start_ring_level)
    e_eff_radius = get_ring_radius_method(end_ring_level)

    dx_centers = e_center_x - s_center_x
    dy_centers = e_center_y - s_center_y

    min_len_threshold = node_radius * MIN_STUB_LENGTH_THRESHOLD_FACTOR 

    path_points: list[tuple[float,float] | None] = []
    
    start_offset_val = start_offset_idx * node_radius * offset_factor
    end_offset_val = end_offset_idx * node_radius * offset_factor

    s_on_face: tuple[float,float]
    e_on_face: tuple[float,float]
    
    u_s_stub_dir: tuple[float, float]
    u_e_stub_dir: tuple[float, float]


    if abs(dx_centers) < ALIGN_TOLERANCE:  # Vertically aligned centers
        s_on_face_base_y = s_center_y + s_eff_radius * _sign(dy_centers)
        s_on_face_no_offset = (s_center_x, s_on_face_base_y)
        u_s_stub_dir = (0.0, float(_sign(dy_centers))) # Stub is Vertical

        e_on_face_base_y = e_center_y - e_eff_radius * _sign(dy_centers)
        e_on_face_no_offset = (e_center_x, e_on_face_base_y)
        u_e_stub_dir = (0.0, float(-_sign(dy_centers))) # Stub is Vertical

        if start_ring_level > 0 and start_offset_idx != 0 and s_eff_radius > 1e-6:
            angle_no_offset = math.atan2(s_on_face_no_offset[1] - s_center_y, s_on_face_no_offset[0] - s_center_x)
            # For a vertical stub, offset_val is applied horizontally.
            # A positive offset_idx usually means offset in +X direction for vertical stubs (T/B faces).
            # If s_on_face_no_offset is on South face (angle -pi/2), +X offset is CW.
            # If s_on_face_no_offset is on North face (angle pi/2), +X offset is CCW.
            # To make positive offset_idx consistently CCW tangent:
            # Need to consider the orientation of the "face" the offset_val is applied along.
            # Let's define that a positive offset_val results in a CCW angular shift.
            angular_shift = start_offset_val / s_eff_radius 
            final_angle = angle_no_offset + angular_shift 
            s_on_face = (s_center_x + s_eff_radius * math.cos(final_angle), 
                         s_center_y + s_eff_radius * math.sin(final_angle))
            # u_s_stub_dir remains (0, _sign(dy_centers)) - strictly vertical
        else: 
            s_on_face = (s_center_x + start_offset_val, s_on_face_base_y) # Offset applied to X for V-stub base

        if end_ring_level > 0 and end_offset_idx != 0 and e_eff_radius > 1e-6:
            angle_no_offset = math.atan2(e_on_face_no_offset[1] - e_center_y, e_on_face_no_offset[0] - e_center_x)
            angular_shift = end_offset_val / e_eff_radius 
            final_angle = angle_no_offset + angular_shift
            e_on_face = (e_center_x + e_eff_radius * math.cos(final_angle), 
                         e_center_y + e_eff_radius * math.sin(final_angle))
            # u_e_stub_dir remains (0, -_sign(dy_centers)) - strictly vertical
        else: 
            e_on_face = (e_center_x + end_offset_val, e_on_face_base_y) # Offset applied to X for V-stub base
        
        path_points = [s_on_face, e_on_face]

    elif abs(dy_centers) < ALIGN_TOLERANCE:  # Horizontally aligned centers
        s_on_face_base_x = s_center_x + s_eff_radius * _sign(dx_centers)
        s_on_face_no_offset = (s_on_face_base_x, s_center_y)
        u_s_stub_dir = (float(_sign(dx_centers)), 0.0) # Stub is Horizontal

        e_on_face_base_x = e_center_x - e_eff_radius * _sign(dx_centers)
        e_on_face_no_offset = (e_on_face_base_x, e_center_y)
        u_e_stub_dir = (float(-_sign(dx_centers)), 0.0) # Stub is Horizontal

        if start_ring_level > 0 and start_offset_idx != 0 and s_eff_radius > 1e-6:
            angle_no_offset = math.atan2(s_on_face_no_offset[1] - s_center_y, s_on_face_no_offset[0] - s_center_x)
            # For a horizontal stub, offset_val is applied vertically.
            # Positive offset_idx usually means offset in +Y direction for horizontal stubs (L/R faces).
            # If on East face (angle 0), +Y offset is CCW. If on West face (angle pi), +Y offset is CW.
            # Consistent CCW angular shift for positive offset_val.
            angular_shift = start_offset_val / s_eff_radius 
            final_angle = angle_no_offset + angular_shift
            s_on_face = (s_center_x + s_eff_radius * math.cos(final_angle), 
                         s_center_y + s_eff_radius * math.sin(final_angle))
            # u_s_stub_dir remains (_sign(dx_centers), 0.0) - strictly horizontal
        else:
            s_on_face = (s_on_face_base_x, s_center_y + start_offset_val) # Offset applied to Y for H-stub base

        if end_ring_level > 0 and end_offset_idx != 0 and e_eff_radius > 1e-6:
            angle_no_offset = math.atan2(e_on_face_no_offset[1] - e_center_y, e_on_face_no_offset[0] - e_center_x)
            angular_shift = end_offset_val / e_eff_radius
            final_angle = angle_no_offset + angular_shift
            e_on_face = (e_center_x + e_eff_radius * math.cos(final_angle), 
                         e_center_y + e_eff_radius * math.sin(final_angle))
            # u_e_stub_dir remains (-_sign(dx_centers), 0.0) - strictly horizontal
        else:
            e_on_face = (e_on_face_base_x, e_center_y + end_offset_val) # Offset applied to Y for H-stub base

        path_points = [s_on_face, e_on_face]

    else: # --- Diagonal Case ---
        s_stub_is_horizontal = abs(dx_centers) >= abs(dy_centers)
        # For diagonal, e_stub_is_horizontal usually mirrors s_stub_is_horizontal for parallel main segment
        e_stub_is_horizontal = s_stub_is_horizontal 

        s_on_face_no_offset: tuple[float,float]
        cartesian_offset_s_vec: tuple[float,float] 

        if s_stub_is_horizontal: 
            s_on_face_no_offset = (s_center_x + s_eff_radius * _sign(dx_centers), s_center_y)
            u_s_stub_dir = (float(_sign(dx_centers)), 0.0)
            cartesian_offset_s_vec = (0.0, start_offset_val) # Offset is vertical
        else: 
            s_on_face_no_offset = (s_center_x, s_center_y + s_eff_radius * _sign(dy_centers))
            u_s_stub_dir = (0.0, float(_sign(dy_centers)))
            cartesian_offset_s_vec = (start_offset_val, 0.0) # Offset is horizontal
        
        if start_ring_level > 0 and start_offset_idx != 0 and s_eff_radius > 1e-6:
            angle_no_offset = math.atan2(s_on_face_no_offset[1] - s_center_y, s_on_face_no_offset[0] - s_center_x)
            # Use the original linear offset_val as the arc length.
            # The sign of angular_shift needs to be consistent.
            # If offset_s_vec was (0, val_y) and s_on_face_no_offset was on +X face, val_y > 0 is CCW.
            # If offset_s_vec was (val_x, 0) and s_on_face_no_offset was on +Y face, val_x > 0 is CCW from +Y view.
            # For simplicity, let positive offset_idx (hence positive start_offset_val if factor >0) be CCW.
            angular_shift = start_offset_val / s_eff_radius 
            final_angle = angle_no_offset + angular_shift
            s_on_face = (s_center_x + s_eff_radius * math.cos(final_angle), 
                         s_center_y + s_eff_radius * math.sin(final_angle))
            # u_s_stub_dir STAYS as the H/V direction determined by s_stub_is_horizontal
        else: 
            s_on_face = (s_on_face_no_offset[0] + cartesian_offset_s_vec[0], 
                         s_on_face_no_offset[1] + cartesian_offset_s_vec[1])
            # u_s_stub_dir is already set based on s_stub_is_horizontal

        # --- End Node (Diagonal) ---
        e_on_face_no_offset: tuple[float,float]
        cartesian_offset_e_vec: tuple[float,float]

        if e_stub_is_horizontal: 
            e_on_face_no_offset = (e_center_x - e_eff_radius * _sign(dx_centers), e_center_y)
            u_e_stub_dir = (float(-_sign(dx_centers)), 0.0) 
            cartesian_offset_e_vec = (0.0, end_offset_val) 
        else: 
            e_on_face_no_offset = (e_center_x, e_center_y - e_eff_radius * _sign(dy_centers))
            u_e_stub_dir = (0.0, float(-_sign(dy_centers)))
            cartesian_offset_e_vec = (end_offset_val, 0.0)

        if end_ring_level > 0 and end_offset_idx != 0 and e_eff_radius > 1e-6:
            angle_no_offset = math.atan2(e_on_face_no_offset[1] - e_center_y, e_on_face_no_offset[0] - e_center_x)
            angular_shift = end_offset_val / e_eff_radius 
            final_angle = angle_no_offset + angular_shift
            e_on_face = (e_center_x + e_eff_radius * math.cos(final_angle), 
                         e_center_y + e_eff_radius * math.sin(final_angle))
            # u_e_stub_dir STAYS as the H/V direction determined by e_stub_is_horizontal
        else: 
            e_on_face = (e_on_face_no_offset[0] + cartesian_offset_e_vec[0], 
                         e_on_face_no_offset[1] + cartesian_offset_e_vec[1])
            # u_e_stub_dir is already set based on e_stub_is_horizontal
        
        kohd_slope_magnitude = 2.5 
        m_k: float
        if abs(dx_centers) < 1e-6 : 
            m_k = float('inf') 
        else:
            m_k = (_sign(dy_centers) * _sign(dx_centers)) * kohd_slope_magnitude 
            if abs(m_k) > 1e7: m_k = float('inf')

        Ls: float = node_radius * short_stub_length_factor 
        Le: float = node_radius * short_stub_length_factor 

        if m_k == float('inf'): 
            denom_L_vertical = u_s_stub_dir[0] - u_e_stub_dir[0] 
            if abs(denom_L_vertical) > 1e-6:
                L_adj = (e_on_face[0] - s_on_face[0]) / denom_L_vertical
                if L_adj >= min_len_threshold: Ls = Le = L_adj
                else: 
                    Ls = node_radius * short_stub_length_factor
                    if abs(u_e_stub_dir[0]) > 1e-6 :
                        Le_calc = (s_on_face[0] + Ls * u_s_stub_dir[0] - e_on_face[0]) / u_e_stub_dir[0]
                        Le = Le_calc if Le_calc >= min_len_threshold else node_radius * short_stub_length_factor
                    else: Le = node_radius * short_stub_length_factor
        else: 
            coeff_Le_val = (u_e_stub_dir[1] - m_k * u_e_stub_dir[0])
            coeff_Ls_val = -(u_s_stub_dir[1] - m_k * u_s_stub_dir[0]) 
            constant_val = m_k * (e_on_face[0] - s_on_face[0]) - (e_on_face[1] - s_on_face[1])

            if abs(coeff_Le_val + coeff_Ls_val) > 1e-6: 
                L_adj = constant_val / (coeff_Le_val + coeff_Ls_val)
                if L_adj >= min_len_threshold: Ls = Le = L_adj
                else: 
                    Ls = node_radius * short_stub_length_factor
                    if abs(coeff_Le_val) > 1e-6:
                        Le_calc = (constant_val - Ls * coeff_Ls_val) / coeff_Le_val
                        Le = Le_calc if Le_calc >= min_len_threshold else node_radius * short_stub_length_factor
                    else: Le = node_radius * short_stub_length_factor
            else:
                pass 

        if Ls < min_len_threshold : Ls = min_len_threshold
        if Le < min_len_threshold : Le = min_len_threshold
        
        p_A = (s_on_face[0] + Ls * u_s_stub_dir[0], s_on_face[1] + Ls * u_s_stub_dir[1])
        p_D = (e_on_face[0] + Le * u_e_stub_dir[0], e_on_face[1] + Le * u_e_stub_dir[1])
        
        path_points.append(s_on_face)
        if not _points_are_close(s_on_face, p_A): path_points.append(p_A)
        
        detour_points = []
        main_segment_collided = False
        if obstacle_node_coords and p_A and p_D: 
            for obs_coord in obstacle_node_coords:
                if _segment_intersects_circle(p_A, p_D, obs_coord, node_radius):
                    main_segment_collided = True
                    mid_ax, mid_ay = (p_A[0] + p_D[0]) / 2, (p_A[1] + p_D[1]) / 2
                    avoid_dx = mid_ax - obs_coord[0]
                    avoid_dy = mid_ay - obs_coord[1]
                    avoid_len = math.sqrt(avoid_dx**2 + avoid_dy**2)
                    avoid_norm_dx = (avoid_dx / avoid_len) if avoid_len > 1e-6 else 0
                    avoid_norm_dy = (avoid_dy / avoid_len) if avoid_len > 1e-6 else 0
                    
                    detour_pt = (mid_ax + avoid_norm_dx * node_radius * 1.5, 
                                 mid_ay + avoid_norm_dy * node_radius * 1.5)

                    if not any(_points_are_close(detour_pt, dp) for dp in detour_points):
                        detour_points.append(detour_pt)
                    break 
        
        if detour_points:
            detour_points.sort(key=lambda pt: _dist_sq(p_A, pt)) 
            for dp in detour_points:
                 if not path_points or not _points_are_close(path_points[-1], dp):
                    path_points.append(dp)

        last_added_point_before_pD = path_points[-1] if path_points else None
        if not _points_are_close(last_added_point_before_pD, p_D):
            if not main_segment_collided: 
                 if not _points_are_close(p_A, p_D): 
                    path_points.append(p_D)
            elif detour_points : 
                 path_points.append(p_D)
            elif main_segment_collided and not detour_points and not _points_are_close(p_A,p_D):
                 path_points.append(p_D)

        if not path_points or not _points_are_close(path_points[-1], e_on_face):
            path_points.append(e_on_face)

    final_path_tuples: list[tuple[float,float]] = []
    if path_points:
        valid_points = [pt for pt in path_points if pt is not None]
        if valid_points:
            final_path_tuples.append(valid_points[0])
            for i in range(1, len(valid_points)):
                if not _points_are_close(valid_points[i], final_path_tuples[-1]):
                    final_path_tuples.append(valid_points[i])
    
    if len(final_path_tuples) < 2: 
        # Fallback logic (ensure s_on_face and e_on_face are defined if they weren't)
        if 's_on_face' not in locals() or s_on_face is None: # Check if s_on_face was defined
             s_on_face_fb_is_horiz = abs(dx_centers) >= abs(dy_centers)
             s_on_face_fb_dir_x = _sign(dx_centers); s_on_face_fb_dir_y = _sign(dy_centers)
             if s_on_face_fb_is_horiz:
                 s_on_face_base_fb = (s_center_x + s_eff_radius * s_on_face_fb_dir_x, s_center_y)
                 s_on_face = (s_on_face_base_fb[0], s_on_face_base_fb[1] + start_offset_val)
             else:
                 s_on_face_base_fb = (s_center_x, s_center_y + s_eff_radius * s_on_face_fb_dir_y)
                 s_on_face = (s_on_face_base_fb[0] + start_offset_val, s_on_face_base_fb[1])
        
        if 'e_on_face' not in locals() or e_on_face is None: # Check if e_on_face was defined
             e_on_face_fb_is_horiz = abs(dx_centers) >= abs(dy_centers)
             e_on_face_fb_dir_x = _sign(dx_centers); e_on_face_fb_dir_y = _sign(dy_centers)
             if e_on_face_fb_is_horiz: 
                 e_on_face_base_fb = (e_center_x - e_eff_radius * e_on_face_fb_dir_x, e_center_y)
                 e_on_face = (e_on_face_base_fb[0], e_on_face_base_fb[1] + end_offset_val)
             else: 
                 e_on_face_base_fb = (e_center_x, e_center_y - e_eff_radius * e_on_face_fb_dir_y)
                 e_on_face = (e_on_face_base_fb[0] + end_offset_val, e_on_face_base_fb[1])

        # Ensure s_on_face and e_on_face are tuples before returning for fallback
        if isinstance(s_on_face, tuple) and isinstance(e_on_face, tuple):
            if not _points_are_close(s_on_face, e_on_face):
                return [s_on_face, e_on_face]
            else: return [s_on_face] 
        elif isinstance(s_on_face, tuple): return [s_on_face]
        else: return []
            
    return final_path_tuples


if __name__ == '__main__':
    mock_node_positions = {
        'ABC': (50, 50), 'DEF': (150, 50), 'GHI': (250, 50),
        'JKL': (50, 150), 'MNO': (150, 150), 'PQR': (250, 150),
        'STU': (50, 250), 'VWX': (150, 250), 'YZ':  (250, 250)
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

    print("--- Trace Router Tests: Angular Offset for Rings & H/V Stubs ---")
    stub_factor_test = 0.5 
    offset_f_test = 0.25

    test_cases_ring_stubs = [
        # Test case: ABC to MNO, ABC is Ring 1, offset_idx = 2 for start
        ("ABC", "MNO", 1, 0, 2, 0, "ABC(R1, off2) to MNO(R0, off0) - Diagonal"),
        # Test case: Vertical align, DEF (Ring 1, offset_idx=-2) to MNO (Ring 0)
        ("DEF", "MNO", 1, 0, -2, 0, "DEF(R1, off-2) to MNO(R0, off0) - Vertical"),
        # Test case: Horizontal align, ABC (Ring 1, offset_idx=1) to DEF (Ring 0)
        ("ABC", "DEF", 1, 0, 1, 0, "ABC(R1, off1) to DEF(R0, off0) - Horizontal")
    ]

    for start_n, end_n, s_ring, e_ring, s_off_idx, e_off_idx, desc in test_cases_ring_stubs:
        path = calculate_trace_path(
            start_n, end_n, 
            s_ring, e_ring, 
            mock_node_positions, 
            mock_node_layout, 
            mock_node_radius, 
            mock_get_ring_radius,
            start_offset_idx=s_off_idx, end_offset_idx=e_off_idx, 
            offset_factor=offset_f_test,
            short_stub_length_factor=stub_factor_test
        )
        display_path = [(round(p[0],1), round(p[1],1)) for p in path]
        s_center = mock_node_positions[start_n]
        s_eff_r = mock_get_ring_radius(s_ring)
        
        print(f"\nTest: {desc}")
        print(f"  Path: {display_path}")
        
        if path:
            s_on_f = path[0]
            dist_s_on_f_to_center = math.sqrt((s_on_f[0]-s_center[0])**2 + (s_on_f[1]-s_center[1])**2)
            print(f"  {start_n} center: {s_center}, Ring {s_ring} eff_radius: {s_eff_r:.1f}")
            print(f"  s_on_face: {s_on_f}, Dist to center: {dist_s_on_f_to_center:.1f} (should be ~{s_eff_r:.1f})")

            if len(path) > 1:
                p_A = path[1]
                stub_dx = p_A[0] - s_on_f[0]
                stub_dy = p_A[1] - s_on_f[1]
                stub_type = "Angled"
                if abs(stub_dx) < ALIGN_TOLERANCE and abs(stub_dy) > ALIGN_TOLERANCE:
                    stub_type = "Vertical"
                elif abs(stub_dy) < ALIGN_TOLERANCE and abs(stub_dx) > ALIGN_TOLERANCE:
                    stub_type = "Horizontal"
                elif _points_are_close(s_on_f, p_A):
                     stub_type = "No Stub (points close)"
                print(f"  Stub s_on_face to p_A: dx={stub_dx:.1f}, dy={stub_dy:.1f} -> Type: {stub_type}")

    print("\n--- Obstacle Tests (retaining original diagonal stub logic) ---")
    # ... (obstacle tests can remain the same as they test a different aspect)