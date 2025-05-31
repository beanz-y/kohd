# kohd_translator/kohd_core/glyph_builder.py
from .kohd_rules import LETTER_TO_NODE_INFO, NODE_POSITIONS, NODE_LAYOUT
from .trace_router import calculate_trace_path 
import math

class KohdGlyphBuilder:
    def __init__(self, node_radius: float, get_ring_radius_method: callable): 
        self.rules = {
            'letter_to_node_info': LETTER_TO_NODE_INFO,
            'node_positions': NODE_POSITIONS,
            'node_layout': NODE_LAYOUT,
        }
        self.node_name_to_row_col = {
            name: (r, c)
            for r, row_list in enumerate(self.rules['node_layout'])
            for c, name in enumerate(row_list)
        }
        self.preferred_corner_nodes_for_null_modifier = [
            self.rules['node_layout'][0][2], 
            self.rules['node_layout'][2][2], 
            self.rules['node_layout'][2][0], 
            self.rules['node_layout'][0][0]  
        ]
        
        self.node_radius_for_router = node_radius
        self.get_ring_radius_method_for_router = get_ring_radius_method
        
        self.node_connection_manager = {} 
        self.reset()

    def reset(self):
        self.current_word_string = ""
        self.active_node_name = None
        self.first_node_name = None
        self.subnode_queue = []
        self.glyph_elements = []
        self.is_finalized = False
        self.current_word_used_node_names = set()
        self.node_connection_manager.clear() 

    def _get_or_create_node_element_data(self, node_name, node_elements_data_map):
        if node_name not in node_elements_data_map:
            node_elements_data_map[node_name] = {
                'type': 'node', 'name': node_name,
                'coords': self.rules['node_positions'][node_name],
                'is_active': False, 'ring_count': 0 
            }
        return node_elements_data_map[node_name]

    def _determine_connection_face(self, from_node_coords: tuple[float, float], to_node_coords: tuple[float, float]) -> str:
        dx = to_node_coords[0] - from_node_coords[0]
        dy = to_node_coords[1] - from_node_coords[1] 

        if abs(dx) < 1e-6 and abs(dy) < 1e-6: 
             # Should ideally not happen if from_node != to_node, but as a fallback:
            return 'E' 

        if abs(dx) >= abs(dy): 
            return 'E' if dx > 0 else 'W'
        else:  
            return 'S' if dy > 0 else 'N'

    def _get_next_offset_idx(self, node_name: str, face_key: str) -> int:
        # Key for manager is (node_name, face_key), ignoring ring_level for offset pool
        node_face_tuple = (node_name, face_key)

        if node_face_tuple not in self.node_connection_manager:
            self.node_connection_manager[node_face_tuple] = []
        
        used_indices_for_face = self.node_connection_manager[node_face_tuple]
        
        offset_idx_to_try = 0
        if 0 not in used_indices_for_face:
            offset_idx_to_try = 0
        else:
            i = 1
            max_offset_magnitude = 5 
            found = False
            while i <= max_offset_magnitude:
                if i not in used_indices_for_face:
                    offset_idx_to_try = i
                    found = True; break
                if -i not in used_indices_for_face:
                    offset_idx_to_try = -i
                    found = True; break
                i += 1
            if not found: 
                offset_idx_to_try = i 
                while offset_idx_to_try in used_indices_for_face: # Ensure positive fallback is also unique
                    offset_idx_to_try +=1
        
        used_indices_for_face.append(offset_idx_to_try)
        return offset_idx_to_try

    def _rebuild_glyph_elements_for_string(self):
        self.glyph_elements = []
        self.node_connection_manager.clear() 
        
        current_node_data_map = {}
        _current_processing_active_node_name = None
        _first_node_name_for_this_word = None
        _subnode_queue_for_current_trace = []
        _nodes_that_have_been_departed_from = set()

        self.current_word_used_node_names.clear()
        if not self.current_word_string:
            self.active_node_name = None; self.first_node_name = None; self.subnode_queue = []
            return

        for char_code_init_pass in self.current_word_string:
            letter_init_pass = char_code_init_pass.upper()
            if letter_init_pass in self.rules['letter_to_node_info']:
                self.current_word_used_node_names.add(self.rules['letter_to_node_info'][letter_init_pass]['node_name'])

        for i, char_code in enumerate(self.current_word_string):
            letter = char_code.upper()
            if letter not in self.rules['letter_to_node_info']: continue

            letter_info = self.rules['letter_to_node_info'][letter]
            target_node_name_for_letter = letter_info['node_name']
            subnode_info_for_letter = {'letter': letter, 'count': letter_info['subnodes']}

            target_node_data = self._get_or_create_node_element_data(target_node_name_for_letter, current_node_data_map)

            if i == 0:
                _first_node_name_for_this_word = target_node_name_for_letter
                _current_processing_active_node_name = target_node_name_for_letter
                _subnode_queue_for_current_trace.append(subnode_info_for_letter)
            else:
                if target_node_name_for_letter == _current_processing_active_node_name:
                    _subnode_queue_for_current_trace.append(subnode_info_for_letter)
                else:
                    from_node_name_for_trace = _current_processing_active_node_name
                    from_node_data = current_node_data_map[from_node_name_for_trace]

                    _nodes_that_have_been_departed_from.add(from_node_name_for_trace)
                    is_return_to_target_node = target_node_name_for_letter in _nodes_that_have_been_departed_from

                    origin_connect_ring_level = from_node_data.get('ring_count', 0)
                    target_connect_ring_level = target_node_data.get('ring_count', 0)
                    
                    from_node_coords = self.rules['node_positions'][from_node_name_for_trace]
                    to_node_coords = self.rules['node_positions'][target_node_name_for_letter]

                    exit_face = self._determine_connection_face(from_node_coords, to_node_coords)
                    entry_face = self._determine_connection_face(to_node_coords, from_node_coords)

                    start_offset_idx = self._get_next_offset_idx(from_node_name_for_trace, exit_face)
                    
                    # Straight line offset consistency (Point 2)
                    dx_trace = to_node_coords[0] - from_node_coords[0]
                    dy_trace = to_node_coords[1] - from_node_coords[1]
                    align_tolerance = 0.1 # From trace_router

                    if abs(dy_trace) < align_tolerance or abs(dx_trace) < align_tolerance: # H or V aligned
                        target_node_face_tuple = (target_node_name_for_letter, entry_face)
                        # Check if target face has any offsets assigned AT ALL for this word construction
                        is_target_face_virgin = target_node_face_tuple not in self.node_connection_manager or \
                                                not self.node_connection_manager[target_node_face_tuple]
                        
                        if is_target_face_virgin:
                            end_offset_idx = start_offset_idx
                            self.node_connection_manager.setdefault(target_node_face_tuple, []).append(end_offset_idx)
                        else:
                            # If target face not virgin, try to use same offset if available, else new one.
                            # For simplicity now, if not virgin, get its own next available.
                            # A more robust solution would check if start_offset_idx is available on target.
                            if start_offset_idx not in self.node_connection_manager.get(target_node_face_tuple, []):
                                end_offset_idx = start_offset_idx
                                self.node_connection_manager.setdefault(target_node_face_tuple, []).append(end_offset_idx)
                            else:
                                end_offset_idx = self._get_next_offset_idx(target_node_name_for_letter, entry_face)
                    else: # Diagonal
                        end_offset_idx = self._get_next_offset_idx(target_node_name_for_letter, entry_face)
                        
                    calculated_path = calculate_trace_path(
                        start_node_name=from_node_name_for_trace,
                        end_node_name=target_node_name_for_letter,
                        start_ring_level=origin_connect_ring_level,
                        end_ring_level=target_connect_ring_level,
                        all_node_positions=self.rules['node_positions'],
                        node_layout=self.rules['node_layout'],
                        node_radius=self.node_radius_for_router, 
                        get_ring_radius_method=self.get_ring_radius_method_for_router,
                        start_offset_idx=start_offset_idx,
                        end_offset_idx=end_offset_idx
                    )

                    self.glyph_elements.append({
                        'type': 'trace',
                        'from_node_name': from_node_name_for_trace,
                        'to_node_name': target_node_name_for_letter,
                        'subnodes_on_trace': list(_subnode_queue_for_current_trace),
                        'connect_from_ring_level': origin_connect_ring_level,
                        'connect_to_ring_level': target_connect_ring_level,
                        'path_points': calculated_path,
                        'start_offset_idx': start_offset_idx, 
                        'end_offset_idx': end_offset_idx    
                    })
                    _subnode_queue_for_current_trace.clear()

                    if is_return_to_target_node:
                        # This logic correctly increments ring count for future returns
                        target_node_data['ring_count'] = target_connect_ring_level + 1


                    _current_processing_active_node_name = target_node_name_for_letter
                    _subnode_queue_for_current_trace.append(subnode_info_for_letter)

        self.active_node_name = _current_processing_active_node_name
        self.first_node_name = _first_node_name_for_this_word
        self.subnode_queue = list(_subnode_queue_for_current_trace)

        for node_name, data in current_node_data_map.items():
            data['is_active'] = (node_name == self.active_node_name and not self.is_finalized)
            existing_el = next((el for el in self.glyph_elements if el['type'] == 'node' and el['name'] == node_name), None)
            if not existing_el: self.glyph_elements.append(data)
            else: existing_el.update(data)

    def add_letter(self, letter: str):
        letter = letter.upper()
        if letter not in self.rules['letter_to_node_info']: return False
        self.current_word_string += letter; self.is_finalized = False
        self._rebuild_glyph_elements_for_string(); return True

    def _should_add_null_modifier(self) -> bool:
        # (Logic for _should_add_null_modifier remains unchanged from previous version)
        if not self.current_word_used_node_names or len(self.current_word_used_node_names) == 0:
            return False
        if len(self.current_word_used_node_names) >= 9: 
             return False
        if len(self.current_word_used_node_names) == 1: 
            return True
        min_r, max_r, min_c, max_c = float('inf'), float('-inf'), float('inf'), float('-inf')
        for node_name in self.current_word_used_node_names:
            r, c = self.node_name_to_row_col[node_name]
            min_r, max_r = min(min_r, r), max(max_r, r)
            min_c, max_c = min(min_c, c), max(max_c, c)
        rows_spanned = (max_r - min_r + 1)
        cols_spanned = (max_c - min_c + 1)
        if rows_spanned < 3 or cols_spanned < 3:
            if len(self.current_word_used_node_names) == 3: 
                is_collinear_h = len(set(self.node_name_to_row_col[name][0] for name in self.current_word_used_node_names)) == 1
                is_collinear_v = len(set(self.node_name_to_row_col[name][1] for name in self.current_word_used_node_names)) == 1
                if is_collinear_h or is_collinear_v: 
                    return True

                is_main_diag = all(self.node_name_to_row_col[name][0] == self.node_name_to_row_col[name][1] for name in self.current_word_used_node_names)
                is_anti_diag = all(self.node_name_to_row_col[name][0] + self.node_name_to_row_col[name][1] == 2 for name in self.current_word_used_node_names)
                
                if is_main_diag or is_anti_diag:
                    return False 
            return True 
        return False


    def _find_null_modifier_placement_node(self) -> str | None:
        # (Logic for _find_null_modifier_placement_node remains unchanged from previous version)
        if not self.current_word_used_node_names:
             pass # Will use preferred_grid_corners directly

        min_r_used, max_r_used, min_c_used, max_c_used = 0, 2, 0, 2 
        if self.current_word_used_node_names:
            min_r_used = min(self.node_name_to_row_col[n][0] for n in self.current_word_used_node_names)
            max_r_used = max(self.node_name_to_row_col[n][0] for n in self.current_word_used_node_names)
            min_c_used = min(self.node_name_to_row_col[n][1] for n in self.current_word_used_node_names)
            max_c_used = max(self.node_name_to_row_col[n][1] for n in self.current_word_used_node_names)
        
        preferred_grid_corners = [
            (2, 2, self.rules['node_layout'][2][2]), (2, 0, self.rules['node_layout'][2][0]),
            (0, 2, self.rules['node_layout'][0][2]), (0, 0, self.rules['node_layout'][0][0])
        ]

        for r_corn, c_corn, node_name_corn in preferred_grid_corners:
            is_outside_bbox = not (min_r_used <= r_corn <= max_r_used and \
                                   min_c_used <= c_corn <= max_c_used)
            if node_name_corn not in self.current_word_used_node_names and is_outside_bbox:
                return node_name_corn
        
        for _, _, node_name_corn in preferred_grid_corners:
            if node_name_corn not in self.current_word_used_node_names:
                return node_name_corn
        return None

    def finalize_word(self):
        # (Logic for finalize_word remains largely unchanged regarding ground/charge/null indicators)
        # The key changes for offsets are handled in _rebuild_glyph_elements_for_string
        if not self.current_word_string or self.is_finalized: return
        
        active_node_for_ground_trace = self.active_node_name
        if self.subnode_queue and active_node_for_ground_trace:
            active_node_final_data = next((n for n in self.glyph_elements if n['type']=='node' and n['name'] == active_node_for_ground_trace), None)
            origin_ring_level_for_ground_trace = active_node_final_data.get('ring_count', 0) if active_node_final_data else 0
            
            self.glyph_elements.append({
                'type': 'trace_to_ground',
                'from_node_name': active_node_for_ground_trace,
                'subnodes_on_trace': list(self.subnode_queue),
                'connect_from_ring_level': origin_ring_level_for_ground_trace
            }) # Note: trace_to_ground does not currently use calculate_trace_path or offsets.
               # This could be a future enhancement if ground traces also need offsetting.

        if active_node_for_ground_trace: 
            self.glyph_elements.append({'type': 'ground_indicator', 'node_name': active_node_for_ground_trace })
        
        if self.first_node_name: 
            self.glyph_elements.append({'type': 'charge_indicator', 'node_name': self.first_node_name})
        
        if self._should_add_null_modifier():
            placement_node_name = self._find_null_modifier_placement_node()
            if placement_node_name and placement_node_name in self.rules['node_positions']:
                self.glyph_elements.append({
                    'type': 'null_modifier',
                    'node_name': placement_node_name,
                    'coords': self.rules['node_positions'][placement_node_name] 
                })
        
        self.is_finalized = True
        self.active_node_name = None 
        self.subnode_queue.clear() 
        
        for el in self.glyph_elements:
            if el.get('type') == 'node':
                 el['is_active'] = False


    def get_glyph_elements(self):
        return list(self.glyph_elements)

