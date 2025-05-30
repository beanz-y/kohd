# kohd_translator/kohd_core/glyph_builder.py
from .kohd_rules import LETTER_TO_NODE_INFO, NODE_POSITIONS, NODE_LAYOUT
import math

class KohdGlyphBuilder:
    def __init__(self):
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
            self.rules['node_layout'][0][2], # GHI (Top-right)
            self.rules['node_layout'][2][2], # YZ  (Bottom-right)
            self.rules['node_layout'][2][0], # STU (Bottom-left)
            self.rules['node_layout'][0][0]  # ABC (Top-left)
        ]
        self.reset()

    def reset(self):
        self.current_word_string = ""
        self.active_node_name = None
        self.first_node_name = None
        self.subnode_queue = []
        self.glyph_elements = []
        self.is_finalized = False
        self.current_word_used_node_names = set()

    def _get_or_create_node_element_data(self, node_name, node_elements_data_map):
        if node_name not in node_elements_data_map:
            node_elements_data_map[node_name] = {
                'type': 'node', 'name': node_name,
                'coords': self.rules['node_positions'][node_name], # Storing raw coords, canvas will scale
                'is_active': False, 'ring_count': 0
            }
        return node_elements_data_map[node_name]

    def _rebuild_glyph_elements_for_string(self):
        self.glyph_elements = []
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

                    self.glyph_elements.append({
                        'type': 'trace',
                        'from_node_name': from_node_name_for_trace,
                        'to_node_name': target_node_name_for_letter,
                        'subnodes_on_trace': list(_subnode_queue_for_current_trace),
                        'connect_from_ring_level': origin_connect_ring_level,
                        'connect_to_ring_level': target_connect_ring_level,
                        'path_points': []  # Initialize path_points
                    })
                    _subnode_queue_for_current_trace.clear()

                    if is_return_to_target_node:
                        target_node_data['ring_count'] = target_connect_ring_level + 1

                    _current_processing_active_node_name = target_node_name_for_letter
                    _subnode_queue_for_current_trace.append(subnode_info_for_letter)

        self.active_node_name = _current_processing_active_node_name
        self.first_node_name = _first_node_name_for_this_word
        self.subnode_queue = list(_subnode_queue_for_current_trace)

        # Add node elements to glyph_elements
        for node_name, data in current_node_data_map.items():
            data['is_active'] = (node_name == self.active_node_name and not self.is_finalized)
            existing_el = next((el for el in self.glyph_elements if el['type'] == 'node' and el['name'] == node_name), None)
            if not existing_el: self.glyph_elements.append(data)
            else: existing_el.update(data) # Update existing if somehow already added (should be rare)

    def add_letter(self, letter: str):
        letter = letter.upper()
        if letter not in self.rules['letter_to_node_info']: return False
        self.current_word_string += letter; self.is_finalized = False
        self._rebuild_glyph_elements_for_string(); return True

    def _should_add_null_modifier(self) -> bool:
        if not self.current_word_used_node_names or len(self.current_word_used_node_names) == 0:
            return False
        if len(self.current_word_used_node_names) >= 9: # All nodes used, no ambiguity
             return False
        if len(self.current_word_used_node_names) == 1: # Single node words like "MOM"
            # As per clarification: "Words using only two nodes... require a null modifier."
            # A single node word has a limited bounding box (1x1), so it should require a modifier.
            return True

        min_r, max_r, min_c, max_c = float('inf'), float('-inf'), float('inf'), float('-inf')
        for node_name in self.current_word_used_node_names:
            r, c = self.node_name_to_row_col[node_name]
            min_r, max_r = min(min_r, r), max(max_r, r)
            min_c, max_c = min(min_c, c), max(max_c, c)

        rows_spanned = (max_r - min_r + 1)
        cols_spanned = (max_c - min_c + 1)

        # If the bounding box is smaller than 3x3 in either dimension, it implies ambiguity.
        # This covers 2-node words and 3-nodes-in-a-line.
        if rows_spanned < 3 or cols_spanned < 3:
            # Exception: 3-node words in a clear diagonal line (e.g., top-left, center, bottom-right) do NOT require it.
            if len(self.current_word_used_node_names) == 3:
                is_main_diag = all(self.node_name_to_row_col[name][0] == self.node_name_to_row_col[name][1] for name in self.current_word_used_node_names)
                is_anti_diag = all(self.node_name_to_row_col[name][0] + self.node_name_to_row_col[name][1] == 2 for name in self.current_word_used_node_names)
                if is_main_diag or is_anti_diag:
                    return False # Clear diagonal, no modifier needed
            return True
        return False


    def _find_null_modifier_placement_node(self) -> str | None:
        # Clarification logic:
        # 1. Determine minimal "bounding box". (Done implicitly by checking used nodes vs preferred corners)
        # 2. Identify corners of the 3x3 grid that fall *outside* this bounding box.
        # 3. Prioritize: bottom-right, bottom-left, top-right, top-left.

        bounding_box_nodes = set()
        if self.current_word_used_node_names:
            min_r, max_r, min_c, max_c = float('inf'), float('-inf'), float('inf'), float('-inf')
            for node_name in self.current_word_used_node_names:
                r, c = self.node_name_to_row_col[node_name]
                min_r, max_r = min(min_r, r), max(max_r, r)
                min_c, max_c = min(min_c, c), max(max_c, c)
            for r_idx in range(min_r, max_r + 1):
                for c_idx in range(min_c, max_c + 1):
                    bounding_box_nodes.add(self.rules['node_layout'][r_idx][c_idx])
        
        # Preferred corners as per clarification (inverted for direct use here)
        # Original clarification order for placement: BR, BL, TR, TL
        # We check if a preferred corner is outside the bounding box AND not used by the word itself.
        preferred_placement_order = [
            self.rules['node_layout'][2][2], # YZ (Bottom-right)
            self.rules['node_layout'][2][0], # STU (Bottom-left)
            self.rules['node_layout'][0][2], # GHI (Top-right)
            self.rules['node_layout'][0][0]  # ABC (Top-left)
        ]

        for corner_node_name in preferred_placement_order:
            if corner_node_name not in self.current_word_used_node_names and \
               corner_node_name not in bounding_box_nodes: # Check if outside bounding box implicitly
                return corner_node_name
        
        # Fallback if all corners are within bounding box (e.g. very large word) 
        # or used, though _should_add_null_modifier should prevent this if not needed.
        # If still needed, use the old logic of farthest unused from preferred list.
        unused_corners = [cn for cn in self.preferred_corner_nodes_for_null_modifier if cn not in self.current_word_used_node_names]
        if not unused_corners: return None # No place to put it

        if not self.current_word_used_node_names: return unused_corners[0]


        sum_x, sum_y = 0, 0
        num_used = len(self.current_word_used_node_names)
        if num_used == 0: return unused_corners[0]

        for node_name in self.current_word_used_node_names:
            coords = self.rules['node_positions'][node_name]
            sum_x += coords[0]; sum_y += coords[1]
        center_x = sum_x / num_used
        center_y = sum_y / num_used

        farthest_node_name = None; max_dist_sq = -1
        # Iterate through preferred_corner_nodes_for_null_modifier to respect the initial PDF example's preference
        for corner_name in self.preferred_corner_nodes_for_null_modifier:
            if corner_name in unused_corners: # Only consider those that are actually unused
                corner_coords = self.rules['node_positions'][corner_name]
                dist_sq = (corner_coords[0] - center_x)**2 + (corner_coords[1] - center_y)**2
                if dist_sq > max_dist_sq:
                    max_dist_sq = dist_sq
                    farthest_node_name = corner_name
        return farthest_node_name if farthest_node_name else unused_corners[0]


    def finalize_word(self):
        if not self.current_word_string or self.is_finalized: return

        self._rebuild_glyph_elements_for_string()

        active_node_for_ground_trace = self.active_node_name

        if self.subnode_queue and active_node_for_ground_trace:
            # Find the node data for the active node to get its final ring_count
            active_node_final_data = next((n for n in self.glyph_elements if n['type']=='node' and n['name'] == active_node_for_ground_trace), None)
            origin_ring_level_for_ground_trace = active_node_final_data.get('ring_count', 0) if active_node_final_data else 0

            self.glyph_elements.append({
                'type': 'trace_to_ground',
                'from_node_name': active_node_for_ground_trace,
                'subnodes_on_trace': list(self.subnode_queue),
                'connect_from_ring_level': origin_ring_level_for_ground_trace
            })
        if active_node_for_ground_trace: # Ensure ground indicator is only added if there's an active node
            self.glyph_elements.append({'type': 'ground_indicator', 'node_name': active_node_for_ground_trace })
        if self.first_node_name: # Ensure charge indicator is only added if there's a first node
            self.glyph_elements.append({'type': 'charge_indicator', 'node_name': self.first_node_name})

        if self._should_add_null_modifier():
            placement_node_name = self._find_null_modifier_placement_node()
            if placement_node_name and placement_node_name in self.rules['node_positions']:
                self.glyph_elements.append({
                    'type': 'null_modifier',
                    'node_name': placement_node_name,
                    'coords': self.rules['node_positions'][placement_node_name] # Store raw coords
                })

        self.is_finalized = True
        current_active_node_name_before_clear = self.active_node_name
        self.active_node_name = None
        self.subnode_queue.clear() # Clear the queue after final use

        # Update node elements to reflect no active node for drawing
        for el in self.glyph_elements:
            if el.get('type') == 'node' and el.get('name') == current_active_node_name_before_clear :
                el['is_active'] = False
            elif el.get('type') == 'node' :
                 el['is_active'] = False


    def get_glyph_elements(self):
        return list(self.glyph_elements) # Return a copy

