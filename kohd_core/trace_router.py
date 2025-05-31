import math

def _get_node_rc(node_name: str, node_layout: list[list[str]]) -> tuple[int | None, int | None]:
    for r_idx, row in enumerate(node_layout):
        if node_name in row:
            return r_idx, row.index(node_name)
    return None, None

def _sign(val: float) -> int:
    if abs(val) < 1e-9: # Treat very small numbers as zero for sign determination
        return 1 # Default to positive sign for zero to avoid issues with direction
    return 1 if val > 0 else -1

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

    align_tolerance = 0.1 # Tolerance for considering nodes aligned
    min_len_threshold = node_radius * 0.05 # Minimum acceptable stub length

    path_points: list[tuple[float,float] | None] = []

    # Calculate offset distances
    # Assuming offset_idx can be positive or negative to indicate direction, or use parity for alternating.
    # For now, positive idx means one direction, will use fixed perpendicular shift.
    start_offset_val = start_offset_idx * node_radius * offset_factor
    end_offset_val = end_offset_idx * node_radius * offset_factor


    if abs(dx_centers) < align_tolerance:  # Vertically aligned centers
        s_on_face_base_y = s_center_y + s_eff_radius * _sign(dy_centers)
        e_on_face_base_y = e_center_y - e_eff_radius * _sign(dy_centers)
        
        # Offset horizontally (fixed direction for now, e.g. +X)
        s_on_face = (s_center_x + start_offset_val, s_on_face_base_y)
        e_on_face = (e_center_x + end_offset_val, e_on_face_base_y) # Potentially use different offset_idx for e_on_face
        path_points = [s_on_face, e_on_face]

    elif abs(dy_centers) < align_tolerance:  # Horizontally aligned centers
        s_on_face_base_x = s_center_x + s_eff_radius * _sign(dx_centers)
        e_on_face_base_x = e_center_x - e_eff_radius * _sign(dx_centers)

        # Offset vertically (fixed direction for now, e.g. +Y)
        s_on_face = (s_on_face_base_x, s_center_y + start_offset_val)
        e_on_face = (e_on_face_base_x, e_center_y + end_offset_val)
        path_points = [s_on_face, e_on_face]
    else:
        # --- Diagonal Case ---
        # 1. Determine base connection points and unit stub directions (away from node center)
        s_stub_is_horizontal = abs(dx_centers) >= abs(dy_centers)
        if s_stub_is_horizontal:
            s_on_face_no_offset = (s_center_x + s_eff_radius * _sign(dx_centers), s_center_y)
            u_s_stub_dir = (_sign(dx_centers), 0.0)
            offset_s_vec = (0.0, start_offset_val) # Offset along Y
        else: # Vertical start stub
            s_on_face_no_offset = (s_center_x, s_center_y + s_eff_radius * _sign(dy_centers))
            u_s_stub_dir = (0.0, _sign(dy_centers))
            offset_s_vec = (start_offset_val, 0.0) # Offset along X
        s_on_face = (s_on_face_no_offset[0] + offset_s_vec[0], s_on_face_no_offset[1] + offset_s_vec[1])

        e_stub_is_horizontal = abs(dx_centers) >= abs(dy_centers)
        if e_stub_is_horizontal: # End node receives on E/W face, stub is H
            e_on_face_no_offset = (e_center_x - e_eff_radius * _sign(dx_centers), e_center_y)
            u_e_stub_dir = (-_sign(dx_centers), 0.0) # Stub points from e_on_face away from e_center (towards s_center general area)
            offset_e_vec = (0.0, end_offset_val) 
        else: # End node receives on N/S face, stub is V
            e_on_face_no_offset = (e_center_x, e_center_y - e_eff_radius * _sign(dy_centers))
            u_e_stub_dir = (0.0, -_sign(dy_centers))
            offset_e_vec = (end_offset_val, 0.0)
        e_on_face = (e_on_face_no_offset[0] + offset_e_vec[0], e_on_face_no_offset[1] + offset_e_vec[1])

        # 2. Determine Chosen Kohd Slope (m_k)
        kohd_slope_magnitude = 2.5
        if abs(dx_centers) < 1e-6 : # Effectively vertical overall connection
            m_k = float('inf') # Represent infinite slope
        else:
            m_k = (_sign(dy_centers) * _sign(dx_centers)) * kohd_slope_magnitude
            if abs(m_k) > 1e7: m_k = float('inf') # Cap large slopes to 'inf'

        # 3. Calculate Stub Lengths (Ls, Le)
        Ls: float
        Le: float
        default_Ls = node_radius * short_stub_length_factor

        if m_k == float('inf'): # Handle vertical diagonal case: p_A_x must equal p_D_x
            # p_A_x = s_on_face[0] + Ls * u_s_stub_dir[0]
            # p_D_x = e_on_face[0] + Le * u_e_stub_dir[0]
            # s_on_face[0] + Ls * u_s_stub_dir[0] = e_on_face[0] + Le * u_e_stub_dir[0]
            # Ls * u_s_stub_dir[0] - Le * u_e_stub_dir[0] = e_on_face[0] - s_on_face[0]
            denom_L_vertical = u_s_stub_dir[0] - u_e_stub_dir[0] # Assuming Ls=Le=L
            if abs(denom_L_vertical) > 1e-6:
                L_adj = (e_on_face[0] - s_on_face[0]) / denom_L_vertical
                if L_adj >= min_len_threshold:
                    Ls = Le = L_adj
                else: # Fallback for vertical if L_adj is too small/negative
                    Ls = default_Ls
                    # Recalculate Le for vertical
                    if abs(u_e_stub_dir[0]) > 1e-6 :
                        Le = (s_on_face[0] + Ls * u_s_stub_dir[0] - e_on_face[0]) / u_e_stub_dir[0]
                        if Le < min_len_threshold: Le = default_Ls # Further fallback
                    else: # u_e_stub_dir[0] is 0, u_s_stub_dir[0] must also be 0 for this to be solvable for Ls=Le
                          # This case (overall vertical, but one stub wants to be H) implies misaligned stubs.
                          # This needs more complex handling or implies this m_k inf choice was poor.
                          # For now, use default for both.
                        Ls = Le = default_Ls
            else: # Stubs are parallel and vertical, or both horizontal. If both H, can't make p_Ax = p_Dx unless s_on_face_x = e_on_face_x
                  # This indicates an issue with forcing vertical with current stub definitions.
                Ls = Le = default_Ls
        else: # Normal slope calculation
            coeff_Le_val = (u_e_stub_dir[1] - m_k * u_e_stub_dir[0])
            coeff_Ls_val = -(u_s_stub_dir[1] - m_k * u_s_stub_dir[0]) # Coefficient for Ls
            constant_val = m_k * (e_on_face[0] - s_on_face[0]) - (e_on_face[1] - s_on_face[1])

            if abs(coeff_Le_val + coeff_Ls_val) > 1e-6: # Try Ls = Le = L_adj
                L_adj = constant_val / (coeff_Le_val + coeff_Ls_val)
                if L_adj >= min_len_threshold:
                    Ls = Le = L_adj
                else: # L_adj is too small or negative, try fixing Ls and calculate Le
                    Ls = default_Ls
                    if abs(coeff_Le_val) > 1e-6:
                        Le = (constant_val - Ls * coeff_Ls_val) / coeff_Le_val
                        if Le < min_len_threshold: Le = default_Ls # Fallback for Le
                    else: # Cannot solve for Le
                        Le = default_Ls 
            else: # Denominator for L_adj is zero, try fixing Ls
                Ls = default_Ls
                if abs(coeff_Le_val) > 1e-6:
                    Le = (constant_val - Ls * coeff_Ls_val) / coeff_Le_val
                    if Le < min_len_threshold: Le = default_Ls
                else: # Cannot solve for Le either
                    Le = default_Ls
        
        # Final check on stub lengths (ensure they are not excessively negative if logic missed it)
        if Ls < min_len_threshold : Ls = min_len_threshold
        if Le < min_len_threshold : Le = min_len_threshold

        # 4. Calculate p_A and p_D
        p_A = (s_on_face[0] + Ls * u_s_stub_dir[0], s_on_face[1] + Ls * u_s_stub_dir[1])
        p_D = (e_on_face[0] + Le * u_e_stub_dir[0], e_on_face[1] + Le * u_e_stub_dir[1])
        
        path_points.append(s_on_face)
        if not _points_are_close(s_on_face, p_A): path_points.append(p_A)
        if not _points_are_close(p_A, p_D) and (not path_points or not _points_are_close(path_points[-1], p_D)):
            path_points.append(p_D)
        if not path_points or not _points_are_close(path_points[-1], e_on_face):
            path_points.append(e_on_face)

    # --- Cleanup and Fallback ---
    final_path_tuples: list[tuple[float,float]] = []
    if path_points:
        first_valid_point_idx = -1
        for i, pt in enumerate(path_points):
            if pt is not None: first_valid_point_idx = i; break
        
        if first_valid_point_idx != -1:
            final_path_tuples.append(path_points[first_valid_point_idx])
            for i in range(first_valid_point_idx + 1, len(path_points)):
                current_point = path_points[i]
                if current_point is not None and not _points_are_close(current_point, final_path_tuples[-1]):
                    final_path_tuples.append(current_point)

    if len(final_path_tuples) < 2:
        # Fallback to direct connection if path construction failed
        # (Re-calculate s_on_face/e_on_face with offsets for this fallback if not already defined in scope)
        if 's_on_face' not in locals() or s_on_face is None : # Should be defined from diagonal or aligned block
             s_on_face_fb_is_horiz = abs(dx_centers) >= abs(dy_centers)
             s_on_face_fb_dir_x = _sign(dx_centers); s_on_face_fb_dir_y = _sign(dy_centers)
             if s_on_face_fb_is_horiz:
                 s_on_face_base_fb = (s_center_x + s_eff_radius * s_on_face_fb_dir_x, s_center_y)
                 s_on_face = (s_on_face_base_fb[0], s_on_face_base_fb[1] + start_offset_val)
             else:
                 s_on_face_base_fb = (s_center_x, s_center_y + s_eff_radius * s_on_face_fb_dir_y)
                 s_on_face = (s_on_face_base_fb[0] + start_offset_val, s_on_face_base_fb[1])
        
        if 'e_on_face' not in locals() or e_on_face is None :
             e_on_face_fb_is_horiz = abs(dx_centers) >= abs(dy_centers)
             e_on_face_fb_dir_x = _sign(dx_centers); e_on_face_fb_dir_y = _sign(dy_centers)
             if e_on_face_fb_is_horiz:
                 e_on_face_base_fb = (e_center_x - e_eff_radius * e_on_face_fb_dir_x, e_center_y)
                 e_on_face = (e_on_face_base_fb[0], e_on_face_base_fb[1] + end_offset_val)
             else:
                 e_on_face_base_fb = (e_center_x, e_center_y - e_eff_radius * e_on_face_fb_dir_y)
                 e_on_face = (e_on_face_base_fb[0] + end_offset_val, e_on_face_base_fb[1])

        if not _points_are_close(s_on_face, e_on_face):
            return [s_on_face, e_on_face]
        else:
            return [s_on_face] if s_on_face is not None else [] # Return empty if s_on_face somehow None
            
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

    print("--- Trace Router Tests with Updated Stub Logic and Slope Correction ---")
    stub_factor_test = 0.5 
    offset_f_test = 0.25

    test_cases = [
        # Aligned cases
        ("ABC", "DEF", 0, 0, "H-aligned, no offset", 0, 0),
        ("ABC", "DEF", 0, 0, "H-aligned, s_offset=1", 1, 0),
        ("ABC", "JKL", 0, 0, "V-aligned, no offset", 0, 0),
        ("ABC", "JKL", 0, 0, "V-aligned, s_offset=1", 1, 0),
        # Diagonal cases
        ("MNO", "STU", 0, 0, "MNO to STU (Q3-like), no offset", 0, 0), # Down-Left
        ("MNO", "STU", 0, 0, "MNO to STU (Q3-like), s_offset=1", 1, 0),
        ("STU", "MNO", 0, 0, "STU to MNO (Q1-like), no offset", 0, 0), # Up-Right
        ("STU", "MNO", 0, 0, "STU to MNO (Q1-like), s_offset=1", 1, 0),
        ("STU", "GHI", 0, 0, "STU to GHI (Q2-like), no offset", 0, 0), # Up-Right (corrected, STU is bottom-left, GHI is top-right)
                                                                        # STU (50,250) GHI (250,50) -> dx=200, dy=-200 (Q4-like from STU)
        ("STU", "GHI", 0, 0, "STU to GHI (Q4-like), s_offset=1", 1, 0),
        ("ABC", "MNO", 0, 0, "ABC to MNO (Q1-like), no offset", 0, 0), # Down-Right
        ("ABC", "MNO", 0, 0, "ABC to MNO (Q1-like), s_offset=1", 1, 0),
        ("GHI", "MNO", 0, 0, "GHI to MNO (Q2-like), no offset", 0, 0), # Down-Left
                                                                        # GHI (250,50) MNO (150,150) -> dx=-100, dy=100 (Q2-like from GHI)
        ("GHI", "MNO", 0, 0, "GHI to MNO (Q2-like), s_offset=1", 1, 0),
        ("ABC", "YZ", 0, 0, "ABC to YZ (Q1-like long), no offset", 0, 0),
        ("YZ", "ABC", 0, 0, "YZ to ABC (Q3-like long), no offset", 0, 0)
    ]

    for start, end, r1, r2, desc, s_off_idx, e_off_idx in test_cases:
        path = calculate_trace_path(
            start, end, r1, r2,
            mock_node_positions, mock_node_layout,
            mock_node_radius, mock_get_ring_radius,
            short_stub_length_factor=stub_factor_test,
            start_offset_idx=s_off_idx,
            end_offset_idx=e_off_idx, # Using same offset_idx for end for simplicity here
            offset_factor=offset_f_test
        )
        display_path = [(round(p[0],1), round(p[1],1)) for p in path]
        
        slope_str = "N/A"
        if len(path) == 4 and "like" in desc : # For 4-point diagonal paths s_on_face, p_A, p_D, e_on_face
            p_A_calc = path[1]
            p_D_calc = path[2]
            dx_diag = p_D_calc[0] - p_A_calc[0]
            dy_diag = p_D_calc[1] - p_A_calc[1]
            if abs(dx_diag) < 1e-6:
                slope_str = "inf" if abs(dy_diag) > 1e-6 else "undef (pA,pD close)"
            else:
                slope_val = dy_diag / dx_diag
                slope_str = f"{slope_val:.2f}"
        elif len(path) == 2 and ("aligned" in desc): # For H/V aligned direct paths
             dx_aligned = path[1][0] - path[0][0]
             dy_aligned = path[1][1] - path[0][1]
             if abs(dx_aligned) < 1e-6:
                 slope_str = "inf" if abs(dy_aligned) > 1e-6 else "undef (pts close)"
             elif abs(dy_aligned) < 1e-6:
                 slope_str = "0.00" if abs(dx_aligned) > 1e-6 else "undef (pts close)"
             else: # Should not happen for aligned if truly aligned by check
                 slope_val = dy_aligned / dx_aligned
                 slope_str = f"{slope_val:.2f} (direct)"
        
        s_node_pos = mock_node_positions[start]
        e_node_pos = mock_node_positions[end]
        overall_dx = round(e_node_pos[0] - s_node_pos[0],0)
        overall_dy = round(e_node_pos[1] - s_node_pos[1],0)

        print(f"Path {start}(R{r1},off{s_off_idx}) to {end}(R{r2},off{e_off_idx}) (dx:{overall_dx}, dy:{overall_dy}) ({desc}): {display_path} | Slope(pA-pD): {slope_str}")