if __name__ == '__main__':
    mock_node_radius_main = 20.0
    def mock_get_ring_radius_main(ring_level: int) -> float:
        if ring_level == 0: return mock_node_radius_main
        # Copied from canvas for more accurate testing if MAX_RINGS_TO_DRAW is relevant
        TEMP_MAX_RINGS_TO_DRAW_MOCK_BUILDER = 2 
        TEMP_RING_NODE_INSET_FACTOR_MOCK_BUILDER = 0.7
        if ring_level > 0:
            actual_ring_to_calc = min(ring_level, TEMP_MAX_RINGS_TO_DRAW_MOCK_BUILDER)
            inset_factor = TEMP_RING_NODE_INSET_FACTOR_MOCK_BUILDER - ((actual_ring_to_calc - 1) * 0.25)
            return mock_node_radius_main * max(0.1, inset_factor)
        return mock_node_radius_main


    builder = KohdGlyphBuilder(node_radius=mock_node_radius_main, get_ring_radius_method=mock_get_ring_radius_main)
    
    words_to_test_offset = ["DEFD", "MEMO", "MOTHERBOARD", "ADDDA"] 
    # ADDDA: A(ABC) D(DEF) D(DEF) D(DEF) A(ABC)
    # Trace 1: ABC -> DEF (for D)
    # (subnodes on trace: for D(DEF))
    # (D,D,D on DEF node, no new traces)
    # Trace 2: DEF -> ABC (for A)

    for word in words_to_test_offset:
        print(f"\n--- Building word: {word} ---")
        builder.reset() # Resets connection_manager
        for char_code in word:
            builder.add_letter(char_code) # This calls _rebuild, which now uses new offset logic
        
        print(f"  Connection Manager state for '{word}': {builder.node_connection_manager}")
        builder.finalize_word()
        print(f"  Glyph Elements for '{word}' after finalization ({len(builder.get_glyph_elements())}):")
        for i, element in enumerate(builder.get_glyph_elements()):
            if element['type'] == 'trace':
                print(f"    {i+1}. Type: {element['type']}, From: {element['from_node_name']}(R{element['connect_from_ring_level']}), To: {element['to_node_name']}(R{element['connect_to_ring_level']}), StartOff: {element.get('start_offset_idx')}, EndOff: {element.get('end_offset_idx')}, SubN: {len(element['subnodes_on_trace'])}")
            else:
                 print(f"    {i+1}. {element.get('type')}: {element.get('name', element.get('node_name', 'N/A'))}")


    print("\n--- Null Modifier Tests (confirming no regressions) ---")
    null_mod_tests = {
        "A": True, "HI": True, "MOM": True, "ADG": True, "AEI": False, 
        "CEG": False, "MOTHERBOARD": False, "FELLED": True, "TWO": True
    }
    for word, expects_modifier in null_mod_tests.items():
        builder.reset()
        for char_code in word: builder.add_letter(char_code)
        should_add = builder._should_add_null_modifier()
        placement = "N/A"
        if should_add: placement = builder._find_null_modifier_placement_node()
        builder.finalize_word() 
        has_modifier_element = any(el['type'] == 'null_modifier' for el in builder.get_glyph_elements())
        status = "PASS" if should_add == expects_modifier and has_modifier_element == expects_modifier else "FAIL"
        print(f"Word: '{word}', ExpMod: {expects_modifier}, Calc: {should_add}, HasElem: {has_modifier_element}, Place: {placement} -> {status}")