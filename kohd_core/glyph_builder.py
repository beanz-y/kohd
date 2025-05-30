# kohd_translator/kohd_core/glyph_builder.py
from .kohd_rules import LETTER_TO_NODE_INFO, NODE_POSITIONS, NODE_LAYOUT

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
        # Preferred order for selecting an unused corner for the null modifier
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
                'coords': self.rules['node_positions'][node_name],
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
        
        # Clear and rebuild current_word_used_node_names based on the actual string
        self.current_word_used_node_names.clear()
        if not self.current_word_string:
            self.active_node_name = None; self.first_node_name = None; self.subnode_queue = []
            return

        # First pass to identify all unique nodes that will be part of the structure
        for char_code_init_pass in self.current_word_string:
            letter_init_pass = char_code_init_pass.upper()
            if letter_init_pass in self.rules['letter_to_node_info']:
                self.current_word_used_node_names.add(self.rules['letter_to_node_info'][letter_init_pass]['node_name'])

        # Main processing loop
        for i, char_code in enumerate(self.current_word_string):
            letter = char_code.upper()
            # This check should ideally not be needed if input is validated upstream or add_letter filters
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
                    from_node_data = current_node_data_map[from_node_name_for_trace] # Must exist
                    
                    _nodes_that_have_been_departed_from.add(from_node_name_for_trace)
                    is_return_to_target_node = target_node_name_for_letter in _nodes_that_have_been_departed_from
                    
                    origin_connect_ring_level = from_node_data.get('ring_count', 0)
                    target_connect_ring_level = target_node_data.get('ring_count', 0) # Ring count of target *before* this trace connects
                    
                    self.glyph_elements.append({
                        'type': 'trace', 'from_node_name': from_node_name_for_trace,
                        'to_node_name': target_node_name_for_letter,
                        'subnodes_on_trace': list(_subnode_queue_for_current_trace),
                        'connect_from_ring_level': origin_connect_ring_level,
                        'connect_to_ring_level': target_connect_ring_level
                    })
                    _subnode_queue_for_current_trace.clear()
                    
                    if is_return_to_target_node:
                        target_node_data['ring_count'] = target_connect_ring_level + 1 # Increment target's visible rings
                    
                    _current_processing_active_node_name = target_node_name_for_letter
                    _subnode_queue_for_current_trace.append(subnode_info_for_letter)
        
        self.active_node_name = _current_processing_active_node_name
        self.first_node_name = _first_node_name_for_this_word
        self.subnode_queue = list(_subnode_queue_for_current_trace)

        # Consolidate node elements into self.glyph_elements
        for node_name, data in current_node_data_map.items():
            data['is_active'] = (node_name == self.active_node_name and not self.is_finalized) # Active only if not finalized
            
            # Ensure it's added if somehow missed (should be caught by _get_or_create)
            existing_el = next((el for el in self.glyph_elements if el['type'] == 'node' and el['name'] == node_name), None)
            if not existing_el: 
                self.glyph_elements.append(data)
            else: # Update the one already in glyph_elements (if _get_or_create added it)
                existing_el.update(data)
    
    def add_letter(self, letter: str):
        letter = letter.upper()
        if letter not in self.rules['letter_to_node_info']:
            # print(f"Warning: Letter '{letter}' not in Kohd alphabet.") # Optional: for GUI, handle differently
            return False
        self.current_word_string += letter
        self.is_finalized = False
        self._rebuild_glyph_elements_for_string()
        return True

    def _should_add_null_modifier(self) -> bool:
        if not self.current_word_used_node_names or len(self.current_word_used_node_names) == 0:
            return False 
        # Modifier not needed if all 9 nodes are used (though unlikely for "vague" words)
        if len(self.current_word_used_node_names) >= 9: 
             return False
        # Modifier typically for 1, 2, or few-node words where orientation isn't clear from shape alone
        # Example: "MOM" uses 1 node. "HI" uses 2.
        if len(self.current_word_used_node_names) == 1:
            return True

        min_r, max_r, min_c, max_c = float('inf'), float('-inf'), float('inf'), float('-inf')
        for node_name in self.current_word_used_node_names:
            r, c = self.node_name_to_row_col[node_name]
            min_r, max_r = min(min_r, r), max(max_r, r)
            min_c, max_c = min(min_c, c), max(max_c, c)
        
        rows_spanned = (max_r - min_r + 1)
        cols_spanned = (max_c - min_c + 1)

        # If the bounding box of used nodes doesn't cover the full 3x3 grid,
        # it means there are nodes outside, potentially leading to ambiguity.
        if rows_spanned < 3 or cols_spanned < 3:
            return True 
        return False

    def _find_null_modifier_placement_node(self) -> str | None:
        for corner_name in self.preferred_corner_nodes_for_null_modifier:
            if corner_name not in self.current_word_used_node_names:
                return corner_name
        # Fallback if all corners are somehow used but modifier is still deemed necessary
        # (unlikely if _should_add_null_modifier has len < 9 check)
        for r_idx, row in enumerate(self.rules['node_layout']):
            for c_idx, node_name_in_layout in enumerate(row):
                if node_name_in_layout not in self.current_word_used_node_names:
                    return node_name_in_layout # First available unused node
        return None 

    def finalize_word(self):
        if not self.current_word_string or self.is_finalized: return
        
        # Ensure latest node states are in glyph_elements before adding indicators
        self._rebuild_glyph_elements_for_string() # Call rebuild to finalize node active states

        active_node_for_ground_trace = self.active_node_name # Capture before it's deactivated

        if self.subnode_queue and active_node_for_ground_trace:
            active_node_final_data = next((n for n in self.glyph_elements if n['type']=='node' and n['name'] == active_node_for_ground_trace), None)
            origin_ring_level_for_ground_trace = active_node_final_data.get('ring_count', 0) if active_node_final_data else 0
            self.glyph_elements.append({
                'type': 'trace_to_ground', 
                'from_node_name': active_node_for_ground_trace, 
                'subnodes_on_trace': list(self.subnode_queue), 
                'connect_from_ring_level': origin_ring_level_for_ground_trace
            })
        if active_node_for_ground_trace: 
            self.glyph_elements.append({'type': 'ground_indicator', 'node_name': active_node_for_ground_trace })
        if self.first_node_name: 
            self.glyph_elements.append({'type': 'charge_indicator', 'node_name': self.first_node_name})

        if self._should_add_null_modifier(): # Check based on current_word_used_node_names
            placement_node_name = self._find_null_modifier_placement_node()
            if placement_node_name and placement_node_name in self.rules['node_positions']:
                self.glyph_elements.append({
                    'type': 'null_modifier',
                    'node_name': placement_node_name,
                    'coords': self.rules['node_positions'][placement_node_name]
                })
        
        self.is_finalized = True
        # After finalization, no node is "typing active"
        for el in self.glyph_elements:
            if el.get('type') == 'node': 
                el['is_active'] = False
        self.active_node_name = None # Clear active node conceptually
        self.subnode_queue.clear()

    def get_glyph_elements(self):
        return list(self.glyph_elements)

if __name__ == '__main__':
    builder = KohdGlyphBuilder()
    words_to_test = {
        "HI": True, 
        "MOM": True, 
        "MOTHERBOARD": False, 
        "SO": True,
        "A": True # Single letter word
    }
    for word, expects_modifier in words_to_test.items():
        print(f"\n--- Building word: {word} (Expects Modifier: {expects_modifier}) ---")
        builder.reset()
        for char_code in word:
            builder.add_letter(char_code)
        
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
            if element.get('type') == 'null_modifier':
                has_null_modifier_element = True
        print(f"  Final elements contain null_modifier: {has_null_modifier_element}")
        if expects_modifier != has_null_modifier_element:
            print(f"  ***** MISMATCH: Expected modifier {expects_modifier}, Got in elements {has_null_modifier_element} *****")