if __name__ == '__main__':
    builder = KohdGlyphBuilder()
    words_to_test = { "HI": True, "MOM": True, "A":True, "MOTHERBOARD": False, "FELLED": True, "ACE": False } # ACE is diagonal
    for word, expects_modifier in words_to_test.items():
        print(f"\n--- Building word: {word} (Expects Modifier: {expects_modifier}) ---")
        builder.reset();
        for char_code in word: builder.add_letter(char_code)
        print(f"  Used nodes for '{word}': {builder.current_word_used_node_names}")
        needs_mod_check = builder._should_add_null_modifier()
        print(f"  _should_add_null_modifier() returns: {needs_mod_check}")
        if needs_mod_check:
            mod_node = builder._find_null_modifier_placement_node()
            print(f"  _find_null_modifier_placement_node() returns: {mod_node}")
        builder.finalize_word()
        print(f"  Glyph Elements after finalization ({len(builder.get_glyph_elements())}):")
        has_null_modifier_element = False
        for i, element in enumerate(builder.get_glyph_elements()):
             print(f"    {i+1}. {element}")
             if element.get('type') == 'null_modifier': has_null_modifier_element = True
        print(f"  Final elements contain null_modifier: {has_null_modifier_element}")
        if expects_modifier != has_null_modifier_element:
            print(f"  ***** MISMATCH: Expected modifier {expects_modifier}, Got in elements {has_null_modifier_element} for word '{word}' *****")